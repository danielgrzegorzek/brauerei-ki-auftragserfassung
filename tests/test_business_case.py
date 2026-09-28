"""Tests für den Business Case – Rechnung von Hand nachvollziehbar, Daten aus der Test-Datenbank."""

import json
from datetime import date

import pytest

from src.business_case import (
    ASSUMPTIONS, DEFAULT_CHANNELS, DEFAULTS, EVALUATION_FILE, Inputs, calculate, calculation_steps,
    busiest_and_quietest, inputs_from_settings, measured_ai_cost, orders_by_month, orders_last_12_months,
    period_last_12_months,
)
from src.extraction import MODEL

# 600 Aufträge, 6 bzw. 2 min, 40 €/h, 2 % bzw. 1 % Fehler à 50 €, 1.000 € Betrieb, 1 Cent KI je Auftrag
EXAMPLE = Inputs(orders_per_year=600, minutes_manual=6, minutes_ai=2, hourly_rate=40,
                 error_rate_manual=0.02, error_rate_ai=0.01, cost_per_error=50,
                 operating_cost=1000, ai_cost_per_order=0.01)


def test_calculation_by_hand():
    result = calculate(EXAMPLE)
    # vorher: 600 × 6 min = 60 h → 2.400 €; 12 Fehler → 600 €; zusammen 3.000 €
    assert (result.before.hours, result.before.labor_cost) == (60, 2400)
    assert (result.before.errors, result.before.error_cost) == (12, 600)
    assert result.before.total == 3000
    # nachher: 20 h → 800 €; 6 Fehler → 300 €; KI 6 €; Betrieb 1.000 €; zusammen 2.106 €
    assert (result.after.hours, result.after.labor_cost) == (20, 800)
    assert (result.after.errors, result.after.error_cost) == (6, 300)
    assert result.after.ai_cost == pytest.approx(6)
    assert result.after.total == pytest.approx(2106)
    assert result.saved_hours == 40
    assert result.saved_eur == pytest.approx(894)
    assert result.avoided_errors == 6
    assert result.saved_work_weeks == 1


def test_savings_can_be_negative_and_are_shown_honestly():
    """Dauert die Erfassung mit KI länger, wird die Ersparnis negativ – nichts wird schöngerechnet."""
    worse = Inputs(**{**EXAMPLE.__dict__, "minutes_ai": 8})
    assert calculate(worse).saved_hours < 0 and calculate(worse).saved_eur < 0


def test_no_orders_means_only_operating_cost():
    result = calculate(Inputs(**{**EXAMPLE.__dict__, "orders_per_year": 0}))
    assert result.saved_eur == -1000


@pytest.mark.parametrize("field, value", [
    ("orders_per_year", -1), ("minutes_manual", -1), ("hourly_rate", -5),
    ("error_rate_manual", 1.5), ("error_rate_ai", -0.1), ("ai_cost_per_order", -0.01),
])
def test_invalid_inputs_are_rejected(field, value):
    with pytest.raises(ValueError):
        Inputs(**{**EXAMPLE.__dict__, field: value})


def test_settings_in_percent_are_converted():
    inputs = inputs_from_settings(600, DEFAULTS, 0.01)
    assert inputs.error_rate_manual == DEFAULTS["error_rate_manual"] / 100
    assert inputs.orders_per_year == 600


def test_calculation_steps_show_the_way_with_german_numbers():
    steps = calculation_steps(EXAMPLE, calculate(EXAMPLE))
    assert steps[0] == "**Arbeitszeit vorher:** 600 Aufträge × 6,0 min = 60 h × 40 €/h = 2.400 €"
    assert "894 € pro Jahr" in steps[-1]


def test_every_assumption_is_cautious_and_explained():
    for assumption in ASSUMPTIONS:
        assert assumption.minimum <= assumption.default <= assumption.maximum
        assert len(assumption.reason) > 30  # mindestens ein ganzer Satz Begründung
    assert DEFAULTS["minutes_ai"] < DEFAULTS["minutes_manual"]
    assert DEFAULTS["error_rate_ai"] < DEFAULTS["error_rate_manual"]


# ---------- Daten ----------

def test_orders_come_from_the_database(conn):
    per_channel = orders_last_12_months(conn)
    assert set(DEFAULT_CHANNELS) <= set(per_channel) and "Telefon" in per_channel
    start, end = period_last_12_months(conn)
    total = conn.execute("SELECT COUNT(*) FROM orders WHERE source = 'Historie' AND order_date BETWEEN ? AND ?",
                         (start.isoformat(), end.isoformat())).fetchone()[0]
    assert sum(per_channel.values()) == total
    assert (end - start).days <= 366


def test_captured_demo_orders_do_not_count(writable_conn):
    before = orders_last_12_months(writable_conn)
    writable_conn.execute("INSERT INTO orders (order_id, customer_id, order_date, delivery_date, channel, source) "
                          "SELECT MAX(order_id) + 1, 'K1001', '2026-09-30', '2026-10-02', 'WhatsApp', "
                          "'KI-Erfassung' FROM orders")
    assert orders_last_12_months(writable_conn) == before


def test_monthly_orders_and_season(conn):
    monthly = orders_by_month(conn, DEFAULT_CHANNELS)
    assert len(monthly) == 12
    assert sum(n for _, n in monthly) == sum(orders_last_12_months(conn)[c] for c in DEFAULT_CHANNELS)
    (_, busiest), (quiet_month, quietest) = busiest_and_quietest(monthly)
    assert busiest > quietest * 1.3                              # deutliche Saisonspitze
    assert quiet_month[5:7] in {"11", "12", "01", "02", "03"}     # ruhig im Winter


def test_busiest_and_quietest_by_hand():
    assert busiest_and_quietest([("2026-01", 50), ("2026-07", 150), ("2026-03", 80)]) == (
        ("2026-07", 150), ("2026-01", 50))


# ---------- gemessene KI-Kosten ----------

def test_measured_cost_uses_the_latest_run_of_the_model(tmp_path):
    path = tmp_path / "evaluation.json"
    run = {"model": "claude-sonnet-5", "model_name": "Claude Sonnet 5", "date": "2026-09-28",
           "hits": 7, "total": 7, "cost_per_message_usd": 0.0085}
    path.write_text(json.dumps([run, {**run, "date": "2026-10-05", "cost_per_message_usd": 0.009},
                                {**run, "model": "claude-haiku-4-5", "cost_per_message_usd": 0.0036}]))
    measured = measured_ai_cost("claude-sonnet-5", path)
    assert measured.usd_per_order == 0.009 and measured.measured_on == date(2026, 10, 5)
    assert "7 von 7" in measured.source_text
    assert measured_ai_cost("unbekannt", path) is None
    assert measured_ai_cost("claude-sonnet-5", tmp_path / "fehlt.json") is None


def test_real_evaluation_file_has_a_measurement_for_the_app_model():
    measured = measured_ai_cost(MODEL, EVALUATION_FILE)
    assert measured is not None and 0 < measured.eur_per_order < 0.05
