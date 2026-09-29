"""Chat-Logik der Messenger-Ansicht – ohne Streamlit, vollständig testbar.

Die Antwort der „Brauerei“ entsteht im Code aus Abgleich und Prüfung: kein zweiter KI-Aufruf, also keine
Zusatzkosten und keine erfundenen Zusagen.
- Sofort gibt es nur eine Eingangsbestätigung oder eine Rückfrage – die verbindliche Auftragsbestätigung
  folgt erst, wenn ein Mensch den Auftrag gespeichert hat.
- Rückfragen kommen einzeln und immer mit Schnellantwort-Knöpfen (Artikel, Menge, Liefertermin); ein Klick
  ergänzt den Auftrag per Code. Was sich nicht per Knopf klären lässt, übernimmt der Innendienst – so gibt
  es keine offene Frage, auf die man tippen müsste (eine getippte Nachricht ist eine neue Bestellung).
"""

import re
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from src.extraction import WEEKDAYS
from src.formatting import format_date, format_number
from src.order_capture import (
    INFO, ORDER_CUTOFF, CheckResult, Draft, DraftLine, Issue, check_order, customer_history,
    first_regular_delivery_day, load_customers, load_products, price_on,
)
from src.order_models import ExtractedItem, ExtractedOrder

BERLIN = ZoneInfo("Europe/Berlin")
CUSTOMER, BREWERY, NOTICE = "customer", "brewery", "notice"  # Wer „spricht“ im Chat
MAX_OPTIONS = 4        # höchstens so viele Schnellantworten je Rückfrage
DAYS_OFFERED = 3       # so viele Liefertage bietet die Terminfrage an
STEM_LENGTH = 6        # Wortstamm für die Sortensuche: „Limonaden“ → „limona“

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
ASSIGN_CUSTOMER_REPLY = ("Danke für Ihre Bestellung! Unser Innendienst ordnet sie gleich Ihrem Kundenkonto zu "
                         "und meldet sich bei Ihnen.")
CHECKING_REPLY = "Danke für Ihre Bestellung! Unser Innendienst prüft noch ein Detail und meldet sich gleich."
NOTED_REPLY = ("Danke, notiert! Unser Innendienst stellt Ihren Auftrag gerade fertig und schickt Ihnen gleich "
               "die Bestätigung.")
REPLACED_NOTICE = "Neue Bestellung erkannt – der vorige, noch nicht bestätigte Auftrag wurde verworfen."
DATE_QUESTIONS = {
    "no_date": "Für wann dürfen wir liefern?",
    "past_date": "Der Wunschtermin liegt in der Vergangenheit – für wann dürfen wir liefern?",
    "sunday": "Sonntags liefern wir leider nicht – passt Ihnen ein anderer Tag?",
}
# Wörter, die bei der Sortensuche nicht helfen: Gebinde und zu allgemeine Begriffe („Bier“ passt auf vieles)
IGNORED_WORDS = {"kasten", "kästen", "kiste", "kisten", "kistn", "träger", "fass", "fässer", "fassl", "flaschen",
                 "bier", "biere", "getränk", "getränke", "sorte", "sorten", "gemischt"}


@dataclass
class QuickReply:
    """Schnellantwort-Knopf: setzt für eine Position den Artikel oder die Menge – oder den Liefertermin."""
    label: str
    line_index: int | None = None       # None = betrifft den ganzen Auftrag (Liefertermin)
    product_id: str | None = None
    quantity: int | None = None
    delivery_date: date | None = None


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


def short_date(day: date) -> str:
    """'Fr, 02.10.' – für Knöpfe"""
    return f"{WEEKDAYS[day.weekday()][:2]}, {day.strftime('%d.%m.')}"


def join_or(labels: list[str]) -> str:
    """['a', 'b', 'c'] → 'a, b oder c'"""
    return labels[0] if len(labels) == 1 else f"{', '.join(labels[:-1])} oder {labels[-1]}"


def lines_summary(lines: list[tuple[str | None, int]], products: dict[str, dict]) -> str:
    """'5 × Helles – Fass 50 l, 10 × Weißbier – Kasten 20 × 0,5 l'"""
    return ", ".join(f"{format_number(quantity)} × {products[product_id]['name']}"
                     for product_id, quantity in lines if product_id)


