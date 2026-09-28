"""Tests für das Evaluationsskript – mit dem Demo-Extraktor statt der echten API (kostenlos)."""

from datetime import date

from src.extraction import DemoExtractor
from tools.evaluate_extraction import evaluate_orders, render_report, security_test, summarize

TODAY = date(2026, 9, 28)


def test_prepared_results_score_seven_of_seven(conn):
    """Der Demo-Extraktor liefert genau das Soll – die Vergleichslogik muss also 7/7 ergeben."""
    rows = evaluate_orders(conn, DemoExtractor(), TODAY)
    assert len(rows) == 7 and all(row["final_ok"] for row in rows)


def test_security_test_detects_blocked_injection(conn):
    security = security_test(conn, DemoExtractor(), TODAY)
    assert security["blocked"] and security["flagged_by_ai"]


def test_report_contains_comparison_and_details(conn):
    rows = evaluate_orders(conn, DemoExtractor(), TODAY)
    security = security_test(conn, DemoExtractor(), TODAY)
    runs = [summarize("claude-sonnet-5", TODAY, rows, security),
            summarize("claude-haiku-4-5", TODAY, rows, security)]
    report = render_report(runs)
    assert "## Modellvergleich" in report
    assert "| Claude Sonnet 5 | 28.09.2026 | 7 / 7 |" in report
    assert "## Claude Haiku 4.5 – letzter Lauf" in report
    assert "Sicherheitstest: bestanden" in report
