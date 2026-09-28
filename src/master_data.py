"""Stammdaten der (fiktiven) Bräu am Stein GmbH: Leergutarten, Artikel, Preise und Kunden."""

import random
import sqlite3

CUSTOMER_GROUPS = ("Gastronomie", "Getränkegroßhandel", "Lebensmittelhandel", "Veranstalter")
ORDER_CHANNELS = ("Telefon", "E-Mail", "WhatsApp")

# ---------- Leergutarten ----------
# (ID, Bezeichnung, Pfand je Stück in €)
# Kasten: 1,50 € für den Kasten + 20 Flaschen × 0,08 € = 3,10 €
EMPTIES_TYPES = [
    ("KASTEN", "Kasten", 3.10),
    ("FASS", "Fass", 30.00),
]

# ---------- Artikel (in SAP: Materialstamm) ----------
# (ID, Bezeichnung, Sorte, Warengruppe, Liter je Einheit, Leergutart)
PRODUCTS = [
    ("HELL-K20", "Helles – Kasten 20 × 0,5 l", "Helles", "Helles", 10.0, "KASTEN"),
    ("WEISS-K20", "Weißbier – Kasten 20 × 0,5 l", "Weißbier", "Weißbier", 10.0, "KASTEN"),
    ("PILS-K20", "Pils – Kasten 20 × 0,5 l", "Pils", "Pils", 10.0, "KASTEN"),
    ("HELLAF-K20", "Helles Alkoholfrei – Kasten 20 × 0,5 l", "Helles Alkoholfrei", "Alkoholfrei", 10.0, "KASTEN"),
    ("WEISSAF-K20", "Weißbier Alkoholfrei – Kasten 20 × 0,5 l", "Weißbier Alkoholfrei", "Alkoholfrei", 10.0, "KASTEN"),
    ("RADLER-K20", "Radler – Kasten 20 × 0,5 l", "Radler", "Radler", 10.0, "KASTEN"),
    ("ZITRO-K20", "Zitronenlimonade – Kasten 20 × 0,5 l", "Zitronenlimonade", "Limonade", 10.0, "KASTEN"),
    ("ORANGE-K20", "Orangenlimonade – Kasten 20 × 0,5 l", "Orangenlimonade", "Limonade", 10.0, "KASTEN"),
    ("COLAMIX-K20", "Cola-Mix – Kasten 20 × 0,5 l", "Cola-Mix", "Limonade", 10.0, "KASTEN"),
    ("HELL-F30", "Helles – Fass 30 l", "Helles", "Helles", 30.0, "FASS"),
    ("HELL-F50", "Helles – Fass 50 l", "Helles", "Helles", 50.0, "FASS"),
    ("WEISS-F30", "Weißbier – Fass 30 l", "Weißbier", "Weißbier", 30.0, "FASS"),
    ("WEISS-F50", "Weißbier – Fass 50 l", "Weißbier", "Weißbier", 50.0, "FASS"),
    ("PILS-F30", "Pils – Fass 30 l", "Pils", "Pils", 30.0, "FASS"),
]

# ---------- Preise (in SAP: Konditionen, stark vereinfacht) ----------
# Nettopreis für die Gastronomie je Artikel in €
BASE_PRICES_GASTRONOMY = {
    "HELL-K20": 17.50, "WEISS-K20": 18.50, "PILS-K20": 17.50,
    "HELLAF-K20": 17.50, "WEISSAF-K20": 18.00, "RADLER-K20": 16.50,
    "ZITRO-K20": 14.00, "ORANGE-K20": 14.00, "COLAMIX-K20": 14.50,
    "HELL-F30": 85.00, "HELL-F50": 135.00, "WEISS-F30": 92.00,
    "WEISS-F50": 145.00, "PILS-F30": 85.00,
}
# Preisfaktor je Kundengruppe (Gastronomie = 100 %). Großabnehmer zahlen weniger.
GROUP_PRICE_FACTORS = {
    "Gastronomie": 1.00,
    "Veranstalter": 0.94,
    "Lebensmittelhandel": 0.83,
    "Getränkegroßhandel": 0.77,
}
PRICE_VALID_FROM = "2024-01-01"
PRICE_INCREASE_DATE = "2026-01-01"
PRICE_INCREASE_FACTOR = 1.05  # Preiserhöhung um 5 %

