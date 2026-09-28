"""Tests für das Zielformat der KI-Auswertung."""

from datetime import date

from src.order_models import BEVERAGES, ExtractedOrder


def test_dict_round_trip_keeps_all_values():
    data = {
        "customer_name": "Gasthof Zur Post",
        "delivery_date": "2026-10-02",
        "delivery_date_text": "für Freitag",
        "items": [{"original_text": "5 Fass Helles", "quantity": 5, "beverage": "Helles",
                   "unit": "Fass", "size_liters": None, "note": "Fassgröße nicht angegeben"}],
        "note": None,
    }
    order = ExtractedOrder.from_dict(data)
    assert order.delivery_date == date(2026, 10, 2)
    assert order.items[0].beverage == "Helles"
    assert order.to_dict() == data


def test_missing_date_and_items_are_allowed():
    order = ExtractedOrder.from_dict({"customer_name": None, "delivery_date": None, "delivery_date_text": None})
    assert order.delivery_date is None
    assert order.items == []


def test_beverages_come_from_master_data():
    assert "Weißbier" in BEVERAGES and "Cola-Mix" in BEVERAGES
    assert "Dunkles" not in BEVERAGES
