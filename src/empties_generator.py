"""Simulierte Leergut-Bewegungen: Auslieferung (+) und Rückgabe (−) von Kästen und Fässern."""

import random
import sqlite3
from datetime import date, timedelta

from src.order_generator import END_DATE

# Anteil des beim Kunden stehenden Leerguts, der bei einer Rückgabe mitkommt (von, bis)
RETURN_SHARE = {"KASTEN": (0.85, 1.0), "FASS": (0.90, 1.0)}
# Schwund: Anteil des gelieferten Leerguts, der nie zurückkommt
LOSS_RATE_NORMAL = {"KASTEN": 0.01, "FASS": 0.003}
LOSS_RATE_PROBLEM = {"KASTEN": 0.05, "FASS": 0.02}  # „Problemkunden“ (ca. 10 %)
PROBLEM_CUSTOMER_SHARE = 0.10
# Ab so vielen Tagen ohne Lieferung wird das Leergut separat abgeholt (z. B. Saisonende, nach einem Fest)
PICKUP_AFTER_DAYS = 21
PICKUP_DELAY_DAYS = 7


def load_deliveries(conn: sqlite3.Connection) -> dict[str, list[tuple[int, date, dict[str, int]]]]:
    """Liefert je Kunde seine Lieferungen: [(Auftrag, Lieferdatum, {Leergutart: Menge}), …] chronologisch."""
    rows = conn.execute("""
        SELECT o.customer_id, o.order_id, o.delivery_date, p.empties_type_id, SUM(i.quantity)
        FROM orders o
        JOIN order_items i ON i.order_id = o.order_id
        JOIN products p ON p.product_id = i.product_id
        GROUP BY o.order_id, p.empties_type_id
        ORDER BY o.customer_id, o.delivery_date, o.order_id
    """)
    deliveries: dict[str, list] = {}
    for customer_id, order_id, delivery_date, empties_type, quantity in rows:
        customer_deliveries = deliveries.setdefault(customer_id, [])
        if not customer_deliveries or customer_deliveries[-1][0] != order_id:
            customer_deliveries.append((order_id, date.fromisoformat(delivery_date), {}))
        customer_deliveries[-1][2][empties_type] = quantity
    return deliveries


def not_on_sunday(day: date) -> date:
    return day + timedelta(days=1) if day.weekday() == 6 else day


def customer_movements(customer_id, deliveries, rng: random.Random) -> list[tuple]:
    """Simuliert die Leergut-Bewegungen eines Kunden: (Kunde, Datum, Leergutart, Menge, Auftrag)."""
    is_problem_customer = rng.random() < PROBLEM_CUSTOMER_SHARE
    loss_rate = LOSS_RATE_PROBLEM if is_problem_customer else LOSS_RATE_NORMAL
    at_customer = {"KASTEN": 0, "FASS": 0}  # rückgabefähiges Leergut, das gerade beim Kunden steht
    movements = []
    last_delivery = None

    for order_id, delivery_date, quantities in deliveries:
        # 1. Rückgabe: bei der Lieferung – oder nach langer Pause als separate Abholung
        long_break = last_delivery is not None and (delivery_date - last_delivery).days > PICKUP_AFTER_DAYS
        for empties_type in at_customer:
            returned = round(at_customer[empties_type] * rng.uniform(*RETURN_SHARE[empties_type]))
            if returned > 0:
                if long_break:
                    pickup_date = not_on_sunday(last_delivery + timedelta(days=PICKUP_DELAY_DAYS))
                    movements.append((customer_id, pickup_date, empties_type, -returned, None))
                else:
                    movements.append((customer_id, delivery_date, empties_type, -returned, order_id))
                at_customer[empties_type] -= returned

        # 2. Lieferung: volles Gebinde raus, ein kleiner Teil geht als Schwund verloren
        for empties_type, quantity in quantities.items():
            movements.append((customer_id, delivery_date, empties_type, quantity, order_id))
            lost = rng.binomialvariate(quantity, loss_rate[empties_type])
            at_customer[empties_type] += quantity - lost
        last_delivery = delivery_date

    # Nach der letzten Lieferung: Abholung nur, wenn die lange Pause noch im Simulationszeitraum liegt
    if last_delivery + timedelta(days=PICKUP_AFTER_DAYS) <= END_DATE:
        pickup_date = not_on_sunday(last_delivery + timedelta(days=PICKUP_DELAY_DAYS))
        for empties_type in at_customer:
            returned = round(at_customer[empties_type] * rng.uniform(*RETURN_SHARE[empties_type]))
            if returned > 0:
                movements.append((customer_id, pickup_date, empties_type, -returned, None))
    return movements


def generate_empties_movements(conn: sqlite3.Connection, rng: random.Random) -> None:
    """Erzeugt die Leergut-Bewegungen aller Kunden und speichert sie chronologisch."""
    movements = []
    for customer_id, deliveries in load_deliveries(conn).items():
        movements += customer_movements(customer_id, deliveries, rng)
    movements.sort(key=lambda m: (m[1], m[0]))  # nach Datum, dann Kunde
    conn.executemany(
        "INSERT INTO empties_movements (customer_id, movement_date, empties_type_id, quantity, order_id) "
        "VALUES (?, ?, ?, ?, ?)",
        [(customer_id, day.isoformat(), empties_type, quantity, order_id)
         for customer_id, day, empties_type, quantity, order_id in movements],
    )
