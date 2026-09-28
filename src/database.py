"""Datenbank: Verbindung zur SQLite-Datei und Tabellenschema."""

import sqlite3
from pathlib import Path

# Speicherort der Datenbank: <Projektordner>/data/brauerei.db
# Der Pfad wird relativ zu dieser Datei berechnet, damit es egal ist,
# aus welchem Ordner die App gestartet wird.
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "brauerei.db"

# Versionsnummer des Schemas. Bei jeder Schemaänderung erhöhen –
# dann wird eine vorhandene alte Datenbank beim nächsten Start neu aufgebaut.
SCHEMA_VERSION = 2  # 2: Spalte orders.source (Historie / KI-Erfassung)

# Tabellenschema. Reihenfolge: erst Stammdaten, dann Bewegungsdaten.
# STRICT = SQLite prüft Datentypen streng (sonst würde z. B. Text in einer Zahlenspalte akzeptiert).
SCHEMA = """
-- ===== Stammdaten =====

-- Leergutarten mit Pfandbetrag
CREATE TABLE empties_types (
    empties_type_id TEXT PRIMARY KEY,                          -- z. B. 'KASTEN'
    name            TEXT NOT NULL,                             -- z. B. 'Kasten'
    deposit_eur     REAL NOT NULL CHECK (deposit_eur > 0)      -- Pfand je Stück
) STRICT;

-- Artikel (in SAP: Materialstamm)
CREATE TABLE products (
    product_id      TEXT PRIMARY KEY,                          -- z. B. 'HELL-K20'
    name            TEXT NOT NULL,                             -- z. B. 'Helles – Kasten 20 × 0,5 l'
    beverage        TEXT NOT NULL,                             -- Sorte, z. B. 'Weißbier Alkoholfrei'
    product_group   TEXT NOT NULL,                             -- Warengruppe (SAP), z. B. 'Alkoholfrei'
    volume_liters   REAL NOT NULL CHECK (volume_liters > 0),   -- Inhalt je Einheit (für Hektoliter)
    empties_type_id TEXT NOT NULL REFERENCES empties_types (empties_type_id)
) STRICT;

-- Nettopreise je Artikel und Kundengruppe mit Gültigkeitsbeginn
-- (in SAP: stark vereinfachte Konditionen)
CREATE TABLE prices (
    product_id     TEXT NOT NULL REFERENCES products (product_id),
    customer_group TEXT NOT NULL CHECK (customer_group IN
                       ('Gastronomie', 'Getränkegroßhandel', 'Lebensmittelhandel', 'Veranstalter')),
    valid_from     TEXT NOT NULL,                              -- Datum als 'JJJJ-MM-TT'
    net_price_eur  REAL NOT NULL CHECK (net_price_eur > 0),
    PRIMARY KEY (product_id, customer_group, valid_from)       -- zusammengesetzter Schlüssel
) STRICT;

-- Kunden (in SAP: Kundenstamm / Geschäftspartner)
CREATE TABLE customers (
    customer_id    TEXT PRIMARY KEY,                           -- z. B. 'K1001'
    name           TEXT NOT NULL,
    customer_group TEXT NOT NULL CHECK (customer_group IN
                       ('Gastronomie', 'Getränkegroßhandel', 'Lebensmittelhandel', 'Veranstalter')),
    city           TEXT NOT NULL
) STRICT;

-- ===== Bewegungsdaten =====

-- Auftragskopf: wer, wann, über welchen Kanal (in SAP: Tabelle VBAK)
CREATE TABLE orders (
    order_id      INTEGER PRIMARY KEY,                         -- Auftragsnummer
    customer_id   TEXT NOT NULL REFERENCES customers (customer_id),
    order_date    TEXT NOT NULL,
    delivery_date TEXT NOT NULL CHECK (delivery_date >= order_date),
    channel       TEXT NOT NULL CHECK (channel IN ('Telefon', 'E-Mail', 'WhatsApp')),
    source        TEXT NOT NULL DEFAULT 'Historie'             -- Herkunft: simulierte Historie oder neu erfasst
                  CHECK (source IN ('Historie', 'KI-Erfassung'))
) STRICT;

-- Auftragspositionen: was, wie viel, zu welchem Preis (in SAP: Tabelle VBAP)
CREATE TABLE order_items (
    order_id       INTEGER NOT NULL REFERENCES orders (order_id),
    item_no        INTEGER NOT NULL,                           -- 10, 20, 30 … wie in SAP
    product_id     TEXT NOT NULL REFERENCES products (product_id),
    quantity       INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_eur REAL NOT NULL CHECK (unit_price_eur > 0),   -- Preis zum Bestellzeitpunkt (bewusst kopiert)
    PRIMARY KEY (order_id, item_no)                            -- zusammengesetzter Schlüssel
) STRICT;

-- Leergut-Bewegungen: + geht zum Kunden, − kommt zurück. Summe = offenes Leergut.
CREATE TABLE empties_movements (
    movement_id     INTEGER PRIMARY KEY,
    customer_id     TEXT NOT NULL REFERENCES customers (customer_id),
    movement_date   TEXT NOT NULL,
    empties_type_id TEXT NOT NULL REFERENCES empties_types (empties_type_id),
    quantity        INTEGER NOT NULL CHECK (quantity <> 0),
    order_id        INTEGER REFERENCES orders (order_id)       -- optional: zugehöriger Auftrag
) STRICT;
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Öffnet eine Verbindung zur Datenbank und schaltet die Fremdschlüssel-Prüfung ein."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    # Wichtig: SQLite prüft Fremdschlüssel nur, wenn man es pro Verbindung einschaltet.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    """Legt alle Tabellen in einer leeren Datenbank an und merkt sich die Schemaversion."""
    conn.executescript(SCHEMA)
    # user_version ist ein freies Zahlenfeld, das SQLite in jeder Datenbankdatei mitführt
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def read_schema_version(conn: sqlite3.Connection) -> int:
    """Liest die Schemaversion einer vorhandenen Datenbank (0 = unbekannt/leer)."""
    return conn.execute("PRAGMA user_version").fetchone()[0]
