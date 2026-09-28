"""Simulierte Auftragshistorie über 2 Jahre: Aufträge und Auftragspositionen."""

import random
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from src.master_data import PRODUCTS

START_DATE = date(2024, 10, 1)
END_DATE = date(2026, 9, 30)
FIRST_ORDER_ID = 100001

# Saisonfaktor je Monat (1 = Durchschnitt). Zusammen mit Biergärten, Festen und dem
# Weißbier-Aufschlag ergibt sich im Sommer (Jun–Aug) ≈ 1,5–1,8 × Umsatz des Winters (Dez–Feb).
SEASON_FACTORS = {
    1: 0.85, 2: 0.85, 3: 0.90, 4: 0.95, 5: 1.10, 6: 1.20,
    7: 1.25, 8: 1.25, 9: 1.10, 10: 0.95, 11: 0.85, 12: 1.00,
}
# Weißbier und Radler laufen im Hochsommer (Jun–Aug) zusätzlich besser
SUMMER_BOOST_BEVERAGES = {"Weißbier", "Radler"}
SUMMER_BOOST = 1.25

# Sorte und Leergutart je Artikel, z. B. {"HELL-F50": ("Helles", "FASS")}
PRODUCT_INFO = {product_id: (beverage, empties) for product_id, _, beverage, _, _, empties in PRODUCTS}
CRATE_PRODUCTS = [product_id for product_id, (_, empties) in PRODUCT_INFO.items() if empties == "KASTEN"]
LEMONADES = ["ZITRO-K20", "ORANGE-K20", "COLAMIX-K20"]


@dataclass
class GroupProfile:
    """Typisches Bestellverhalten einer Kundengruppe."""
    orders_per_week: float           # durchschnittliche Anzahl Bestellungen pro Woche
    crate_quantity: tuple[int, int]  # Kästen je Position (von, bis)
    keg_quantity: tuple[int, int]    # Fässer je Position (von, bis)
    lead_days: tuple[int, int]       # Tage zwischen Bestellung und Lieferung (von, bis)
    item_probability: float          # Chance, dass ein Sortimentsartikel in einer Bestellung vorkommt


GROUP_PROFILES = {
    "Gastronomie": GroupProfile(1.0, (2, 8), (2, 5), (1, 3), 0.7),
    "Getränkegroßhandel": GroupProfile(0.5, (40, 120), (6, 20), (2, 5), 0.8),
    "Lebensmittelhandel": GroupProfile(1.0, (10, 40), (0, 0), (1, 3), 0.8),
    # Veranstalter bestellen nicht regelmäßig, sondern rund um ihre Feste (siehe event_orders)
    "Veranstalter": GroupProfile(0.0, (15, 50), (20, 60), (3, 10), 0.9),
}

# Feste Profile für Demo-Kunden, damit die Demo-Nachrichten zur Historie passen:
# Gasthof Zur Post bestellt 50-l-Fässer, Gasthaus Brandl nur kleine Mengen 30-l-Fässer usw.
DEMO_PROFILES = {
    "Gasthof Zur Post": {"size": 1.3, "assortment": ["HELL-F50", "WEISS-K20", "WEISS-F50", "HELLAF-K20", "ZITRO-K20"]},
    "Gasthaus Brandl": {"size": 0.6, "assortment": ["HELL-F30", "WEISS-F30", "PILS-K20", "HELLAF-K20"]},
    "Biergarten Donaublick": {"size": 1.5, "assortment": ["HELL-F50", "WEISS-F50", "RADLER-K20", "COLAMIX-K20", "ZITRO-K20"]},
}


@dataclass
class CustomerProfile:
    """Bestellverhalten eines einzelnen Kunden (wird nicht gespeichert, nur zur Simulation)."""
    customer_id: str
    customer_group: str
    size: float                 # Größenfaktor: 1 = durchschnittlicher Kunde seiner Gruppe
    assortment: list[str]       # Artikel, die der Kunde regelmäßig bestellt
    beer_garden: bool = False   # Biergärten haben nur April–September geöffnet
    event_months: list[int] = field(default_factory=list)  # nur Veranstalter: Monate mit Fest


@dataclass
class Order:
    """Ein simulierter Auftrag; die Auftragsnummer wird erst beim Speichern vergeben."""
    customer_id: str
    order_date: date
    delivery_date: date
    channel: str
    items: list[tuple[str, int, float]]  # (Artikel, Menge, Preis je Einheit)


