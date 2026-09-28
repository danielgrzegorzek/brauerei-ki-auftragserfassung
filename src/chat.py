"""Chat-Logik der Messenger-Ansicht – ohne Streamlit, vollständig testbar.

Die Antwort der „Brauerei“ entsteht im Code aus dem Prüfergebnis: kein zweiter KI-Aufruf, also keine
Zusatzkosten und keine erfundenen Zusagen. Sofort gibt es nur eine Eingangsbestätigung oder Rückfrage –
die verbindliche Auftragsbestätigung folgt erst, wenn ein Mensch den Auftrag gespeichert hat.
Rückfragen bekommen Schnellantwort-Knöpfe; ein Klick ergänzt den Auftrag per Code.
"""

import re
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.extraction import WEEKDAYS
from src.formatting import format_date, format_number
from src.order_capture import (
    INFO, CheckResult, Draft, DraftLine, Issue, check_order, load_customers, load_products, price_on,
)
from src.order_models import ExtractedItem, ExtractedOrder

BERLIN = ZoneInfo("Europe/Berlin")
CUSTOMER, BREWERY, NOTICE = "customer", "brewery", "notice"  # Wer „spricht“ im Chat
MAX_OPTIONS = 4  # höchstens so viele Schnellantworten je Rückfrage

# „Du schreibst als …“: Anzeige → Absender, wie er im Messenger erscheint (Kunden aus dem Demo-Stamm)
PERSONAS = {
    "Sepp · Gasthof Zur Post": "Sepp (Gasthof Zur Post)",
    "Vroni · Biergarten Donaublick": "Vroni (Biergarten Donaublick)",
    "Brandl · Gasthaus Brandl": "Brandl (Gasthaus Brandl)",
    "Hans Aigner · FF Hengersberg": "Hans Aigner (FF Hengersberg)",
    "Unbekannte Nummer": "Unbekannte Nummer",
}

WELCOME = ("Servus! Hier ist der Bestellservice von Bräu am Stein. Schreiben Sie uns einfach, was Sie brauchen – "
           "zum Beispiel „bis Freitag 5 Fass Helles“.")
PRIVACY_NOTICE = ("🔒 Nachrichten gehen zur Auswertung an die Claude-API (Anthropic). Bitte keine echten Namen, "
                  "Telefonnummern oder anderen persönlichen Daten eingeben.")
DEMO_ONLY_NOTICE = ("Demo-Modus: Ohne Live-KI können nur die Beispielvorschläge ausgewertet werden – "
                    "tippen Sie oben auf einen Vorschlag.")
SAFETY_REPLY = ("Ihre Nachricht enthält Anweisungen an unser System – die führen wir nicht aus. Preise gelten laut "
                "Preisliste, und jede Bestellung prüft bei uns ein Mensch. Unser Innendienst meldet sich bei Ihnen.")
NO_ORDER_REPLY = ("Danke für Ihre Nachricht! Darin haben wir keine Bestellung gefunden – schreiben Sie einfach "
                  "Menge, Sorte und Gebinde, zum Beispiel „5 Fass Helles“.")
UNKNOWN_CUSTOMER_REPLY = ("Danke für Ihre Nachricht! Wir finden Sie noch nicht in unserer Kundenliste – unser "
                          "Innendienst meldet sich, um Sie als Kunden anzulegen.")
DATE_QUESTIONS = {
    "no_date": "Für wann dürfen wir liefern?",
    "past_date": "Der Wunschtermin liegt in der Vergangenheit – für wann dürfen wir liefern?",
    "sunday": "Sonntags liefern wir leider nicht – passt Ihnen ein anderer Tag?",
}
# Wörter, die nur das Gebinde beschreiben – helfen nicht bei der Suche nach der Sorte
UNIT_WORDS = {"kasten", "kästen", "kiste", "kisten", "kistn", "träger", "fass", "fässer", "fassl", "flaschen"}


@dataclass
class QuickReply:
    """Schnellantwort-Knopf unter einer Rückfrage: setzt bei Position line_index den Artikel product_id."""
    label: str
    line_index: int
    product_id: str


