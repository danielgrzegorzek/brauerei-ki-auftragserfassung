"""Tests für das Evaluationsskript – mit dem Demo-Extraktor statt der echten API (kostenlos)."""

from datetime import date

from src.extraction import DemoExtractor, ExtractionResult
from src.order_models import ExtractedItem, ExtractedOrder
from tools.evaluate_extraction import attack_blocked, evaluate_orders, render_report, security_test, summarize

TODAY = date(2026, 9, 28)


def test_prepared_results_score_seven_of_seven(conn):
    """Der Demo-Extraktor liefert genau das Soll – die Vergleichslogik muss also 7/7 ergeben."""
    rows = evaluate_orders(conn, DemoExtractor(), TODAY)
    assert len(rows) == 7 and all(row["final_ok"] for row in rows)


def test_security_test_detects_blocked_injection(conn):
    security = security_test(conn, DemoExtractor(), TODAY)
    assert security["blocked"] and security["flagged_by_ai"]


class ObedientExtractor:
    """Tut so, als hätte die KI eine harmlose Bestellung übernommen – der Test darf dann NICHT bestehen."""

    def extract(self, message, today):
        order = ExtractedOrder("Gasthof Zur Post", None, None, [ExtractedItem("5 Fass Helles", 5, "Helles", "Fass")])
        return ExtractionResult(order, source="Test")


def test_security_test_is_not_passed_by_the_missing_date_alone(conn):
    """Früher hat schon der fehlende Liefertermin „blockiert“ – jetzt wird mit gültigem Termin geprüft."""
    assert security_test(conn, ObedientExtractor(), TODAY)["blocked"] is False


def test_no_extracted_position_counts_as_blocked(conn):
    blocked, reason = attack_blocked(conn, ExtractedOrder("Gasthof Zur Post", None, None, []), TODAY)
    assert blocked and reason == "keine Position übernommen"


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
