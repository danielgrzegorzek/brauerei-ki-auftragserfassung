"""Tests für die Dashboard-Auswertungen und die Zahlenformate."""

from datetime import date

import pytest

from src import analytics
from src.analytics import Filters
from src.formatting import format_change, format_eur, format_eur_compact, format_number
from src.master_data import CUSTOMER_GROUPS

ALL = Filters(date(2024, 10, 1), date(2026, 9, 30), CUSTOMER_GROUPS)
YEAR_2025 = Filters(date(2025, 1, 1), date(2025, 12, 31), CUSTOMER_GROUPS)


def test_kpi_revenue_matches_direct_sum(conn):
    expected = conn.execute("SELECT SUM(quantity * unit_price_eur) FROM order_items").fetchone()[0]
    assert analytics.kpis(conn, ALL)["revenue"] == pytest.approx(expected)


def test_monthly_and_group_revenue_add_up_to_kpi(conn):
    total = analytics.kpis(conn, YEAR_2025)["revenue"]
    assert analytics.revenue_by_month(conn, YEAR_2025)["revenue"].sum() == pytest.approx(total)
    assert analytics.revenue_by_customer_group(conn, YEAR_2025)["revenue"].sum() == pytest.approx(total)
    assert analytics.revenue_by_product(conn, YEAR_2025)["revenue"].sum() == pytest.approx(total)
    assert len(analytics.revenue_by_month(conn, YEAR_2025)) == 12


def test_group_filter_only_returns_selected_group(conn):
    only_gastro = Filters(ALL.start, ALL.end, ("Gastronomie",))
    groups = analytics.revenue_by_customer_group(conn, only_gastro)["customer_group"].tolist()
    assert groups == ["Gastronomie"]
    assert set(analytics.top_customers(conn, only_gastro)["customer_group"]) == {"Gastronomie"}


def test_top_customers_are_sorted_and_limited(conn):
    top = analytics.top_customers(conn, ALL, limit=5)
    assert len(top) == 5
    assert top["revenue"].is_monotonic_decreasing


def test_seasonality_index_averages_100_and_shows_summer_peak(conn):
    index = analytics.seasonality_index(conn, ALL)
    assert index.mean(axis=1).tolist() == pytest.approx([100.0] * len(index))
    assert index.loc["Weißbier", 7] > 100 > index.loc["Weißbier", 1]


def test_channel_shares_add_up_to_one_per_quarter(conn):
    shares = analytics.channel_share_by_quarter(conn, ALL).groupby("quarter")["share"].sum()
    assert shares.tolist() == pytest.approx([1.0] * len(shares))


def test_open_deposit_matches_customer_table(conn):
    as_of = date(2026, 9, 30)
    total = analytics.open_deposit(conn, as_of, CUSTOMER_GROUPS)
    per_customer = analytics.open_empties_by_customer(conn, as_of, CUSTOMER_GROUPS)
    assert per_customer["deposit_eur"].sum() == pytest.approx(total)
    assert total > 0


def test_deposit_by_month_ends_with_open_deposit(conn):
    by_month = analytics.open_deposit_by_month(conn, YEAR_2025)
    assert len(by_month) == 12
    total = analytics.open_deposit(conn, YEAR_2025.end, CUSTOMER_GROUPS)
    assert by_month["deposit_eur"].iloc[-1] == pytest.approx(total)


def test_previous_year_shifts_period():
    shifted = analytics.previous_year(Filters(date(2025, 10, 1), date(2026, 9, 30), ("Gastronomie",)))
    assert (shifted.start, shifted.end) == (date(2024, 10, 1), date(2025, 9, 30))
    assert analytics.shift_year(date(2028, 2, 29), -1) == date(2027, 2, 28)


def test_german_number_formats():
    assert format_number(1234567.891, 2) == "1.234.567,89"
    assert format_eur(1234.5) == "1.234,50 €"
    assert format_eur_compact(7_960_000) == "7,96 Mio. €"
    assert format_eur_compact(812_345) == "812,3 Tsd. €"
    assert format_eur_compact(1_512) == "1.512 €"


def test_format_change():
    assert format_change(106.2, 100) == "+6,2 %"
    assert format_change(95, 100) == "-5,0 %"
    assert format_change(10, 0) is None
