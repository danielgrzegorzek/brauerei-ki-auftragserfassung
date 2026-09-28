"""Tests für den Plausibilitäts-Check."""

import pytest

from src.plausibility import ALL_CHECKS, check_no_kegs_for_grocery


# parametrize: pytest führt den Test einmal je Prüfung aus → jede Prüfung erscheint einzeln im Ergebnis
@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda check: check.__name__)
def test_generated_data_passes_check(conn, check):
    result = check(conn)
    assert result.passed, f"{result.name}: {result.detail}"


def test_check_detects_keg_for_grocery(writable_conn):
    """Der Check selbst muss Fehler finden – sonst wäre er wertlos."""
    grocery_order = writable_conn.execute("""
        SELECT o.order_id FROM orders o JOIN customers c ON c.customer_id = o.customer_id
        WHERE c.customer_group = 'Lebensmittelhandel' LIMIT 1
    """).fetchone()[0]
    writable_conn.execute(
        "INSERT INTO order_items VALUES (?, 990, 'HELL-F50', 1, 135.0)", (grocery_order,)
    )
    assert not check_no_kegs_for_grocery(writable_conn).passed