# ---------- Rückfragen mit Schnellantworten ----------

def word_stems(text: str) -> set[str]:
    """Suchbegriffe einer Textstelle: Wort, Wort ohne Endung, Wortstamm – ohne Gebinde und allgemeine Wörter."""
    stems = set()
    for word in re.findall(r"[a-zäöüß]+", text.casefold()):
        if len(word) < 4 or word in IGNORED_WORDS:
            continue
        stems.add(word)
        if word.endswith(("s", "n", "e")) and len(word) > 4:
            stems.add(word[:-1])             # „Limos“ → „limo“
        if len(word) > STEM_LENGTH:
            stems.add(word[:STEM_LENGTH])    # „Limonaden“ → „limona“
    return stems


def keyword_candidates(text: str, unit: str | None, products: dict[str, dict]) -> list[str]:
    """Artikel, deren Sorte oder Warengruppe zu einem Wort der Textstelle passt: 'Limo' → alle Limonaden."""
    stems = word_stems(text)
    return [pid for pid, product in products.items()
            if (unit is None or product["unit"] == unit)
            and any(product["group"].casefold().startswith(stem)
                    or re.search(r"\b" + re.escape(stem), product["beverage"].casefold())  # nur Wortanfänge
                    for stem in stems)]


def product_question(index: int, item: ExtractedItem, line: DraftLine, products: dict[str, dict],
                     allowed: set[str] | None) -> Reply | None:
    """Rückfrage zum Artikel (Größe, Sorte, Gebinde oder Alternative) – oder None.
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
        return None
    if allowed is not None:
        candidates = [pid for pid in candidates if pid in allowed]
    minimum = 1 if kind == "alternative" else 2
    if not minimum <= len(candidates) <= MAX_OPTIONS:
        return None

    # 2. Beschriftung der Knöpfe – eindeutig, sonst der volle Artikelname
    if kind == "size":
        candidates.sort(key=lambda pid: products[pid]["volume"])
        labels = [f"{format_number(products[pid]['volume'])} l" for pid in candidates]
    elif kind == "beverage":
        candidates.sort(key=lambda pid: products[pid]["name"])
        labels = [products[pid]["beverage"] for pid in candidates]
    else:
        candidates.sort(key=lambda pid: products[pid]["name"])
        labels = [products[pid]["name"] for pid in candidates]
    if len(set(labels)) < len(labels):
        labels = [products[pid]["name"] for pid in candidates]

    # 3. Frage
    if kind == "size":
        size_word = "Fassgröße" if unit == "Fass" else "Größe"
        question = f"Welche {size_word} meinen Sie bei „{item.original_text}“ – {join_or(labels)}?"
    elif kind == "beverage":
        question = f"Welche Sorte meinen Sie bei „{item.original_text}“ – {join_or(labels)}?"
    elif kind == "unit":
        question = f"Kasten oder Fass bei „{item.original_text}“?"
    else:
        question = f"„{item.original_text}“ haben wir so nicht – passt {join_or(labels)}?"
    return Reply(question, [QuickReply(label, index, product_id=pid) for label, pid in zip(labels, candidates)])


def quantity_question(index: int, item: ExtractedItem, line: DraftLine, checked_codes: set[str],
                      history: dict[str, tuple[int, int]]) -> Reply | None:
    """Rückfrage zur Menge: ungewöhnlich hoch (Tippfehler?) oder fehlend – mit Knöpfen aus der Historie."""
    usual = history.get(line.product_id, (0, 0))[1]  # größte bisherige Menge des Kunden für diesen Artikel
    if "unusual_quantity" in checked_codes:
        options = [QuickReply(f"Ja, {format_number(line.quantity)} stimmt", index, quantity=line.quantity)]
        if usual:
            options.append(QuickReply(f"Nein, wie sonst: {format_number(usual)}", index, quantity=usual))
        return Reply(f"Nur zur Sicherheit: Stimmt die Menge bei „{item.original_text}“? "
                     "Das ist deutlich mehr als sonst.", options)
    if "zero_quantity" in checked_codes and usual:
        return Reply(f"Wie viele dürfen es bei „{item.original_text}“ sein?",
                     [QuickReply(f"Wie sonst: {format_number(usual)}", index, quantity=usual)])
    return None


def next_delivery_days(today: date, count: int = DAYS_OFFERED, after_cutoff: bool = False) -> list[date]:
    """Die nächsten regulären Liefertage – ohne Sonntag, nach Bestellschluss ohne den nächsten Liefertag."""
    days, day = [], first_regular_delivery_day(today, after_cutoff)
    while len(days) < count:
        if day.weekday() != 6:
            days.append(day)
        day += timedelta(days=1)
    return days


def date_question(result: CheckResult, today: date, after_cutoff: bool = False) -> Reply | None:
    codes = {issue.code for issue in result.issues}
    code = next((code for code in DATE_QUESTIONS if code in codes), None)
    if code is None:
        return None
    return Reply(DATE_QUESTIONS[code], [QuickReply(short_date(day), delivery_date=day)
                                        for day in next_delivery_days(today, after_cutoff=after_cutoff)])


def open_quick_replies(messages: list[ChatMessage]) -> list[QuickReply]:
    """Knöpfe der letzten Brauerei-Nachricht – solange danach nur Hinweise kamen (keine neue Nachricht)."""
    for message in reversed(messages):
        if message.role != NOTICE:
            return message.quick_replies if message.role == BREWERY else []
    return []


def apply_quick_reply(draft: Draft, choice: QuickReply) -> Draft:
    """Setzt Artikel, Menge oder Liefertermin aus der Schnellantwort – ohne KI, reine Datenänderung."""
    if choice.delivery_date is not None:  # vom Kunden gewählt – ein Hinweis zum alten Termin gilt nicht mehr
        return replace(draft, delivery_date=choice.delivery_date, date_hints=[])
    lines = list(draft.lines)
    line = lines[choice.line_index]
    if choice.product_id is not None:
        line = replace(line, product_id=choice.product_id,
                       hints=[Issue(INFO, f"Im Chat vom Kunden gewählt: „{choice.label}“.", "chosen_in_chat")])
    if choice.quantity is not None:
        line = replace(line, quantity=choice.quantity,
                       hints=line.hints + [Issue(INFO, f"Menge im Chat geklärt: {format_number(choice.quantity)}.",
                                                 "chosen_in_chat")])
    lines[choice.line_index] = line
    return replace(draft, lines=lines)


# ---------- Antwort der Brauerei ----------

def not_available_text(item: ExtractedItem, line: DraftLine) -> str:
    """Position ohne Artikel und ohne mögliche Rückfrage – nur „nicht im Sortiment“, wenn das feststeht."""
    codes = {hint.code for hint in line.hints}
    if "not_in_assortment" in codes or "sortiment" in (item.note or "").casefold():
        return f"„{item.original_text}“ haben wir leider nicht im Sortiment."
    return f"Bei „{item.original_text}“ sind wir nicht sicher, welchen Artikel Sie meinen – unser Innendienst meldet sich kurz."


def compose_reply(extracted: ExtractedOrder, draft: Draft, result: CheckResult, products: dict[str, dict],
                  allowed: set[str] | None, history: dict[str, tuple[int, int]], today: date,
                  answered: set[int] = frozenset(), safety_issues: list[Issue] = (),
                  after_cutoff: bool = False) -> Reply:
    """Eingangsbestätigung oder EINE Rückfrage mit Knöpfen – aus Abgleich (draft) und Prüfung (result).
    answered: Positionen, deren Rückfrage der Kunde schon per Schnellantwort beantwortet hat.
    after_cutoff: nach Bestellschluss – die Terminknöpfe beginnen dann einen Liefertag später."""
    if safety_issues:
        return Reply(SAFETY_REPLY)
    if not draft.lines:
        return Reply(NO_ORDER_REPLY)

    questions, problems = [], []
    for index, (item, line, checked) in enumerate(zip(extracted.items, draft.lines, result.lines)):
        codes = {issue.code for issue in checked.issues}
        if index not in answered:
            question = (product_question(index, item, line, products, allowed)
                        or quantity_question(index, item, line, codes, history))
            if question:
                questions.append(question)
                continue
        if line.product_id is None:
            problems.append(not_available_text(item, line))
        elif "not_released" in codes:
            problems.append(f"„{item.original_text}“ können wir Ihnen leider nicht liefern.")
        elif "hard_limit" in codes:
            problems.append(f"„{item.original_text}“ ist mehr, als wir auf einmal liefern können – "
                            "wir melden uns wegen der Menge.")
        elif "zero_quantity" in codes:
            problems.append(f"Die Menge bei „{item.original_text}“ klärt unser Innendienst kurz mit Ihnen.")

    if draft.customer_id is None:  # Kunde erst zuordnen bzw. anlegen – Details klärt der Innendienst
        codes = {hint.code for hint in draft.customer_hints}
        first = UNKNOWN_CUSTOMER_REPLY if "customer_unknown" in codes else ASSIGN_CUSTOMER_REPLY
        return Reply(" ".join([first] + problems))

    # Nach Bestellschluss verschoben (apply_order_cutoff) – das erfährt der Kunde gleich mit
    cutoff_note = ([f"Unser Bestellschluss für den nächsten Liefertag ist {ORDER_CUTOFF.hour} Uhr – wir liefern "
                    f"deshalb am {date_label(draft.delivery_date)}."]
                   if any(hint.code == "moved_after_cutoff" for hint in draft.date_hints) else [])

    asked_date = date_question(result, today, after_cutoff)
    if asked_date:
        questions.append(asked_date)
    if questions:  # immer nur eine Frage – die Knöpfe gehören eindeutig zu ihr
        more = " Danach hätten wir noch eine kurze Frage." if len(questions) > 1 else ""
        return Reply(" ".join(["Danke für Ihre Bestellung!"] + problems + cutoff_note + [questions[0].text + more]),
                     questions[0].quick_replies)
    if problems:
        return Reply(" ".join(["Danke für Ihre Bestellung!"] + problems + cutoff_note))
    if result.has_errors:  # Sicherheitsnetz: nie eine Eingangsbestätigung für einen fehlerhaften Auftrag
        return Reply(CHECKING_REPLY)
    summary = lines_summary([(line.product_id, line.quantity) for line in draft.lines], products)
    if cutoff_note:
        return Reply(f"Danke, Ihre Bestellung ist eingegangen: {summary}. {cutoff_note[0]} "
                     "Wir prüfen kurz und schicken Ihnen gleich die Bestätigung.")
    return Reply(f"Danke, Ihre Bestellung ist eingegangen: {summary} – Lieferung am {date_label(draft.delivery_date)}. "
                 "Wir prüfen kurz und schicken Ihnen gleich die Bestätigung.")


def reply_for_draft(conn: sqlite3.Connection, extracted: ExtractedOrder, draft: Draft, today: date,
                    answered: set[int] = frozenset(), safety_issues: list[Issue] = (),
                    after_cutoff: bool = False) -> Reply:
    """Prüft den Entwurf und erzeugt daraus die Antwort der Brauerei."""
    result = check_order(conn, draft.customer_id, draft.delivery_date,
                         [(line.product_id, line.quantity) for line in draft.lines], today, after_cutoff)
    products = load_products(conn)
    allowed, history = None, {}
    if draft.customer_id:
        group = load_customers(conn)[draft.customer_id]["group"]
        allowed = {pid for pid in products if price_on(conn, pid, group, today) is not None}
        history = customer_history(conn, draft.customer_id)
    return compose_reply(extracted, draft, result, products, allowed, history, today, answered, safety_issues,
                         after_cutoff)


def confirmation_text(order_id: int, delivery_date: date, summary: str) -> str:
    """Verbindliche Auftragsbestätigung – erst nach der Freigabe durch den Menschen, mit dem gespeicherten Stand."""
    return (f"✅ Ihr Auftrag {order_id} ist bestätigt: {summary} – Lieferung am {date_label(delivery_date)}. "
            "Vielen Dank und bis bald!")