# ---------- Kunden ----------
# Feste Kunden, auf die sich die Demo-Nachrichten der KI-Erfassung beziehen: (Name, Kundengruppe, Ort)
DEMO_CUSTOMERS = [
    ("Gasthof Zur Post", "Gastronomie", "Plattling"),
    ("Gasthaus Brandl", "Gastronomie", "Osterhofen"),
    ("Biergarten Donaublick", "Gastronomie", "Vilshofen an der Donau"),
    ("Getränkehandel Brunner KG", "Getränkegroßhandel", "Deggendorf"),
    ("Frischemarkt Wimmer", "Lebensmittelhandel", "Landau an der Isar"),
    ("Freiwillige Feuerwehr Hengersberg", "Veranstalter", "Hengersberg"),
]

# Orte in Niederbayern mit Gewichtung (Brauerei-Nähe = mehr Kunden)
TOWNS = {
    "Deggendorf": 6, "Plattling": 4, "Straubing": 5, "Passau": 4, "Landshut": 3,
    "Vilshofen an der Donau": 3, "Osterhofen": 3, "Hengersberg": 2, "Landau an der Isar": 3,
    "Dingolfing": 3, "Bogen": 2, "Regen": 2, "Zwiesel": 2, "Grafenau": 1,
    "Eggenfelden": 1, "Pfarrkirchen": 1,
}
# Familiennamen als Bausteine (Brandl, Brunner, Wimmer sind für Demo-Kunden reserviert)
FAMILY_NAMES = [
    "Huber", "Bauer", "Maier", "Wagner", "Schmid", "Fischer", "Weber", "Hofmann", "Gruber",
    "Lehner", "Aigner", "Moser", "Eder", "Hartl", "Obermeier", "Zeller", "Pichler", "Reiter",
    "Straßer", "Weinzierl", "Kagerer", "Rieder", "Loibl", "Stadler", "Kellner", "Sedlmeier",
    "Hierl", "Freundorfer", "Ebner", "Holzer", "Wieser", "Seidl", "Dengler", "Bachmaier",
]
INN_TYPES = ["Gasthof", "Gasthaus", "Wirtshaus", "Landgasthof"]
INN_TRADITIONAL_NAMES = [
    "Zum Hirschen", "Zum Ochsen", "Zur Linde", "Zum Goldenen Stern", "Zum Löwen",
    "Zur Krone", "Zum Schwan", "Zur Sonne", "Zum Adler", "Zum Bräu",
]
BEER_GARDEN_NAMES = [
    "Biergarten am See", "Biergarten Isarauen", "Biergarten zur Mühle", "Waldbiergarten",
    "Biergarten am Stadtpark", "Biergarten Kastanienhof", "Biergarten am Schlossberg",
]
WHOLESALE_REGIONS = ["Donau", "Isar", "Rottal", "Bayerwald", "Gäuboden", "Vilstal"]


def generate_prices() -> list[tuple[str, str, str, float]]:
    """Erzeugt die Preisliste: (Artikel, Kundengruppe, gültig ab, Nettopreis).

    Je Artikel und Kundengruppe gibt es zwei Preise: den Ausgangspreis und den Preis
    nach der Preiserhöhung. Der Lebensmittelhandel bekommt keine Fässer – daher auch
    keinen Fasspreis.
    """
    prices = []
    for product_id, _name, _beverage, _group, _liters, empties_type in PRODUCTS:
        for customer_group, factor in GROUP_PRICE_FACTORS.items():
            if customer_group == "Lebensmittelhandel" and empties_type == "FASS":
                continue
            old_price = round(BASE_PRICES_GASTRONOMY[product_id] * factor, 1)  # auf 10 Cent gerundet
            new_price = round(old_price * PRICE_INCREASE_FACTOR, 1)
            prices.append((product_id, customer_group, PRICE_VALID_FROM, old_price))
            prices.append((product_id, customer_group, PRICE_INCREASE_DATE, new_price))
    return prices


