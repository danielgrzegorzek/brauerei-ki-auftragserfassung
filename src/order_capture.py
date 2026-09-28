"""Auftragserfassung: KI-Ergebnis mit Stammdaten abgleichen, prüfen und speichern.

Ablauf:
1. build_draft()  – KI-Ergebnis → Auftragsentwurf: Kunde und Artikel aus dem Stamm zuordnen
2. check_order()  – Entwurf (ggf. vom Menschen geändert) gegen die Geschäftsregeln prüfen
3. save_order()   – bestätigten Auftrag speichern (erst nach Klick des Menschen)

Grundsatz: Der Abgleich (1) gibt nur Hinweise (Warnung/Info), WIE er zugeordnet hat.
Blockierende Fehler kommen ausschließlich aus der Prüfung (2) – denn nur die läuft nach
jeder Änderung des Menschen neu und kennt den aktuellen Stand.
"""

import difflib
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from src.formatting import format_eur, format_number
from src.order_models import ExtractedItem, ExtractedOrder

# Stufen der Hinweise
ERROR = "error"      # blockiert das Speichern
WARNING = "warning"  # bitte prüfen, Speichern trotzdem möglich
INFO = "info"        # zur Kenntnis

MAX_DAYS_AHEAD = 60             # Liefertermin weiter in der Zukunft → Warnung
UNUSUAL_QUANTITY_FACTOR = 2     # Menge über dem Doppelten der bisher größten Menge → Warnung
CUSTOMER_MATCH_CUTOFF = 0.75    # Mindest-Ähnlichkeit (0–1) für einen unsicheren Kundentreffer


@dataclass
class Issue:
    level: str  # ERROR, WARNING oder INFO
    text: str


@dataclass
class DraftLine:
    """Position im Entwurf: Originaltext, zugeordneter Artikel, Menge und Hinweise aus dem Abgleich."""
    original_text: str
    product_id: str | None
    quantity: int
    hints: list[Issue] = field(default_factory=list)


@dataclass
class Draft:
    """Auftragsentwurf nach dem Abgleich – Grundlage für die Prüfung durch den Menschen."""
    customer_id: str | None
    customer_hints: list[Issue]
    delivery_date: date | None
    lines: list[DraftLine]


@dataclass
class CheckedLine:
    product_id: str | None
    quantity: int
    unit_price: float | None  # Nettopreis je Einheit (None = kein Preis → nicht freigegeben)
    deposit: float            # Pfand je Einheit
    issues: list[Issue]

    @property
    def net_value(self) -> float:
        return self.quantity * (self.unit_price or 0)


@dataclass
class CheckResult:
    issues: list[Issue]        # Hinweise zum ganzen Auftrag (Kunde, Termin, Leergut)
    lines: list[CheckedLine]

    @property
    def net_total(self) -> float:
        return sum(line.net_value for line in self.lines)

    @property
    def deposit_total(self) -> float:
        return sum(line.quantity * line.deposit for line in self.lines)

    def all_issues(self) -> list[Issue]:
        return self.issues + [issue for line in self.lines for issue in line.issues]

    @property
    def has_errors(self) -> bool:
        return any(issue.level == ERROR for issue in self.all_issues())


# ---------- Stammdaten laden ----------

def load_customers(conn: sqlite3.Connection) -> dict[str, dict]:
    """{Kundennummer: {"name", "group", "city"}}"""
    rows = conn.execute("SELECT customer_id, name, customer_group, city FROM customers ORDER BY name")
    return {cid: {"name": name, "group": group, "city": city} for cid, name, group, city in rows}


def load_products(conn: sqlite3.Connection) -> dict[str, dict]:
    """{Artikelnummer: {"name", "beverage", "volume", "unit", "deposit"}}"""
    rows = conn.execute("""
        SELECT p.product_id, p.name, p.beverage, p.volume_liters, e.name, e.deposit_eur
        FROM products p JOIN empties_types e ON e.empties_type_id = p.empties_type_id
        ORDER BY p.name
    """)
    return {pid: {"name": name, "beverage": beverage, "volume": volume, "unit": unit, "deposit": deposit}
            for pid, name, beverage, volume, unit, deposit in rows}


def customer_history(conn: sqlite3.Connection, customer_id: str) -> dict[str, tuple[int, int]]:
    """Bestellhistorie je Artikel: {Artikelnummer: (Anzahl Bestellungen, größte bisherige Menge)}."""
    rows = conn.execute("""
        SELECT i.product_id, COUNT(*), MAX(i.quantity)
        FROM order_items i JOIN orders o ON o.order_id = i.order_id
        WHERE o.customer_id = ?
        GROUP BY i.product_id
    """, (customer_id,))
    return {product_id: (count, max_quantity) for product_id, count, max_quantity in rows}


