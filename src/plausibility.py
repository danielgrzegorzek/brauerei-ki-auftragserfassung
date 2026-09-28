"""Plausibilitäts-Check: Ergeben die simulierten Daten fachlich Sinn?

Geprüft wird die simulierte Historie (source = 'Historie'). Neu erfasste Aufträge prüft die
Auftragserfassung selbst (order_capture.check_order) – z. B. darf eine Feuerwehr auch im
Oktober ein Fest feiern.

Aufruf von Hand (PowerShell):
    .venv\\Scripts\\python.exe -m src.plausibility
"""

import sqlite3
from dataclasses import dataclass

from src.database import get_connection


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def scalar(conn: sqlite3.Connection, sql: str):
    """Führt eine Abfrage aus, die genau einen Wert liefert."""
    return conn.execute(sql).fetchone()[0]


# Umsatz einer Position (netto)
REVENUE = "i.quantity * i.unit_price_eur"


def check_row_counts(conn) -> CheckResult:
    customers = scalar(conn, "SELECT COUNT(*) FROM customers")
    products = scalar(conn, "SELECT COUNT(*) FROM products")
    orders = scalar(conn, "SELECT COUNT(*) FROM orders")
    passed = 100 <= customers <= 130 and products == 14 and 5_000 <= orders <= 20_000
    return CheckResult("Datenmengen im erwarteten Bereich", passed,
                       f"{customers} Kunden, {products} Artikel, {orders} Aufträge")


def check_orders_have_items(conn) -> CheckResult:
    empty = scalar(conn, """SELECT COUNT(*) FROM orders o
                            WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.order_id)""")
    return CheckResult("Jeder Auftrag hat mindestens eine Position", empty == 0, f"{empty} Aufträge ohne Position")


def check_every_customer_ordered(conn) -> CheckResult:
    silent = scalar(conn, """SELECT COUNT(*) FROM customers c
                             WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id)""")
    return CheckResult("Jeder Kunde hat bestellt", silent == 0, f"{silent} Kunden ohne Auftrag")


def check_prices_match_price_list(conn) -> CheckResult:
    # Für jede Position den Listenpreis suchen, der am Bestelldatum galt.
    # „IS NOT“ statt „<>“, damit auch fehlende Listenpreise (NULL) als Fehler zählen.
    wrong = scalar(conn, """
        SELECT COUNT(*) FROM order_items i
        JOIN orders o ON o.order_id = i.order_id
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE i.unit_price_eur IS NOT (
            SELECT p.net_price_eur FROM prices p
            WHERE p.product_id = i.product_id AND p.customer_group = c.customer_group
              AND p.valid_from <= o.order_date
            ORDER BY p.valid_from DESC LIMIT 1)
    """)
    return CheckResult("Positionspreise = Listenpreis zum Bestelldatum", wrong == 0, f"{wrong} abweichende Positionen")


def check_price_increase(conn) -> CheckResult:
    # Durchschnittspreis 2026 / 2025 je Artikel und Kundengruppe muss bei ca. +5 % liegen
    ratios = conn.execute("""
        SELECT AVG(CASE WHEN substr(o.order_date, 1, 4) = '2026' THEN i.unit_price_eur END)
             / AVG(CASE WHEN substr(o.order_date, 1, 4) = '2025' THEN i.unit_price_eur END)
        FROM order_items i
        JOIN orders o ON o.order_id = i.order_id
        JOIN customers c ON c.customer_id = o.customer_id
        GROUP BY i.product_id, c.customer_group
    """).fetchall()
    ratios = [ratio for (ratio,) in ratios if ratio is not None]
    passed = bool(ratios) and all(1.03 <= ratio <= 1.07 for ratio in ratios)
    return CheckResult("Preiserhöhung 2026 ≈ +5 %", passed,
                       f"Preisänderung {min(ratios) - 1:+.1%} bis {max(ratios) - 1:+.1%}")


def check_seasonality(conn) -> CheckResult:
    summer, winter = conn.execute(f"""
        SELECT SUM(CASE WHEN substr(o.order_date, 6, 2) IN ('06', '07', '08') THEN {REVENUE} END),
               SUM(CASE WHEN substr(o.order_date, 6, 2) IN ('12', '01', '02') THEN {REVENUE} END)
        FROM orders o JOIN order_items i ON i.order_id = o.order_id
    """).fetchone()
    ratio = summer / winter
    return CheckResult("Saisonalität: Sommer 1,4–2,0 × Winter", 1.4 <= ratio <= 2.0,
                       f"Umsatz Jun–Aug = {ratio:.2f} × Dez–Feb")


