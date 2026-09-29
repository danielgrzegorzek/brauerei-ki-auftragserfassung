"""Tests für den Inhalt der Making-of-Seite: vollständig, kurz und passend zu Code und Messungen."""

import re
from pathlib import Path

from src import making_of
from src.business_case import measured_ai_cost
from src.extraction import MODEL
from src.order_capture import ORDER_CUTOFF

DECISIONS_FILE = Path(__file__).parent.parent / "docs" / "ENTSCHEIDUNGEN.md"


def sentences(text: str) -> int:
    return len(re.findall(r"[.!?](?:\s|$)", text))


def test_every_decision_has_phase_title_and_one_or_two_sentences():
    assert len(making_of.DECISIONS) >= 10
    for decision in making_of.DECISIONS:
        assert decision.phase and decision.title
        assert 1 <= sentences(decision.text) <= 2, decision.title


def test_timeline_names_the_decisions_daniel_listed():
    titles = " ".join(decision.title for decision in making_of.DECISIONS)
    for keyword in ("Beachvolleyball", "Demo-Modus", "Früh veröffentlichen", "Modellvergleich", "14 Uhr",
                    "WhatsApp", "Business Case", "SAP"):
        assert keyword in titles


def test_cutoff_decision_matches_the_rule_in_the_code():
    """Die Zeitleiste darf nichts behaupten, was die App nicht tut."""
    cutoff = next(decision for decision in making_of.DECISIONS if "Bestellschluss" in decision.title)
    assert f"{ORDER_CUTOFF.hour} Uhr" in cutoff.title
    assert ORDER_CUTOFF.minute == 0


def test_evaluation_story_improves_and_ends_with_the_measured_result():
    steps = making_of.EVALUATION_STEPS
    assert (steps[0].hits, steps[0].total) == (4, 7)
    assert [step.hits for step in steps] == sorted(step.hits for step in steps)
    measured = measured_ai_cost(MODEL)
    assert (steps[-1].hits, steps[-1].total) == (measured.hits, measured.total)


def test_learnings_are_three_or_four_short_points():
    assert 3 <= len(making_of.LEARNINGS) <= 4
    for title, text in making_of.LEARNINGS:
        assert title and 1 <= sentences(text) <= 2


def test_count_decisions_skips_header_and_separator_rows():
    markdown = ("| Entscheidung | Begründung | Alternative |\n|---|---|---|\n"
                "| A | weil | – |\n| B | weil | – |\n\nText | kein Tabellenanfang\n")
    assert making_of.count_decisions(markdown) == 2
    assert making_of.count_decisions(DECISIONS_FILE.read_text(encoding="utf-8")) > 100


def test_links_use_the_new_github_name_and_https():
    for url in (making_of.PORTFOLIO_URL, making_of.GITHUB_URL, making_of.DECISIONS_URL, making_of.EVALUATION_URL):
        assert url.startswith("https://") and "danielgrzegorzek" in url