@dataclass
class ChatMessage:
    role: str   # CUSTOMER (rechts, grün), BREWERY (links) oder NOTICE (Hinweis in der Mitte)
    text: str
    time: str   # „HH:MM“
    quick_replies: list[QuickReply] = field(default_factory=list)


@dataclass
class Reply:
    text: str
    quick_replies: list[QuickReply] = field(default_factory=list)


def now_berlin() -> datetime:
    """Aktuelle Zeit in Deutschland – der Cloud-Server läuft in UTC."""
    return datetime.now(BERLIN)


def date_label(day: date) -> str:
    """'Freitag, 02.10.2026'"""
    return f"{WEEKDAYS[day.weekday()]}, {format_date(day)}"


def join_or(labels: list[str]) -> str:
    """['a', 'b', 'c'] → 'a, b oder c'"""
    return labels[0] if len(labels) == 1 else f"{', '.join(labels[:-1])} oder {labels[-1]}"


# ---------- Rückfragen mit Schnellantworten ----------

def keyword_candidates(text: str, unit: str | None, products: dict[str, dict]) -> list[str]:
    """Artikel, deren Sorte oder Warengruppe zu einem Wort der Textstelle passt: 'Limo' → alle Limonaden."""
    words = [word for word in re.findall(r"[a-zäöüß]+", text.casefold()) if len(word) >= 4 and word not in UNIT_WORDS]
    return [pid for pid, product in products.items()
            if (unit is None or product["unit"] == unit)
            and any(product["group"].casefold().startswith(word) or word in product["beverage"].casefold()
                    for word in words)]


def question_for(index: int, item: ExtractedItem, line: DraftLine, products: dict[str, dict],
                 allowed: set[str] | None) -> tuple[str | None, list[QuickReply]]:
    """Rückfrage mit Schnellantworten für eine Position – oder (None, []), wenn es nichts zu fragen gibt.
    allowed: Artikel mit Preis für die Kundengruppe (None = Kunde unbekannt, keine Einschränkung)."""
    codes = {hint.code for hint in line.hints}
    unit = products[line.product_id]["unit"] if line.product_id else item.unit

    # 1. Welche Artikel kommen in Frage?
    if "size_assumed" in codes:            # Größe fehlt, keine Historie → nachfragen statt annehmen
        kind = "size"
        candidates = [pid for pid, p in products.items() if p["beverage"] == item.beverage and p["unit"] == unit]
    elif "not_recognized" in codes:        # Sorte unklar, z. B. „Limo gemischt“ → passende Sorten anbieten
        kind = "beverage"
        candidates = keyword_candidates(item.original_text, item.unit, products)
    elif "ambiguous_unit" in codes:        # Kasten oder Fass?
        kind = "unit"
        candidates = [pid for pid, p in products.items() if p["beverage"] == item.beverage]
    elif "not_in_assortment" in codes:     # so nicht im Sortiment, z. B. Pils im 50-l-Fass → Alternativen
        kind = "alternative"
        candidates = [pid for pid, p in products.items() if p["beverage"] == item.beverage]
    else:
        return None, []
    if allowed is not None:
        candidates = [pid for pid in candidates if pid in allowed]
    minimum = 1 if kind == "alternative" else 2
    if not minimum <= len(candidates) <= MAX_OPTIONS:
        return None, []

    # 2. Beschriftung der Knöpfe und Frage
    if kind == "size":
        candidates.sort(key=lambda pid: products[pid]["volume"])
        labels = [f"{format_number(products[pid]['volume'])} l" for pid in candidates]
        size_word = "Fassgröße" if unit == "Fass" else "Größe"
        question = f"Welche {size_word} meinen Sie bei „{item.original_text}“ – {join_or(labels)}?"
    elif kind == "beverage":
        candidates.sort(key=lambda pid: products[pid]["beverage"])
        labels = [products[pid]["beverage"] for pid in candidates]
        question = f"Welche Sorte meinen Sie bei „{item.original_text}“ – {join_or(labels)}?"
    else:
        candidates.sort(key=lambda pid: products[pid]["name"])
        labels = [products[pid]["name"] for pid in candidates]
        question = (f"Kasten oder Fass bei „{item.original_text}“?" if kind == "unit"
                    else f"„{item.original_text}“ haben wir so nicht – passt {join_or(labels)}?")
    return question, [QuickReply(label, index, pid) for label, pid in zip(labels, candidates)]