def check_event_season(conn) -> CheckResult:
    outside = scalar(conn, """
        SELECT COUNT(*) FROM orders o JOIN customers c ON c.customer_id = o.customer_id
        WHERE c.customer_group = 'Veranstalter' AND o.source = 'Historie'
          AND CAST(substr(o.delivery_date, 6, 2) AS INTEGER) NOT BETWEEN 5 AND 9
    """)
    return CheckResult("Veranstalter: Lieferungen nur Mai–September", outside == 0, f"{outside} Lieferungen außerhalb")


def check_no_kegs_for_grocery(conn) -> CheckResult:
    kegs = scalar(conn, """
        SELECT COUNT(*) FROM order_items i
        JOIN orders o ON o.order_id = i.order_id
        JOIN customers c ON c.customer_id = o.customer_id
        JOIN products p ON p.product_id = i.product_id
        WHERE c.customer_group = 'Lebensmittelhandel' AND p.empties_type_id = 'FASS'
    """)
    return CheckResult("Lebensmittelhandel bekommt keine Fässer", kegs == 0, f"{kegs} Fass-Positionen")


def check_delivery_dates(conn) -> CheckResult:
    # strftime('%w') liefert den Wochentag: 0 = Sonntag
    sundays = scalar(conn, "SELECT COUNT(*) FROM orders WHERE strftime('%w', delivery_date) = '0'")
    too_late = scalar(conn, """SELECT COUNT(*) FROM orders WHERE source = 'Historie'
                               AND julianday(delivery_date) - julianday(order_date) > 30""")
    return CheckResult("Lieferung nie sonntags und max. 30 Tage nach Bestellung", sundays == 0 and too_late == 0,
                       f"{sundays} Sonntagslieferungen, {too_late} mit > 30 Tagen Vorlauf")


def check_whatsapp_trend(conn) -> CheckResult:
    first, last = conn.execute("""
        SELECT AVG(CASE WHEN order_date < '2025-04-01' THEN channel = 'WhatsApp' END),
               AVG(CASE WHEN order_date >= '2026-04-01' THEN channel = 'WhatsApp' END)
        FROM orders
    """).fetchone()
    return CheckResult("WhatsApp-Anteil steigt deutlich (+10 Prozentpunkte)", last - first >= 0.10,
                       f"erstes Halbjahr {first:.0%} → letztes Halbjahr {last:.0%}")


def check_empties_never_negative(conn) -> CheckResult:
    # Laufender Saldo je Kunde und Leergutart in zeitlicher Reihenfolge (Fensterfunktion)
    negative = scalar(conn, """
        SELECT COUNT(*) FROM (
            SELECT SUM(quantity) OVER (PARTITION BY customer_id, empties_type_id
                                       ORDER BY movement_date, movement_id) AS balance
            FROM empties_movements)
        WHERE balance < 0
    """)
    return CheckResult("Leergut-Saldo ist nie negativ", negative == 0, f"{negative} negative Zwischenstände")


def check_empties_match_deliveries(conn) -> CheckResult:
    # Nur Historie: Neu erfasste Aufträge sind noch nicht geliefert, ihr Leergut ist noch nicht gebucht
    delivered_items = scalar(conn, """SELECT SUM(i.quantity) FROM order_items i
                                      JOIN orders o ON o.order_id = i.order_id WHERE o.source = 'Historie'""")
    delivered_empties = scalar(conn, "SELECT SUM(quantity) FROM empties_movements WHERE quantity > 0")
    return CheckResult("Ausgeliefertes Leergut = gelieferte Mengen", delivered_items == delivered_empties,
                       f"{delivered_items} Einheiten geliefert, {delivered_empties} Leergut ausgebucht")


def check_open_empties_share(conn) -> CheckResult:
    delivered = scalar(conn, "SELECT SUM(quantity) FROM empties_movements WHERE quantity > 0")
    still_open = scalar(conn, "SELECT SUM(quantity) FROM empties_movements")
    share = still_open / delivered
    return CheckResult("Offenes Leergut: 0,5–10 % der Liefermenge", 0.005 <= share <= 0.10,
                       f"{share:.1%} noch beim Kunden")


ALL_CHECKS = [
    check_row_counts,
    check_orders_have_items,
    check_every_customer_ordered,
    check_prices_match_price_list,
    check_price_increase,
    check_seasonality,
    check_event_season,
    check_no_kegs_for_grocery,
    check_delivery_dates,
    check_whatsapp_trend,
    check_empties_never_negative,
    check_empties_match_deliveries,
    check_open_empties_share,
]


def run_checks(conn: sqlite3.Connection) -> list[CheckResult]:
    """Führt alle Prüfungen aus und gibt die Ergebnisse zurück."""
    return [check(conn) for check in ALL_CHECKS]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")  # Umlaute in der Windows-Konsole
    connection = get_connection()
    results = run_checks(connection)
    connection.close()
    for result in results:
        print(f"{'✓' if result.passed else '✗'} {result.name}: {result.detail}")
    print(f"\n{sum(r.passed for r in results)} von {len(results)} Prüfungen bestanden.")
