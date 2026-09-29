"""Tests für die Chat-Logik: Antworten der Brauerei, Rückfragen und Schnellantworten – ohne KI."""

from datetime import date

import pytest

from src.chat import (
    ASSIGN_CUSTOMER_REPLY, BREWERY, CUSTOMER, NO_ORDER_REPLY, NOTICE, PERSONAS, SAFETY_REPLY, UNKNOWN_CUSTOMER_REPLY,
    ChatMessage, QuickReply, apply_quick_reply, confirmation_text, keyword_candidates, now_berlin,
    open_quick_replies, product_question, reply_for_draft,
)
from src.demo_messages import CHAT_EXAMPLES, DEMO_MESSAGES, INJECTION_EXAMPLE
from src.message_safety import instruction_warnings
from src.order_capture import WARNING, DraftLine, Issue, build_draft, load_products
from src.order_models import ExtractedItem, ExtractedOrder

TODAY = date(2026, 9, 28)  # ein Montag
MESSAGES = {message.title: message for message in DEMO_MESSAGES + CHAT_EXAMPLES}


def reply_for(conn, title, answered=frozenset()):
    extracted = MESSAGES[title].extract(TODAY)
    draft = build_draft(conn, extracted)
    return extracted, draft, reply_for_draft(conn, extracted, draft, TODAY, answered,
                                             instruction_warnings(MESSAGES[title].text))


def reply_for_order(conn, customer, items, delivery=date(2026, 10, 2)):
    extracted = ExtractedOrder(customer, delivery, None, items)
    return reply_for_draft(conn, extracted, build_draft(conn, extracted), TODAY)


def size_line(text="3 Fass Helles"):
    item = ExtractedItem(text, 3, "Helles", "Fass")
    return item, DraftLine(text, "HELL-F50", 3, [Issue(WARNING, "Größe angenommen", "size_assumed")])


# ---------- Eingangsbestätigung und Rückfragen ----------

def test_clean_order_gets_receipt_with_summary_not_binding_confirmation(conn):
    _, draft, reply = reply_for(conn, "Stammwirt bestellt per WhatsApp")
    products = load_products(conn)
    assert reply.text.startswith("Danke, Ihre Bestellung ist eingegangen")
    assert f"5 × {products['HELL-F50']['name']}" in reply.text
    assert "Freitag, 02.10.2026" in reply.text
    assert "gleich die Bestätigung" in reply.text   # Eingang ≠ verbindliche Zusage
    assert reply.quick_replies == []


def test_ambiguous_lemonade_gets_question_with_quick_replies(conn):
    _, _, reply = reply_for(conn, "Volksfest")
    assert "Welche Sorte meinen Sie bei „10 Kasten Limo gemischt“" in reply.text
    assert {option.product_id for option in reply.quick_replies} == {"ZITRO-K20", "ORANGE-K20", "COLAMIX-K20"}
    assert {option.line_index for option in reply.quick_replies} == {3}


def test_quick_reply_completes_the_order(conn):
    extracted, draft, reply = reply_for(conn, "Volksfest")
    choice = next(option for option in reply.quick_replies if option.product_id == "ZITRO-K20")
    updated = apply_quick_reply(draft, choice)
    assert updated.lines[3].product_id == "ZITRO-K20"
    assert draft.lines[3].product_id is None  # Original bleibt unverändert
    after = reply_for_draft(conn, extracted, updated, TODAY, answered={3})
    assert after.text.startswith("Danke, Ihre Bestellung ist eingegangen")
    assert after.quick_replies == []


def test_typo_quantity_gets_buttons_so_nobody_has_to_type(conn):
    """Jede Rückfrage hat Knöpfe – eine getippte Antwort wäre eine neue Bestellung."""
    extracted, draft, reply = reply_for(conn, "Tippfehler")
    assert "Stimmt die Menge bei „50 Fass Weißbier“" in reply.text
    labels = [option.label for option in reply.quick_replies]
    assert labels[0] == "Ja, 50 stimmt" and labels[1].startswith("Nein, wie sonst:")
    usual = reply.quick_replies[1]
    after = reply_for_draft(conn, extracted, apply_quick_reply(draft, usual), TODAY, answered={0})
    assert after.text.startswith("Danke, Ihre Bestellung ist eingegangen")
    assert f"{usual.quantity} × " in after.text