def price_on(conn: sqlite3.Connection, product_id: str, customer_group: str, day: date) -> float | None:
    """Am Stichtag gültiger Nettopreis – None, wenn der Artikel für die Kundengruppe keinen Preis hat."""
    row = conn.execute("""
        SELECT net_price_eur FROM prices
        WHERE product_id = ? AND customer_group = ? AND valid_from <= ?
        ORDER BY valid_from DESC LIMIT 1
    """, (product_id, customer_group, day.isoformat())).fetchone()
    return row[0] if row else None


# ---------- Stufe 1: Abgleich ----------

def match_customer(name: str | None, customers: dict[str, dict]) -> tuple[str | None, list[Issue]]:
    """Ordnet den erkannten Kundennamen einer Kundennummer zu: exakt, sonst ähnlich, sonst gar nicht."""
    if not name:
        return None, [Issue(WARNING, "Die KI hat keinen Kunden erkannt – bitte Kunden auswählen.")]
    ids_by_name = {customer["name"]: cid for cid, customer in customers.items()}
    for customer_name, cid in ids_by_name.items():
        if customer_name.casefold() == name.casefold():
            return cid, []
    close = difflib.get_close_matches(name, list(ids_by_name), n=1, cutoff=CUSTOMER_MATCH_CUTOFF)
    if close:
        return ids_by_name[close[0]], [Issue(WARNING, f"Kunde nicht exakt erkannt: „{name}“ → „{close[0]}“ "
                                                      "zugeordnet. Bitte prüfen.")]
    return None, [Issue(WARNING, f"„{name}“ ist nicht im Kundenstamm. Ein Neukunde muss zuerst angelegt werden "
                                 "(in SAP: Geschäftspartner anlegen).")]


def match_product(item: ExtractedItem, products: dict[str, dict],
                  history: dict[str, tuple[int, int]]) -> tuple[str | None, list[Issue]]:
    """Sucht den Artikel zu Sorte, Einheit und Größe. Bei mehreren Treffern entscheidet die Historie."""
    if item.beverage is None:
        return None, [Issue(WARNING, f"Artikel nicht erkannt: „{item.original_text}“ – bitte Artikel auswählen "
                                     "oder Position löschen.")]
    candidates = [
        pid for pid, product in products.items()
        if product["beverage"] == item.beverage
        and (item.unit is None or product["unit"] == item.unit)
        and (item.size_liters is None or product["volume"] == item.size_liters)
    ]
    if not candidates:
        return None, [Issue(WARNING, f"„{item.original_text}“ gibt es so nicht im Sortiment – bitte Artikel auswählen.")]
    if len(candidates) == 1:
        return candidates[0], []

    # Mehrere Artikel passen (z. B. Fassgröße fehlt) → der, den der Kunde am häufigsten bestellt
    ordered_before = sorted((c for c in candidates if c in history), key=lambda c: history[c][0], reverse=True)
    if ordered_before:
        chosen = ordered_before[0]
        return chosen, [Issue(INFO, f"Nicht eindeutig – „{products[chosen]['name']}“ gewählt, "
                                    "weil der Kunde diesen Artikel bisher am häufigsten bestellt.")]
    if len({products[c]["unit"] for c in candidates}) == 1:
        # Nur die Größe fehlt und es gibt keine Historie → Standard: größtes Gebinde
        chosen = max(candidates, key=lambda c: products[c]["volume"])
        return chosen, [Issue(WARNING, f"Größe nicht angegeben und keine Bestellhistorie – "
                                       f"„{products[chosen]['name']}“ angenommen. Bitte prüfen.")]
    return None, [Issue(WARNING, f"„{item.original_text}“ ist mehrdeutig (Kasten oder Fass?) – bitte Artikel auswählen.")]


def build_draft(conn: sqlite3.Connection, extracted: ExtractedOrder) -> Draft:
    """Stufe 1: KI-Ergebnis mit den Stammdaten abgleichen."""
    customer_id, customer_hints = match_customer(extracted.customer_name, load_customers(conn))
    history = customer_history(conn, customer_id) if customer_id else {}
    products = load_products(conn)
    lines = []
    for item in extracted.items:
        hints = [Issue(INFO, f"KI-Hinweis: {item.note}")] if item.note else []
        product_id, match_hints = match_product(item, products, history)
        lines.append(DraftLine(item.original_text, product_id, item.quantity, hints + match_hints))
    return Draft(customer_id, customer_hints, extracted.delivery_date, lines)


