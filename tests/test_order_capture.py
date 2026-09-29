"""Tests für Abgleich und Prüfung der Auftragserfassung – je Demo-Nachricht das erwartete Verhalten."""

from datetime import date, datetime

import pytest

from src.demo_messages import DEMO_MESSAGES
from src.order_capture import (
    ERROR, INFO, WARNING, Draft, apply_order_cutoff, build_draft, captured_orders, check_delivery_date, check_order,
    delete_captured_orders, first_regular_delivery_day, is_after_cutoff, load_customers, match_customer, save_order,
)
from src.plausibility import run_checks

TODAY = date(2026, 9, 28)  # ein Montag
DEMOS = {message.title: message for message in DEMO_MESSAGES}


def run_demo(conn, title):
    """Demo-Nachricht auswerten, abgleichen und prüfen – so, wie der Mensch sie unverändert bestätigen würde."""
    draft = build_draft(conn, DEMOS[title].extract(TODAY))
    result = check_order(conn, draft.customer_id, draft.delivery_date,
                         [(line.product_id, line.quantity) for line in draft.lines], TODAY)
    return draft, result


def levels(issues):
    return {issue.level for issue in issues}


def customer_name(conn, customer_id):
    return load_customers(conn)[customer_id]["name"]


def test_missing_keg_size_is_taken_from_history(conn):
    draft, result = run_demo(conn, "Stammwirt bestellt per WhatsApp")
    assert customer_name(conn, draft.customer_id) == "Gasthof Zur Post"
    assert [line.product_id for line in draft.lines] == ["HELL-F50", "WEISS-K20"]
    assert any("am häufigsten" in hint.text for hint in draft.lines[0].hints)
    assert not result.has_errors
    assert result.net_total > 0 and result.deposit_total == 5 * 30 + 10 * 3.10


def test_clean_wholesale_order_has_no_errors_or_warnings(conn):
    _, result = run_demo(conn, "Großhändler bestellt per E-Mail")
    assert levels(result.all_issues()) <= {INFO}


def test_dialect_is_mapped_to_products(conn):
    draft, result = run_demo(conn, "Biergarten schreibt im Dialekt")
    assert [line.product_id for line in draft.lines] == ["WEISS-F50", "HELL-F50", "COLAMIX-K20"]
    assert not result.has_errors


def test_ambiguous_lemonade_must_be_chosen_by_human(conn):
    draft, result = run_demo(conn, "Feuerwehrfest – Telefonnotiz")
    assert draft.lines[3].product_id is None
    assert any("nicht erkannt" in hint.text for hint in draft.lines[3].hints)
    assert result.has_errors
    # Nach Auswahl durch den Menschen ist der Auftrag speicherbar
    fixed = [(line.product_id or "ZITRO-K20", line.quantity) for line in draft.lines]
    assert not check_order(conn, draft.customer_id, draft.delivery_date, fixed, TODAY).has_errors


def test_kegs_are_blocked_for_grocery_retail(conn):
    draft, result = run_demo(conn, "Supermarkt möchte Fässer")
    keg_line = result.lines[2]
    assert keg_line.unit_price is None
    assert any("nicht freigegeben" in issue.text for issue in keg_line.issues)
    assert result.has_errors


def test_unusual_quantity_gives_warning(conn):
    draft, result = run_demo(conn, "Tippfehler bei der Menge")
    assert draft.lines[0].product_id == "WEISS-F30"  # Brandl bestellt immer 30-l-Fässer
    assert any("Ungewöhnlich hohe Menge" in issue.text for issue in result.lines[0].issues)
    assert not result.has_errors  # Warnung, kein Fehler: der Mensch entscheidet


def test_unknown_customer_and_product_are_errors(conn):
    draft, result = run_demo(conn, "Neukunde mit unbekanntem Artikel")
    assert draft.customer_id is None
    assert any("nicht im Kundenstamm" in hint.text for hint in draft.customer_hints)
    assert draft.lines[0].product_id is None
    assert draft.lines[1].product_id == "ZITRO-K20"
    assert result.has_errors


@pytest.mark.parametrize("message", DEMO_MESSAGES, ids=lambda m: m.title)
def test_matching_only_gives_hints_never_errors(conn, message):
    """Grundsatz: Blockierende Fehler kommen nur aus der Prüfung, nie aus dem Abgleich."""
    draft = build_draft(conn, message.extract(TODAY))
    hints = draft.customer_hints + [hint for line in draft.lines for hint in line.hints]
    assert ERROR not in levels(hints)