def test_missing_date_gets_next_delivery_days_as_buttons(conn):
    extracted = ExtractedOrder("Gasthof Zur Post", None, None, [ExtractedItem("10 Kasten Helles", 10, "Helles", "Kasten")])
    draft = build_draft(conn, extracted)
    reply = reply_for_draft(conn, extracted, draft, TODAY)
    assert "Für wann dürfen wir liefern?" in reply.text
    assert [option.label for option in reply.quick_replies] == ["Di, 29.09.", "Mi, 30.09.", "Do, 01.10."]
    after = reply_for_draft(conn, extracted, apply_quick_reply(draft, reply.quick_replies[2]), TODAY)
    assert "Donnerstag, 01.10.2026" in after.text


def test_offered_days_start_later_after_cutoff(conn):
    """Nach 14 Uhr bietet der Chat „morgen“ nicht mehr an – sonst widerspräche er dem Bestellschluss."""
    extracted = ExtractedOrder("Gasthof Zur Post", None, None, [ExtractedItem("10 Kasten Helles", 10, "Helles", "Kasten")])
    reply = reply_for_draft(conn, extracted, build_draft(conn, extracted), TODAY, after_cutoff=True)
    assert [option.label for option in reply.quick_replies] == ["Mi, 30.09.", "Do, 01.10.", "Fr, 02.10."]


def test_sunday_is_skipped_in_offered_days(conn):
    saturday = date(2026, 10, 3)
    extracted = ExtractedOrder("Gasthof Zur Post", date(2026, 10, 4), "Sonntag",
                               [ExtractedItem("10 Kasten Helles", 10, "Helles", "Kasten")])
    reply = reply_for_draft(conn, extracted, build_draft(conn, extracted), saturday)
    assert "Sonntags liefern wir leider nicht" in reply.text
    assert [option.label for option in reply.quick_replies][0] == "Mo, 05.10."


def test_only_one_question_at_a_time(conn):
    """Mehrere offene Fragen → nur die erste mit Knöpfen, die Knöpfe gehören eindeutig zu ihr."""
    items = [ExtractedItem("10 Kasten Limo", 10, None, "Kasten"), ExtractedItem("5 Kasten Limo", 5, None, "Kasten")]
    reply = reply_for_order(conn, "Gasthof Zur Post", items)
    assert {option.line_index for option in reply.quick_replies} == {0}
    assert "Danach hätten wir noch eine kurze Frage." in reply.text


def test_kegs_for_grocery_retail_are_declined(conn):
    _, _, reply = reply_for(conn, "Supermarkt möchte Fässer")
    assert "„2 Fass Helles“ können wir Ihnen leider nicht liefern." in reply.text


def test_unknown_customer_gets_contact_promise(conn):
    _, _, reply = reply_for(conn, "Neukunde mit unbekanntem Artikel")
    assert reply.text.startswith(UNKNOWN_CUSTOMER_REPLY)
    assert "„2 Kasten Dunkles“ haben wir leider nicht im Sortiment." in reply.text


def test_ambiguous_customer_is_not_treated_as_new_customer(conn):
    reply = reply_for_order(conn, "Zum Ochsen", [ExtractedItem("10 Kasten Helles", 10, "Helles", "Kasten")])
    assert reply.text.startswith(ASSIGN_CUSTOMER_REPLY)


def test_unclear_item_is_not_called_out_of_assortment(conn):
    """„Nicht im Sortiment“ nur, wenn es feststeht – sonst meldet sich der Innendienst."""
    reply = reply_for_order(conn, "Gasthof Zur Post", [ExtractedItem("2 Fass Bier", 2, None, "Fass")])
    assert "nicht im Sortiment" not in reply.text
    assert "nicht sicher, welchen Artikel" in reply.text