# ---------- Stufe 2: Prüfung ----------

def check_delivery_date(delivery_date: date | None, today: date) -> list[Issue]:
    if delivery_date is None:
        return [Issue(ERROR, "Kein Liefertermin – bitte Datum wählen.")]
    if delivery_date < today:
        return [Issue(ERROR, "Der Liefertermin liegt in der Vergangenheit.")]
    if delivery_date.weekday() == 6:
        return [Issue(ERROR, "Sonntags wird nicht ausgeliefert – bitte einen anderen Tag wählen.")]
    if delivery_date == today:
        return [Issue(WARNING, "Lieferung noch heute – bitte mit der Tourenplanung abstimmen.")]
    if delivery_date > today + timedelta(days=MAX_DAYS_AHEAD):
        return [Issue(WARNING, f"Der Liefertermin liegt mehr als {MAX_DAYS_AHEAD} Tage in der Zukunft.")]
    return []


def open_empties_hint(conn: sqlite3.Connection, customer_id: str) -> list[Issue]:
    """Hinweis, wie viel Leergut beim Kunden steht – der Fahrer soll es mitnehmen."""
    rows = conn.execute("""
        SELECT e.name, SUM(m.quantity), SUM(m.quantity) * e.deposit_eur
        FROM empties_movements m JOIN empties_types e ON e.empties_type_id = m.empties_type_id
        WHERE m.customer_id = ?
        GROUP BY e.empties_type_id HAVING SUM(m.quantity) > 0
    """, (customer_id,)).fetchall()
    if not rows:
        return []
    parts = [f"{format_number(quantity)} × {name}" for name, quantity, _ in rows]
    deposit = sum(value for _, _, value in rows)
    return [Issue(INFO, f"Beim Kunden steht noch Leergut: {', '.join(parts)} ({format_eur(deposit)} Pfand) "
                        "– bei der Lieferung mitnehmen.")]


def check_order(conn: sqlite3.Connection, customer_id: str | None, delivery_date: date | None,
                lines: list[tuple[str | None, int]], today: date) -> CheckResult:
    """Stufe 2: Prüft den (ggf. vom Menschen geänderten) Entwurf. lines = [(Artikelnummer, Menge), …]"""
    customers = load_customers(conn)
    products = load_products(conn)
    issues = check_delivery_date(delivery_date, today)
    if customer_id is None:
        issues.insert(0, Issue(ERROR, "Kein Kunde ausgewählt."))
    if not lines:
        issues.append(Issue(ERROR, "Der Auftrag hat keine Positionen."))
    group = customers[customer_id]["group"] if customer_id else None
    history = customer_history(conn, customer_id) if customer_id else {}

    checked, seen = [], set()
    for product_id, quantity in lines:
        line_issues, price, deposit = [], None, 0.0
        if quantity <= 0:
            line_issues.append(Issue(ERROR, "Die Menge muss größer als 0 sein."))
        if product_id is None:
            line_issues.append(Issue(ERROR, "Kein Artikel ausgewählt."))
        else:
            product = products[product_id]
            deposit = product["deposit"]
            if product_id in seen:
                line_issues.append(Issue(WARNING, "Der Artikel steht mehrfach im Auftrag – zusammenfassen?"))
            seen.add(product_id)
            if group:
                price = price_on(conn, product_id, group, today)
                if price is None:
                    line_issues.append(Issue(ERROR, f"„{product['name']}“ ist für die Kundengruppe „{group}“ "
                                                    "nicht freigegeben (kein Preis hinterlegt)."))
                elif product_id not in history:
                    line_issues.append(Issue(INFO, "Der Kunde hat diesen Artikel bisher noch nie bestellt."))
                elif quantity > UNUSUAL_QUANTITY_FACTOR * history[product_id][1]:
                    line_issues.append(Issue(WARNING, f"Ungewöhnlich hohe Menge: {format_number(quantity)} "
                                                      f"(bisher höchstens {format_number(history[product_id][1])}). "
                                                      "Tippfehler?"))
        checked.append(CheckedLine(product_id, quantity, price, deposit, line_issues))

    if customer_id:
        issues += open_empties_hint(conn, customer_id)
    return CheckResult(issues, checked)
