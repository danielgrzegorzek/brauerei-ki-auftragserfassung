"""Tests für Ist- und Soll-Prozess: Kennzahlen und Übereinstimmung mit dem Business Case."""

import pytest

from src.business_case import DEFAULT_CHANNELS, DEFAULTS
from src.process import AS_IS, CUSTOMER, LANES, MANUAL, TO_BE, figures


def test_figures_as_is_and_to_be():
    before, after = figures(AS_IS), figures(TO_BE)
    assert (before.manual_steps, after.manual_steps) == (6, 1)
    assert (before.media_breaks, after.media_breaks) == (2, 0)


def test_minutes_match_the_business_case():
    """Prozessseite und Business Case müssen dieselbe Geschichte erzählen."""
    assert figures(AS_IS).minutes == DEFAULTS["minutes_manual"]
    assert figures(TO_BE).minutes == DEFAULTS["minutes_ai"]


def test_to_be_covers_the_same_channels_as_the_business_case():
    """Anrufe rechnet der Business Case getrennt (dort schreibt weiterhin jemand mit) – der Soll-Prozess
    darf deshalb nur die Kanäle nennen, für die 2 Minuten gelten."""
    order_step = next(step for step in TO_BE if step.kind == CUSTOMER)
    assert all(channel in order_step.title for channel in DEFAULT_CHANNELS)
    assert "Anruf" not in order_step.title and "Telefon" not in order_step.title


@pytest.mark.parametrize("steps", [AS_IS, TO_BE], ids=["Ist", "Soll"])
def test_every_step_has_a_valid_lane_and_a_note(steps):
    assert all(step.lane in LANES and step.note for step in steps)
    assert all(step.minutes == 0 or step.kind == MANUAL for step in steps)  # nur manuelle Schritte kosten Zeit


def test_to_be_keeps_a_human_decision_before_sap():
    lanes = [step.lane for step in TO_BE]
    assert lanes.index("Innendienst") < lanes.index("SAP S/4HANA")