def test_no_receipt_when_the_order_has_errors(conn):
    reply = reply_for_order(conn, "Gasthof Zur Post", [ExtractedItem("Helles wie immer", 0, "Helles", "Kasten")])
    assert not reply.text.startswith("Danke, Ihre Bestellung ist eingegangen")


def test_injection_gets_safety_reply(conn):
    _, _, reply = reply_for(conn, INJECTION_EXAMPLE.title)
    assert reply.text == SAFETY_REPLY and reply.quick_replies == []


def test_message_without_order_gets_help(conn):
    extracted = ExtractedOrder("Gasthof Zur Post", None, None, [])
    reply = reply_for_draft(conn, extracted, build_draft(conn, extracted), TODAY)
    assert reply.text == NO_ORDER_REPLY


# ---------- Artikel-Rückfragen ----------

def test_missing_keg_size_without_history_asks_for_size(conn):
    item, line = size_line()
    reply = product_question(0, item, line, load_products(conn), allowed=None)
    assert reply.text == "Welche Fassgröße meinen Sie bei „3 Fass Helles“ – 30 l oder 50 l?"
    assert [option.product_id for option in reply.quick_replies] == ["HELL-F30", "HELL-F50"]


def test_quick_replies_respect_customer_group(conn):
    """Nur freigegebene Artikel werden angeboten."""
    item, line = size_line()
    assert product_question(0, item, line, load_products(conn), allowed={"HELL-F50"}) is None


@pytest.mark.parametrize("text, unit, expected", [
    ("10 Kasten Limo gemischt", "Kasten", {"ZITRO-K20", "ORANGE-K20", "COLAMIX-K20"}),
    ("10 Kasten Limonaden gemischt", "Kasten", {"ZITRO-K20", "ORANGE-K20", "COLAMIX-K20"}),  # Wortstamm
    ("10 Kasten Limos", "Kasten", {"ZITRO-K20", "ORANGE-K20", "COLAMIX-K20"}),               # Mehrzahl
    ("15 Kasten Alkoholfreies", "Kasten", {"HELLAF-K20", "WEISSAF-K20"}),
    ("2 Kasten Dunkles", "Kasten", set()),
    ("2 Fass Bier", "Fass", set()),   # zu allgemein – nicht nur Weißbier anbieten
])
def test_keyword_candidates(conn, text, unit, expected):
    assert set(keyword_candidates(text, unit, load_products(conn))) == expected


def test_button_labels_are_always_distinct(conn):
    item = ExtractedItem("2 Weiß", 2, None, None)
    line = DraftLine(item.original_text, None, 2, [Issue(WARNING, "nicht erkannt", "not_recognized")])
    reply = product_question(0, item, line, load_products(conn), allowed={"WEISS-F30", "WEISS-F50", "WEISS-K20"})
    labels = [option.label for option in reply.quick_replies]
    assert len(labels) == len(set(labels)) == 3


# ---------- Schnellantworten, Bestätigung, Hilfsfunktionen ----------

def test_open_quick_replies_survive_notices_but_not_new_messages():
    choice = QuickReply("50 l", 0, product_id="HELL-F50")
    question = ChatMessage(BREWERY, "Welche Größe?", "10:00", [choice])
    assert open_quick_replies([question, ChatMessage(NOTICE, "Demo-Modus …", "")]) == [choice]
    assert open_quick_replies([question, ChatMessage(CUSTOMER, "Hallo", "10:01")]) == []


def test_binding_confirmation_names_order_lines_and_date(conn):
    products = load_products(conn)
    text = confirmation_text(10067, date(2026, 10, 2), f"5 × {products['HELL-F50']['name']}")
    assert "10067" in text and "bestätigt" in text and "Freitag, 02.10.2026" in text
    assert products["HELL-F50"]["name"] in text


@pytest.mark.parametrize("example", CHAT_EXAMPLES, ids=lambda m: m.title)
def test_chat_examples_are_written_by_known_personas(example):
    assert example.sender in PERSONAS.values()


def test_clock_is_german_time():
    assert now_berlin().tzinfo.key == "Europe/Berlin"
