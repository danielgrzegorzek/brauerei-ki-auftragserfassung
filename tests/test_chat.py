"""Tests für die Chat-Logik: Antworten der Brauerei, Rückfragen und Schnellantworten – ohne KI."""

from datetime import date

import pytest

from src.chat import (
    NO_ORDER_REPLY, PERSONAS, SAFETY_REPLY, UNKNOWN_CUSTOMER_REPLY, apply_quick_reply,
    confirmation_text, keyword_candidates, now_berlin, question_for, reply_for_draft,
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


def test_clean_order_gets_receipt_with_summary_not_binding_confirmation(conn):
    _, draft, reply = reply_for(conn, "Stammwirt bestellt per WhatsApp")
    products = load_products(conn)
    assert reply.text.startswith("Danke, Ihre Bestellung ist eingegangen")
    assert f"5 × {products['HELL-F50']['name']}" in reply.text
    assert "Freitag, 02.10." in reply.text
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


def test_typo_quantity_is_questioned_without_buttons(conn):
    _, _, reply = reply_for(conn, "Tippfehler")
    assert "Stimmt die Menge bei „50 Fass Weißbier“" in reply.text
    assert reply.quick_replies == []


def test_kegs_for_grocery_retail_are_declined(conn):
    _, _, reply = reply_for(conn, "Supermarkt möchte Fässer")
    assert "„2 Fass Helles“ können wir Ihnen leider nicht liefern." in reply.text


def test_unknown_customer_gets_contact_promise(conn):
    _, _, reply = reply_for(conn, "Neukunde mit unbekanntem Artikel")
    assert reply.text.startswith(UNKNOWN_CUSTOMER_REPLY)
    assert "„2 Kasten Dunkles“ haben wir leider nicht im Sortiment." in reply.text


def test_injection_gets_safety_reply(conn):
    _, _, reply = reply_for(conn, INJECTION_EXAMPLE.title)
    assert reply.text == SAFETY_REPLY and reply.quick_replies == []


def test_message_without_order_gets_help(conn):
    extracted = ExtractedOrder("Gasthof Zur Post", None, None, [])
    reply = reply_for_draft(conn, extracted, build_draft(conn, extracted), TODAY)
    assert reply.text == NO_ORDER_REPLY


def test_sunday_delivery_is_questioned(conn):
    extracted = ExtractedOrder("Gasthof Zur Post", date(2026, 10, 4), "Sonntag",
                               [ExtractedItem("10 Kasten Helles", 10, "Helles", "Kasten")])
    reply = reply_for_draft(conn, extracted, build_draft(conn, extracted), TODAY)
    assert "Sonntags liefern wir leider nicht" in reply.text


def test_missing_keg_size_without_history_asks_for_size(conn):
    products = load_products(conn)
    item = ExtractedItem("3 Fass Helles", 3, "Helles", "Fass")
    line = DraftLine(item.original_text, "HELL-F50", 3, [Issue(WARNING, "Größe angenommen", "size_assumed")])
    question, options = question_for(0, item, line, products, allowed=None)
    assert question == "Welche Fassgröße meinen Sie bei „3 Fass Helles“ – 30 l oder 50 l?"
    assert [option.product_id for option in options] == ["HELL-F30", "HELL-F50"]


def test_keyword_candidates(conn):
    products = load_products(conn)
    assert set(keyword_candidates("10 Kasten Limo gemischt", "Kasten", products)) == {
        "ZITRO-K20", "ORANGE-K20", "COLAMIX-K20"}
    assert keyword_candidates("2 Kasten Dunkles", "Kasten", products) == []


def test_quick_replies_respect_customer_group(conn):
    """Nur freigegebene Artikel werden angeboten."""
    products = load_products(conn)
    item = ExtractedItem("3 Fass Helles", 3, "Helles", "Fass")
    line = DraftLine(item.original_text, "HELL-F50", 3, [Issue(WARNING, "Größe angenommen", "size_assumed")])
    question, options = question_for(0, item, line, products, allowed={"HELL-F50"})
    assert question is None and options == []  # nur eine Größe erlaubt → keine Auswahl nötig


def test_binding_confirmation_names_order_and_date():
    text = confirmation_text(10067, date(2026, 10, 2))
    assert "10067" in text and "bestätigt" in text and "Freitag, 02.10." in text


@pytest.mark.parametrize("example", CHAT_EXAMPLES, ids=lambda m: m.title)
def test_chat_examples_are_written_by_known_personas(example):
    assert example.sender in PERSONAS.values()


def test_clock_is_german_time():
    assert now_berlin().tzinfo.key == "Europe/Berlin"
