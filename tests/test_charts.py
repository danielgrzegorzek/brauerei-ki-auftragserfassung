"""Tests für Diagramme, die Werte selbst berechnen – hier der Kostenvergleich des Business Case."""

from src.charts import PALETTES, contrast_ratio, cost_comparison_chart, label_color


def test_cost_comparison_stacks_segments_and_labels_totals():
    fig = cost_comparison_chart(["Vorher", "Mit KI"], [("Arbeitszeit", [1000.0, 400.0]),
                                                       ("Fehlerkosten", [300.0, 150.0]),
                                                       ("KI & Betrieb", [0.0, 250.0])], PALETTES["light"])
    assert fig.layout.barmode == "stack" and len(fig.data) == 3
    # Plotly zeichnet von unten → umgedreht; die Summe steht unter dem Balkennamen
    assert list(fig.data[0].y) == ["<b>Mit KI</b><br>800 €", "<b>Vorher</b><br>1.300 €"]
    assert all(trace.textangle == 0 for trace in fig.data)       # Zahlen nie senkrecht


def test_every_mode_has_three_category_colors():
    assert all(len(palette["categories"]) == 3 for palette in PALETTES.values())


def test_segment_labels_are_readable_on_every_category_color():
    """Text im Segment braucht mindestens 4,5:1 Kontrast (WCAG AA für normalen Text)."""
    for palette in PALETTES.values():
        for fill in palette["categories"]:
            assert contrast_ratio(label_color(fill), fill) >= 4.5


def test_contrast_ratio_extremes():
    assert round(contrast_ratio("#ffffff", "#000000"), 1) == 21.0
    assert contrast_ratio("#777777", "#777777") == 1
