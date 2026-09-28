"""Tests für Diagramme, die Werte selbst berechnen – hier der Kostenvergleich des Business Case."""

from src.charts import PALETTES, cost_comparison_chart


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
