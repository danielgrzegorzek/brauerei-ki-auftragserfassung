"""Tests für Schema, Schlüssel und automatischen Datenbank-Aufbau."""

import sqlite3

import pytest

from src.data_setup import ensure_database
from src.database import SCHEMA_VERSION, create_schema, get_connection, read_schema_version


@pytest.fixture
def empty_db(tmp_path):
    """Leere Datenbank mit Schema und einem Kunden, einem Artikel, einem Auftrag."""
    conn = get_connection(tmp_path / "empty.db")
    create_schema(conn)
    conn.execute("INSERT INTO customers VALUES ('K1001', 'Gasthof Test', 'Gastronomie', 'Deggendorf')")
    conn.execute("INSERT INTO empties_types VALUES ('KASTEN', 'Kasten', 3.10)")
    conn.execute("INSERT INTO products VALUES ('HELL-K20', 'Helles', 'Helles', 'Helles', 10.0, 'KASTEN')")
    conn.execute("INSERT INTO orders VALUES (100001, 'K1001', '2026-09-28', '2026-10-02', 'WhatsApp', 'Historie')")
    conn.execute("INSERT INTO order_items VALUES (100001, 10, 'HELL-K20', 5, 17.50)")
    yield conn
    conn.close()


def test_schema_creates_all_tables(empty_db):
    tables = {row[0] for row in empty_db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"empties_types", "products", "prices", "customers",
                      "orders", "order_items", "empties_movements"}


def test_schema_version_is_stored(empty_db):
    assert read_schema_version(empty_db) == SCHEMA_VERSION


def test_foreign_key_rejects_unknown_customer(empty_db):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        empty_db.execute("INSERT INTO orders VALUES (100002, 'K9999', '2026-09-28', '2026-10-02', 'Telefon', 'Historie')")


def test_foreign_key_prevents_deleting_customer_with_orders(empty_db):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        empty_db.execute("DELETE FROM customers WHERE customer_id = 'K1001'")


def test_composite_key_rejects_duplicate_item(empty_db):
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        empty_db.execute("INSERT INTO order_items VALUES (100001, 10, 'HELL-K20', 1, 17.50)")


def test_check_rejects_unknown_customer_group(empty_db):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        empty_db.execute("INSERT INTO customers VALUES ('K1002', 'Test', 'Tankstelle', 'Passau')")


def test_check_rejects_delivery_before_order(empty_db):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        empty_db.execute("INSERT INTO orders VALUES (100003, 'K1001', '2026-09-28', '2026-09-01', 'Telefon', 'Historie')")


def test_strict_rejects_text_as_quantity(empty_db):
    with pytest.raises(sqlite3.IntegrityError):
        empty_db.execute("INSERT INTO order_items VALUES (100001, 20, 'HELL-K20', 'viel', 17.50)")


def test_ensure_database_builds_only_when_needed(tmp_path):
    db_path = tmp_path / "brauerei.db"
    assert ensure_database(db_path) is True    # fehlt → wird gebaut
    assert ensure_database(db_path) is False   # aktuell → bleibt

    conn = get_connection(db_path)
    conn.execute("PRAGMA user_version = 0")    # veraltetes Schema simulieren
    conn.close()
    assert ensure_database(db_path) is True    # veraltet → wird neu gebaut
    assert not db_path.with_suffix(".tmp").exists()
