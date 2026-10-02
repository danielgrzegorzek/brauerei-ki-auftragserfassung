"""Tests für das Design: Dieselben Farben stehen an drei Stellen – sie müssen übereinstimmen und lesbar sein.

- assets/tokens.css: Design-Variablen für das eigene CSS (hell und dunkel über light-dark())
- .streamlit/config.toml: Theme für Streamlit selbst (Knöpfe, Eingabefelder, Tabellen)
- src/charts.py: Farben der Plotly-Diagramme
"""

import re
import tomllib
from pathlib import Path

import pytest

from src.charts import PALETTES, contrast_ratio

ROOT = Path(__file__).parent.parent
TOKENS = (ROOT / "assets" / "tokens.css").read_text(encoding="utf-8")
THEME = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))["theme"]


def token(name: str) -> dict[str, str]:
    """'--accent' → {'light': '#a34a1f', 'dark': '#cf7743'} aus „--accent: light-dark(#…, #…);“"""
    match = re.search(rf"{name}:\s*light-dark\((#[0-9a-f]{{6}}),\s*(#[0-9a-f]{{6}})\)", TOKENS)
    assert match, f"{name} fehlt in tokens.css"
    return {"light": match.group(1), "dark": match.group(2)}


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_css_streamlit_and_charts_use_the_same_colors(mode):
    theme = THEME[mode]
    assert token("--accent")[mode] == theme["primaryColor"] == PALETTES[mode]["accent"]
    assert token("--paper")[mode] == theme["backgroundColor"]
    assert token("--surface")[mode] == theme["secondaryBackgroundColor"] == PALETTES[mode]["surface"]
    assert token("--ink")[mode] == theme["textColor"] == PALETTES[mode]["ink"]
    assert token("--muted")[mode] == PALETTES[mode]["text"]
    assert theme["chartCategoricalColors"] == PALETTES[mode]["categories"]


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_text_colors_meet_wcag_aa(mode):
    """Text mindestens 4,5 : 1 auf Papier und auf Karten (WCAG AA)."""
    for background in (token("--paper")[mode], token("--surface")[mode]):
        for text in ("--ink", "--muted", "--accent"):
            assert contrast_ratio(token(text)[mode], background) >= 4.5, (text, background)
    # Schrift auf dem Kupfer-Knopf
    assert contrast_ratio(token("--on-accent")[mode], token("--accent")[mode]) >= 4.5


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_input_borders_are_visible(mode):
    """Rand von Eingabefeldern und Schalter „aus“: mindestens 3 : 1 zur Karte (WCAG, Bedienelemente)."""
    assert contrast_ratio(token("--line-input")[mode], token("--surface")[mode]) >= 3


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_chart_marks_stand_out_from_the_card(mode):
    """Datenfarben und nebensächliche Linien mindestens 3 : 1 zum Kartenhintergrund."""
    palette = PALETTES[mode]
    for color in palette["categories"] + [palette["accent"], palette["muted"], palette["low"], palette["high"]]:
        assert contrast_ratio(color, palette["surface"]) >= 3, color
