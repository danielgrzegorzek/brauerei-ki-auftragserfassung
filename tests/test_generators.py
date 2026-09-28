"""Tests für den Auftrags- und den Leergut-Generator."""

import random
from datetime import date

from src.data_setup import build_database
from src.database import get_connection
from src.empties_generator import customer_movements
from src.order_generator import END_DATE, START_DATE, price_on


def fingerprint(db_path):
    """Kennzahlen, die sich bei jeder Datenänderung ändern würden."""
    conn = get_connection(db_path)
    values = conn.execute("""
        SELECT (SELECT COUNT(*) FROM orders),
               (SELECT SUM(quantity * unit_price_eur) FROM order_items),
               (SELECT SUM(quantity) FROM empties_movements),
               (SELECT GROUP_CONCAT(name) FROM customers)
    """).fetchone()
    conn.close()
    return values


def test_same_seed_gives_identical_database(db_path, tmp_path):
    second = tmp_path / "second.db"
    build_database(second, seed=42)
    assert fingerprint(second) == fingerprint(db_path)


def test_different_seed_gives_different_database(db_path, tmp_path):
    other = tmp_path / "other.db"
    build_database(other, seed=1)
    assert fingerprint(other) != fingerprint(db_path)


def test_price_on_uses_latest_valid_price():
    price_list = {("HELL-K20", "Gastronomie"): [(date(2024, 1, 1), 17.5), (date(2026, 1, 1), 18.4)]}
    assert price_on(price_list, "HELL-K20", "Gastronomie", date(2025, 12, 31)) == 17.5
    assert price_on(price_list, "HELL-K20", "Gastronomie", date(2026, 1, 1)) == 18.4


def test_orders_lie_within_simulation_period(conn):
    first, last = conn.execute("SELECT MIN(order_date), MAX(order_date) FROM orders").fetchone()
    assert first >= START_DATE.isoformat()
    assert last <= END_DATE.isoformat()


def test_item_numbers_are_steps_of_ten(conn):
    wrong = conn.execute("SELECT COUNT(*) FROM order_items WHERE item_no % 10 != 0").fetchone()[0]
    assert wrong == 0


def test_returns_never_exceed_what_customer_has():
    deliveries = [
        (1, date(2025, 6, 2), {"KASTEN": 10, "FASS": 4}),
        (2, date(2025, 6, 9), {"KASTEN": 8}),
        (3, date(2025, 6, 16), {"FASS": 2}),
    ]
    movements = customer_movements("K1001", deliveries, random.Random(1))
    balance = {"KASTEN": 0, "FASS": 0}
    for _, _, empties_type, quantity, _ in movements:
        balance[empties_type] += quantity
        assert balance[empties_type] >= 0


def test_long_break_creates_pickup_without_order():
    deliveries = [
        (1, date(2025, 9, 1), {"FASS": 10}),
        (2, date(2026, 5, 4), {"FASS": 10}),  # Monate später: dazwischen muss abgeholt werden
    ]
    movements = customer_movements("K1001", deliveries, random.Random(1))
    pickups = [m for m in movements if m[3] < 0 and m[4] is None]
    assert pickups and pickups[0][1] == date(2025, 9, 8)  # 7 Tage nach der ersten Lieferung