@pytest.mark.parametrize("written, expected", [
    ("Donaublick", "Biergarten Donaublick"),                  # Namensteil
    ("FF Hengersberg", "Freiwillige Feuerwehr Hengersberg"),  # Abkürzung
    ("Brandl Wirt", "Gasthaus Brandl"),                       # allgemeines Wort ignoriert
])
def test_customer_is_matched_by_name_parts(conn, written, expected):
    """Diese Schreibweisen hat Claude in der Evaluation geliefert – sie müssen zugeordnet werden."""
    customer_id, hints = match_customer(written, load_customers(conn))
    assert customer_name(conn, customer_id) == expected
    assert levels(hints) == {WARNING}  # unsichere Zuordnung → Mensch soll prüfen


def test_ambiguous_name_parts_leave_choice_to_human():
    customers = {"K1": {"name": "Gasthof Huber", "group": "Gastronomie", "city": "Passau"},
                 "K2": {"name": "Getränke Huber GmbH", "group": "Getränkegroßhandel", "city": "Bogen"}}
    customer_id, hints = match_customer("Huber", customers)
    assert customer_id is None
    assert "mehreren Kunden" in hints[0].text and "Getränke Huber GmbH" in hints[0].text


def test_similar_customer_name_is_matched_with_warning(conn):
    customer_id, hints = match_customer("Gasthof Post", load_customers(conn))
    assert customer_name(conn, customer_id) == "Gasthof Zur Post"
    assert levels(hints) == {WARNING}


@pytest.mark.parametrize("delivery, expected", [
    (None, ERROR),                  # fehlt
    (date(2026, 9, 25), ERROR),     # Vergangenheit
    (date(2026, 10, 4), ERROR),     # Sonntag
    (TODAY, WARNING),               # heute
    (date(2027, 1, 4), WARNING),    # mehr als 60 Tage
])
def test_delivery_date_rules(delivery, expected):
    assert levels(check_delivery_date(delivery, TODAY)) == {expected}


def test_normal_delivery_date_has_no_issues():
    assert check_delivery_date(date(2026, 10, 2), TODAY) == []


@pytest.mark.parametrize("now, expected", [
    (datetime(2026, 9, 28, 13, 59), False),
    (datetime(2026, 9, 28, 14, 0), True),
    (datetime(2026, 9, 28, 23, 30), True),
])
def test_order_cutoff_is_14_oclock(now, expected):
    assert is_after_cutoff(now) is expected


@pytest.mark.parametrize("today, after_cutoff, expected", [
    (TODAY, False, date(2026, 9, 29)),              # Montag vor 14 Uhr → Dienstag
    (TODAY, True, date(2026, 9, 30)),               # Montag nach 14 Uhr → Mittwoch
    (date(2026, 10, 3), False, date(2026, 10, 5)),  # Samstag vor 14 Uhr → Montag (sonntags keine Lieferung)
    (date(2026, 10, 3), True, date(2026, 10, 6)),   # Samstag nach 14 Uhr → Dienstag
])
def test_first_regular_delivery_day(today, after_cutoff, expected):
    assert first_regular_delivery_day(today, after_cutoff) == expected


def test_next_day_after_cutoff_is_a_warning_not_an_error():
    """Nach 14 Uhr für morgen: der Mensch stimmt mit der Tourenplanung ab – Speichern bleibt möglich."""
    issues = check_delivery_date(date(2026, 9, 29), TODAY, after_cutoff=True)
    assert [(issue.level, issue.code) for issue in issues] == [(WARNING, "after_cutoff")]
    assert "14 Uhr" in issues[0].text
    assert check_delivery_date(date(2026, 9, 29), TODAY) == []                   # vor 14 Uhr: kein Hinweis
    assert check_delivery_date(date(2026, 9, 30), TODAY, after_cutoff=True) == []  # übermorgen: in Ordnung


def test_dialect_demo_for_tomorrow_warns_after_cutoff(conn):
    draft = build_draft(conn, DEMOS["Biergarten schreibt im Dialekt"].extract(TODAY))
    lines = [(line.product_id, line.quantity) for line in draft.lines]
    before = check_order(conn, draft.customer_id, draft.delivery_date, lines, TODAY)
    after = check_order(conn, draft.customer_id, draft.delivery_date, lines, TODAY, after_cutoff=True)
    assert "after_cutoff" not in {issue.code for issue in before.issues}
    assert "after_cutoff" in {issue.code for issue in after.issues}
    assert not after.has_errors