def apply_quick_reply(draft: Draft, choice: QuickReply) -> Draft:
    """Setzt den gewählten Artikel in der Position – ohne KI, reine Datenänderung."""
    lines = list(draft.lines)
    lines[choice.line_index] = replace(
        lines[choice.line_index], product_id=choice.product_id,
        hints=[Issue(INFO, f"Im Chat vom Kunden gewählt: „{choice.label}“.", "chosen_in_chat")])
    return replace(draft, lines=lines)


# ---------- Antwort der Brauerei ----------

def order_summary(draft: Draft, products: dict[str, dict]) -> str:
    return ", ".join(f"{format_number(line.quantity)} × {products[line.product_id]['name']}"
                     for line in draft.lines if line.product_id)


def compose_reply(extracted: ExtractedOrder, draft: Draft, result: CheckResult, products: dict[str, dict],
                  allowed: set[str] | None, answered: set[int] = frozenset(),
                  safety_issues: list[Issue] = ()) -> Reply:
    """Eingangsbestätigung oder Rückfrage – aus Abgleich (draft) und Prüfung (result) abgeleitet.
    answered: Positionen, deren Rückfrage der Kunde schon per Schnellantwort beantwortet hat."""
    if safety_issues:
        return Reply(SAFETY_REPLY)
    if not draft.lines:
        return Reply(NO_ORDER_REPLY)

    questions, problems, options = [], [], []
    for index, (item, line, checked) in enumerate(zip(extracted.items, draft.lines, result.lines)):
        if index not in answered:
            question, choices = question_for(index, item, line, products, allowed)
            if question:
                questions.append(question)
                options += choices
                continue
        codes = {issue.code for issue in checked.issues}
        if line.product_id is None:
            problems.append(f"„{item.original_text}“ haben wir leider nicht im Sortiment.")
        elif "not_released" in codes:
            problems.append(f"„{item.original_text}“ können wir Ihnen leider nicht liefern.")
        elif "hard_limit" in codes:
            problems.append(f"„{item.original_text}“ ist mehr, als wir auf einmal liefern können – "
                            "wir melden uns wegen der Menge.")
        elif "unusual_quantity" in codes:
            questions.append(f"Nur zur Sicherheit: Stimmt die Menge bei „{item.original_text}“? "
                             "Das ist deutlich mehr als sonst.")

    if draft.customer_id is None:  # Neukunde: erst anlegen – Details klärt der Innendienst
        return Reply(" ".join([UNKNOWN_CUSTOMER_REPLY] + problems))

    order_codes = {issue.code for issue in result.issues}
    date_questions = [text for code, text in DATE_QUESTIONS.items() if code in order_codes]
    if not questions and not problems and not date_questions:
        return Reply(f"Danke, Ihre Bestellung ist eingegangen: {order_summary(draft, products)} – "
                     f"Lieferung am {date_label(draft.delivery_date)}. Wir prüfen kurz und schicken Ihnen "
                     "gleich die Bestätigung.")
    return Reply(" ".join(["Danke für Ihre Bestellung!"] + problems + questions + date_questions), options)


def reply_for_draft(conn: sqlite3.Connection, extracted: ExtractedOrder, draft: Draft, today: date,
                    answered: set[int] = frozenset(), safety_issues: list[Issue] = ()) -> Reply:
    """Prüft den Entwurf und erzeugt daraus die Antwort der Brauerei."""
    result = check_order(conn, draft.customer_id, draft.delivery_date,
                         [(line.product_id, line.quantity) for line in draft.lines], today)
    products = load_products(conn)
    allowed = None
    if draft.customer_id:
        group = load_customers(conn)[draft.customer_id]["group"]
        allowed = {pid for pid in products if price_on(conn, pid, group, today) is not None}
    return compose_reply(extracted, draft, result, products, allowed, answered, safety_issues)


def confirmation_text(order_id: int, delivery_date: date) -> str:
    """Verbindliche Auftragsbestätigung – erst nach der Freigabe durch den Menschen."""
    return (f"✅ Ihr Auftrag {order_id} ist bestätigt – Lieferung am {date_label(delivery_date)}. "
            "Vielen Dank und bis bald!")