def generate_customers(rng: random.Random) -> list[tuple[str, str, str, str]]:
    """Erzeugt die Kundenliste: (Kundennummer, Name, Kundengruppe, Ort).

    Zuerst kommen die festen Demo-Kunden, danach zufällig aus Bausteinen
    zusammengesetzte Kunden. Jeder Name kommt nur einmal vor.
    """
    customers = list(DEMO_CUSTOMERS)
    used_names = {name for name, _group, _city in customers}

    def random_town() -> str:
        return rng.choices(list(TOWNS), weights=list(TOWNS.values()))[0]

    def add_customers(group: str, count: int, make_candidate) -> None:
        """Zieht so lange Namensvorschläge, bis `count` neue, eindeutige Kunden da sind."""
        added = 0
        while added < count:
            name, city = make_candidate()
            if name not in used_names:
                used_names.add(name)
                customers.append((name, group, city))
                added += 1

    def inn():
        if rng.random() < 0.7:
            name = f"{rng.choice(INN_TYPES)} {rng.choice(FAMILY_NAMES)}"
        else:
            name = f"{rng.choice(INN_TYPES)} {rng.choice(INN_TRADITIONAL_NAMES)}"
        return name, random_town()

    def beer_garden():
        return rng.choice(BEER_GARDEN_NAMES), random_town()

    def clubhouse():
        town = random_town()
        return f"Sportheim {town}", town

    def wholesaler():
        if rng.random() < 0.5:
            return f"Getränkevertrieb {rng.choice(WHOLESALE_REGIONS)} GmbH", random_town()
        return f"Getränke {rng.choice(FAMILY_NAMES)} GmbH", random_town()

    def grocery():
        if rng.random() < 0.3:
            town = random_town()
            return f"Dorfladen {town}", town
        return f"{rng.choice(['Frischemarkt', 'Markt', 'Lebensmittel'])} {rng.choice(FAMILY_NAMES)}", random_town()

    def event_organizer():
        if rng.random() < 0.2:
            return f"Festwirt {rng.choice(FAMILY_NAMES)}", random_town()
        town = random_town()
        club = rng.choice(["Freiwillige Feuerwehr", "Burschenverein", "Schützenverein", "Volksfestverein"])
        return f"{club} {town}", town

    # Gastronomie: 80 Kunden = 3 Demo-Kunden + 5 Biergärten + 6 Sportheime + 66 Wirtshäuser
    add_customers("Gastronomie", 5, beer_garden)
    add_customers("Gastronomie", 6, clubhouse)
    add_customers("Gastronomie", 66, inn)
    add_customers("Getränkegroßhandel", 7, wholesaler)      # 8 inkl. Demo-Kunde
    add_customers("Lebensmittelhandel", 14, grocery)        # 15 inkl. Demo-Kunde
    add_customers("Veranstalter", 11, event_organizer)      # 12 inkl. Demo-Kunde

    return [(f"K{1001 + i}", name, group, city) for i, (name, group, city) in enumerate(customers)]


def insert_master_data(conn: sqlite3.Connection, rng: random.Random) -> None:
    """Schreibt alle Stammdaten in die Datenbank.

    Die Fragezeichen sind Platzhalter: SQLite setzt die Werte sicher ein
    (Schutz vor SQL-Injection, kein Ärger mit Anführungszeichen in Namen).
    """
    conn.executemany("INSERT INTO empties_types VALUES (?, ?, ?)", EMPTIES_TYPES)
    conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)", PRODUCTS)
    conn.executemany("INSERT INTO prices VALUES (?, ?, ?, ?)", generate_prices())
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", generate_customers(rng))