def test_dialect_demo_after_cutoff_moves_to_the_day_after_tomorrow(conn):
    """„bis morgn“ nach 14 Uhr: Der Code legt den Termin auf den übernächsten Liefertag – mit Warnhinweis."""
    draft = apply_order_cutoff(build_draft(conn, DEMOS["Biergarten schreibt im Dialekt"].extract(TODAY)), TODAY, True)
    assert draft.delivery_date == date(2026, 9, 30)  # Mittwoch statt Dienstag
    assert [(hint.level, hint.code) for hint in draft.date_hints] == [(WARNING, "moved_after_cutoff")]
    assert "29.09.2026" in draft.date_hints[0].text and "30.09.2026" in draft.date_hints[0].text
    result = check_order(conn, draft.customer_id, draft.delivery_date,
                         [(line.product_id, line.quantity) for line in draft.lines], TODAY, after_cutoff=True)
    assert "after_cutoff" not in {issue.code for issue in result.issues}  # der neue Termin ist regulär


@pytest.mark.parametrize("requested, today, after_cutoff, expected", [
    (date(2026, 9, 29), TODAY, False, date(2026, 9, 29)),             # vor 14 Uhr: bleibt
    (date(2026, 10, 2), TODAY, True, date(2026, 10, 2)),              # späterer Termin: bleibt
    (TODAY, TODAY, True, TODAY),                                       # heute: eigene Warnung, bleibt
    (date(2026, 10, 5), date(2026, 10, 3), True, date(2026, 10, 6)),  # Samstag nach 14 Uhr: Montag → Dienstag
    (date(2026, 10, 4), date(2026, 10, 3), True, date(2026, 10, 4)),  # Sonntag: eigene Prüfung, bleibt
    (None, TODAY, True, None),                                         # kein Termin: Rückfrage im Chat
])
def test_order_cutoff_only_moves_the_next_delivery_day(requested, today, after_cutoff, expected):
    moved = apply_order_cutoff(Draft("K1001", [], requested, []), today, after_cutoff)
    assert moved.delivery_date == expected
    assert bool(moved.date_hints) == (expected != requested)


def save_demo(conn, title, fix_missing_product=None):
    draft = build_draft(conn, DEMOS[title].extract(TODAY))
    lines = [(line.product_id or fix_missing_product, line.quantity) for line in draft.lines]
    return save_order(conn, draft.customer_id, draft.delivery_date, DEMOS[title].channel, lines, TODAY)


def test_saved_order_gets_next_number_and_list_prices(writable_conn):
    highest = writable_conn.execute("SELECT MAX(order_id) FROM orders").fetchone()[0]
    order_id = save_demo(writable_conn, "Stammwirt bestellt per WhatsApp")
    assert order_id == highest + 1
    source, channel = writable_conn.execute(
        "SELECT source, channel FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    assert (source, channel) == ("KI-Erfassung", "WhatsApp")
    items = writable_conn.execute(
        "SELECT item_no, product_id, quantity, unit_price_eur FROM order_items WHERE order_id = ?", (order_id,)
    ).fetchall()
    assert items == [(10, "HELL-F50", 5, 141.8), (20, "WEISS-K20", 10, 19.4)]  # Gastronomie-Preise 2026


def test_order_with_errors_is_not_saved(writable_conn):
    count_before = writable_conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    with pytest.raises(ValueError):
        save_demo(writable_conn, "Supermarkt möchte Fässer")
    assert writable_conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == count_before


def test_captured_orders_can_be_listed_and_deleted(writable_conn):
    save_demo(writable_conn, "Großhändler bestellt per E-Mail")
    save_demo(writable_conn, "Feuerwehrfest – Telefonnotiz", fix_missing_product="ZITRO-K20")
    assert len(captured_orders(writable_conn)) == 2
    history_count = writable_conn.execute("SELECT COUNT(*) FROM orders WHERE source = 'Historie'").fetchone()[0]

    assert delete_captured_orders(writable_conn) == 2
    assert captured_orders(writable_conn) == []
    assert writable_conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == history_count


def test_plausibility_still_passes_after_capturing_orders(writable_conn):
    """Ein Feuerwehrfest im Oktober ist ein echter neuer Auftrag – kein Fehler der Simulation."""
    save_demo(writable_conn, "Feuerwehrfest – Telefonnotiz", fix_missing_product="ZITRO-K20")
    failed = [result.name for result in run_checks(writable_conn) if not result.passed]
    assert failed == []


def test_zero_quantity_and_missing_product_are_errors(conn):
    result = check_order(conn, None, date(2026, 10, 2), [(None, 0)], TODAY)
    texts = [issue.text for issue in result.all_issues()]
    assert "Kein Kunde ausgewählt." in texts
    assert "Die Menge muss größer als 0 sein." in texts
    assert "Kein Artikel ausgewählt." in texts
