"""Tests für die Demo-Nachrichten und ihre vorbereiteten Ergebnisse."""

from datetime import date

import pytest

from src.demo_messages import DEMO_MESSAGES, FRIDAY, next_weekday, weekday_next_week
from src.master_data import ORDER_CHANNELS
from src.order_models import BEVERAGES, UNITS


def test_next_weekday_is_always_in_the_future():
    friday = date(2026, 10, 2)
    assert next_weekday(date(2026, 9, 28), FRIDAY) == friday      # Montag → Freitag derselben Woche
    assert next_weekday(friday, FRIDAY) == date(2026, 10, 9)      # Freitag → nächster Freitag


def test_weekday_next_week():
    assert weekday_next_week(date(2026, 9, 28), 2) == date(2026, 10, 7)  # Montag → Mittwoch der Folgewoche


@pytest.mark.parametrize("message", DEMO_MESSAGES, ids=lambda m: m.title)
@pytest.mark.parametrize("today", [date(2026, 9, 28), date(2027, 3, 5)])
def test_prepared_results_use_the_ai_format(message, today):
    order = message.extract(today)
    assert message.channel in ORDER_CHANNELS
    assert order.delivery_date > today
    for extracted in order.items:
        assert extracted.quantity > 0
        assert extracted.beverage is None or extracted.beverage in BEVERAGES
        assert extracted.unit is None or extracted.unit in UNITS