def random_assortment(customer_group: str, rng: random.Random) -> list[str]:
    """Stellt ein typisches Sortiment für einen Kunden der Gruppe zusammen."""
    if customer_group == "Getränkegroßhandel":
        return list(PRODUCT_INFO)  # Großhändler führen alles
    if customer_group == "Lebensmittelhandel":
        extras = [p for p in CRATE_PRODUCTS if p not in ("HELL-K20", "WEISS-K20", "PILS-K20")]
        return ["HELL-K20", "WEISS-K20", "PILS-K20"] + [p for p in extras if rng.random() < 0.6]
    if customer_group == "Veranstalter":
        assortment = ["HELL-F50", "HELLAF-K20"] + rng.sample(LEMONADES, k=rng.randint(1, 2))
        if rng.random() < 0.7:
            assortment.append("WEISS-F50")
        if rng.random() < 0.5:
            assortment.append("RADLER-K20")
        return assortment
    # Gastronomie: Helles vom Fass (30 oder 50 l), Weißbier aus Fass oder Kasten, dazu Alkoholfreies/Limo
    keg_size = 50 if rng.random() < 0.6 else 30
    assortment = [f"HELL-F{keg_size}"]
    assortment.append(f"WEISS-F{keg_size}" if rng.random() < 0.6 else "WEISS-K20")
    if rng.random() < 0.25:
        assortment.append("PILS-F30")
    for product_id, probability in [("HELLAF-K20", 0.7), ("WEISSAF-K20", 0.5), ("RADLER-K20", 0.5)]:
        if rng.random() < probability:
            assortment.append(product_id)
    assortment += rng.sample(LEMONADES, k=rng.randint(1, 2))
    return assortment


def build_profile(customer_id: str, name: str, customer_group: str, rng: random.Random) -> CustomerProfile:
    """Erzeugt das Bestellverhalten eines Kunden."""
    size = min(3.0, rng.lognormvariate(0, 0.4))  # meist 0,5–2; wenige große Kunden
    profile = CustomerProfile(
        customer_id=customer_id,
        customer_group=customer_group,
        size=size,
        assortment=random_assortment(customer_group, rng),
        beer_garden="Biergarten" in name,
    )
    if customer_group == "Veranstalter":
        profile.event_months = rng.sample([5, 6, 7, 8, 9], k=rng.choice([1, 1, 2]))
    if name in DEMO_PROFILES:
        profile.size = DEMO_PROFILES[name]["size"]
        profile.assortment = DEMO_PROFILES[name]["assortment"]
    return profile


def load_price_list(conn: sqlite3.Connection) -> dict[tuple[str, str], list[tuple[date, float]]]:
    """Lädt alle Preise: {(Artikel, Kundengruppe): [(gültig ab, Preis), …]} aufsteigend nach Datum."""
    price_list: dict[tuple[str, str], list[tuple[date, float]]] = {}
    rows = conn.execute(
        "SELECT product_id, customer_group, valid_from, net_price_eur FROM prices ORDER BY valid_from"
    )
    for product_id, customer_group, valid_from, price in rows:
        price_list.setdefault((product_id, customer_group), []).append((date.fromisoformat(valid_from), price))
    return price_list


def price_on(price_list, product_id: str, customer_group: str, day: date) -> float:
    """Gibt den am Stichtag gültigen Preis zurück (letzter Preis mit gültig ab <= Stichtag)."""
    valid_prices = [price for valid_from, price in price_list[(product_id, customer_group)] if valid_from <= day]
    return valid_prices[-1]


def pick_channel(customer_group: str, order_date: date, rng: random.Random) -> str:
    """Wählt den Bestellkanal. Der WhatsApp-Anteil steigt über die Zeit von 20 % auf 45 %."""
    if customer_group == "Getränkegroßhandel":
        weights = {"E-Mail": 0.75, "Telefon": 0.15, "WhatsApp": 0.10}
    else:
        progress = (order_date - START_DATE).days / (END_DATE - START_DATE).days  # 0 → 1
        whatsapp = 0.20 + 0.25 * progress
        weights = {"WhatsApp": whatsapp, "E-Mail": 0.25, "Telefon": 0.75 - whatsapp}
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def order_quantity(profile: CustomerProfile, product_id: str, month: int, rng: random.Random) -> int:
    """Menge einer Position: typische Menge × Kundengröße × Saison (× Sommer-Aufschlag)."""
    group_profile = GROUP_PROFILES[profile.customer_group]
    beverage, empties_type = PRODUCT_INFO[product_id]
    low, high = group_profile.keg_quantity if empties_type == "FASS" else group_profile.crate_quantity
    quantity = rng.randint(low, high) * profile.size * SEASON_FACTORS[month]
    if beverage in SUMMER_BOOST_BEVERAGES and month in (6, 7, 8):
        quantity *= SUMMER_BOOST
    return max(1, round(quantity))


