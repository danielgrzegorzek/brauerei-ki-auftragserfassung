"""Tests für die geführte Tour: sechs Schritte, richtige Seiten, kurze Texte mit Zahlen aus den Daten."""

import re
from pathlib import Path

from src.business_case import default_result
from src.extraction import MODEL
from src.tour import PAGES, tour_steps

STEPS = tour_steps(orders_per_year=5025, saved_hours=217.2, saved_eur=8288.9)


def test_six_steps_in_the_agreed_order():
    assert [step.page for step in STEPS] == ["home", "order_entry", "order_entry", "process", "business_case",
                                             "dashboard"]
    assert [step.title for step in STEPS] == ["Das Problem der Brauerei", "Live-KI ausprobieren",
                                              "Prüfung und Mensch", "SAP-Übergabe", "Was es bringt",
                                              "Überblick und Fazit"]


def test_every_step_page_exists():
    assert all(step.page in PAGES for step in STEPS)
    assert all((Path("pages") / f"{page}.py").exists() for page in PAGES)


def test_tour_pages_match_the_navigation_in_app_py():
    """ui_tour greift mit pages[step.page] zu – die Schlüssel in app.py müssen den Dateinamen entsprechen."""
    pairs = re.findall(r'"(\w+)": st\.Page\("pages/(\w+)\.py"', Path("app.py").read_text(encoding="utf-8"))
    assert pairs and all(key == file for key, file in pairs)
    assert set(PAGES) <= {key for key, _ in pairs}


def test_every_text_is_exactly_one_sentence():
    for step in STEPS:
        sentences = [part for part in re.split(r"(?<=[.!?])\s+", step.text) if part]
        assert len(sentences) == 1, step.title


def test_numbers_come_from_the_data_in_german_format():
    assert "Rund 5.000 Bestellungen" in STEPS[0].text
    assert "1 statt 6 manuelle Schritte" in STEPS[3].text  # aus src/process.py
    assert "217 Stunden und 8.289 €" in STEPS[4].text


def test_default_result_matches_the_business_case_page(conn):
    inputs, result = default_result(conn, MODEL)
    assert inputs.phone_orders_per_year == 0       # Standard: nur WhatsApp und E-Mail
    assert inputs.minutes_manual == 6 and inputs.minutes_ai == 2
    assert result.saved_hours > 0 and result.saved_eur > 0