def make_order(profile, order_date, delivery_date, price_list, rng) -> Order:
    """Baut einen Auftrag aus dem Sortiment des Kunden (nicht jeder Artikel in jeder Bestellung)."""
    group_profile = GROUP_PROFILES[profile.customer_group]
    ordered = [p for p in profile.assortment if rng.random() < group_profile.item_probability]
    if not ordered:
        ordered = [profile.assortment[0]]  # mindestens der Hauptartikel
    items = [
        (
            product_id,
            order_quantity(profile, product_id, order_date.month, rng),
            price_on(price_list, product_id, profile.customer_group, order_date),
        )
        for product_id in ordered
    ]
    channel = pick_channel(profile.customer_group, order_date, rng)
    return Order(profile.customer_id, order_date, delivery_date, channel, items)


def regular_orders(profile, price_list, rng) -> list[Order]:
    """Regelmäßige Bestellungen (Gastronomie, Handel): Tag für Tag wird „gewürfelt“."""
    group_profile = GROUP_PROFILES[profile.customer_group]
    orders = []
    day = START_DATE
    while day <= END_DATE:
        is_open = not profile.beer_garden or 4 <= day.month <= 9
        if day.weekday() != 6 and is_open:  # sonntags wird nicht bestellt
            probability = group_profile.orders_per_week / 6  # 6 Werktage pro Woche
            if profile.beer_garden and day.month in (6, 7, 8):
                probability *= 1.5  # Hochsaison: Biergärten bestellen öfter nach
            if rng.random() < probability:
                delivery = day + timedelta(days=rng.randint(*group_profile.lead_days))
                if delivery.weekday() == 6:
                    delivery += timedelta(days=1)  # sonntags keine Auslieferung → Montag
                orders.append(make_order(profile, day, delivery, price_list, rng))
        day += timedelta(days=1)
    return orders


def event_orders(profile, price_list, rng) -> list[Order]:
    """Veranstalter: Großbestellung 2–4 Wochen vor dem Fest, teils Nachbestellung am Festtag."""
    orders = []
    for year in (2025, 2026):
        for month in profile.event_months:
            event_day = date(year, month, rng.randint(1, 22))
            while event_day.weekday() != 5:  # Feste beginnen an einem Samstag
                event_day += timedelta(days=1)
            order_date = event_day - timedelta(days=rng.randint(14, 28))
            delivery = event_day - timedelta(days=rng.randint(1, 2))
            orders.append(make_order(profile, order_date, delivery, price_list, rng))
            if rng.random() < 0.4:  # Nachbestellung, weil das Bier knapp wird
                orders.append(make_order(profile, event_day, event_day, price_list, rng))
    return orders


def generate_orders(conn: sqlite3.Connection, rng: random.Random) -> list[Order]:
    """Simuliert alle Aufträge aller Kunden, sortiert nach Bestelldatum."""
    price_list = load_price_list(conn)
    orders = []
    for customer_id, name, customer_group in conn.execute(
        "SELECT customer_id, name, customer_group FROM customers ORDER BY customer_id"
    ):
        profile = build_profile(customer_id, name, customer_group, rng)
        if customer_group == "Veranstalter":
            orders += event_orders(profile, price_list, rng)
        else:
            orders += regular_orders(profile, price_list, rng)
    orders.sort(key=lambda order: (order.order_date, order.customer_id))
    return orders


def insert_orders(conn: sqlite3.Connection, orders: list[Order]) -> None:
    """Vergibt Auftragsnummern (chronologisch) und schreibt Köpfe und Positionen in die Datenbank."""
    order_rows = []
    item_rows = []
    for order_id, order in enumerate(orders, start=FIRST_ORDER_ID):
        order_rows.append((order_id, order.customer_id, order.order_date.isoformat(),
                           order.delivery_date.isoformat(), order.channel))
        for position, (product_id, quantity, price) in enumerate(order.items, start=1):
            item_rows.append((order_id, position * 10, product_id, quantity, price))  # Positionen 10, 20, 30 …
    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", order_rows)
    conn.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", item_rows)
