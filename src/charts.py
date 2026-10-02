"""Plotly-Diagramme für das Dashboard.

Gestaltungsregeln: eine Akzentfarbe (Kupfer, geprüft auf Kontrast und Farbsehschwäche),
Grau für Nebensächliches, dünne Linien (2 px), Balken mit 4 px abgerundetem Ende,
Haarlinien als Gitter, Textschrift der App und nur ausgewählte Beschriftungen direkt im Diagramm.
"""

import pandas as pd
import plotly.graph_objects as go

from src.formatting import format_number
from src.master_data import ORDER_CHANNELS

MONTH_NAMES = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
FONT = "Schibsted Grotesk, Segoe UI, sans-serif"  # Textschrift der App (config.toml)

# Farben je Hell-/Dunkelmodus im Design „Papier, Tinte, Kupfer“ (wie assets/tokens.css). Im dunklen Modus
# eigene Stufen – nicht einfach invertiert. „surface“ = Kartenhintergrund, auf dem die Diagramme stehen.
# Kategorien (Business Case): Kupfer, Blau, Hopfengrün – in dieser Reihenfolge mit dem Prüfskript validiert
# (hell und dunkel: alle Prüfungen bestanden, Farbsehschwäche ΔE ≥ 21 bei Ziel 8).
# Heatmap: Blau (unter Durchschnitt) ↔ neutrales Grau ↔ Kupfer (darüber) – kühl gegen warm.
# „muted“ = nebensächliche Linien (mindestens 3 : 1 auf der Karte), „text“ = Achsen, „ink“ = Tooltip-Text.
PALETTES = {
    "light": {"accent": "#a34a1f", "muted": "#9a9287", "text": "#6b645c", "ink": "#1c1a17",
              "grid": "#ebe6dd", "baseline": "#cfc7bb", "surface": "#fffefb",
              "low": "#2a75ba", "mid": "#efeae2", "high": "#a34a1f",
              "categories": ["#a34a1f", "#2a75ba", "#7c9128"]},
    "dark": {"accent": "#cf7743", "muted": "#6f685f", "text": "#a39c92", "ink": "#ece8e1",
             "grid": "#2b2825", "baseline": "#45403a", "surface": "#1b1a18",
             "low": "#4d97de", "mid": "#34302b", "high": "#cf7743",
             "categories": ["#cf7743", "#4d97de", "#889d37"]},
}


def relative_luminance(hex_color: str) -> float:
    """Relative Helligkeit nach WCAG 2 (0 = schwarz, 1 = weiß)."""
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(first: str, second: str) -> float:
    """Kontrastverhältnis nach WCAG, z. B. 4,5 = Mindestwert für normalen Text."""
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def label_color(fill: str) -> str:
    """Weiß oder Schwarz – je nachdem, was auf der Füllfarbe besser lesbar ist."""
    return max(("#ffffff", "#000000"), key=lambda text: contrast_ratio(text, fill))


def month_label(month: pd.Timestamp) -> str:
    """Timestamp('2026-07-01') → 'Jul 26' (deutsche Monatsnamen)."""
    return f"{MONTH_NAMES[month.month - 1]} {month.year % 100:02d}"


def apply_base_style(fig: go.Figure, colors: dict, height: int) -> go.Figure:
    """Gemeinsamer Stil für alle Diagramme."""
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        separators=",.",  # deutsches Zahlenformat: Dezimalkomma, Tausenderpunkt
        showlegend=False,
        font=dict(family=FONT, color=colors["text"]),
        # Tooltip ruhig wie eine Karte: heller Grund, Haarlinie, Text in Tinte – statt bunter Fläche
        hoverlabel=dict(align="left", bgcolor=colors["surface"], bordercolor=colors["baseline"],
                        font=dict(family=FONT, color=colors["ink"], size=13)),
        # Transparent: Das Diagramm geht nahtlos in die Karte über, auf der es steht
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False, linecolor=colors["baseline"], zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=colors["grid"], gridwidth=1, zeroline=False)
    return fig


def monthly_revenue_chart(monthly: pd.DataFrame, colors: dict) -> go.Figure:
    """Säulen: Umsatz je Monat in Tsd. €; nur der stärkste Monat ist direkt beschriftet."""
    labels = [month_label(m) for m in monthly["month"]]
    values = (monthly["revenue"] / 1000).tolist()
    hover = [f"<b>{label}</b><br>{format_number(value)} Tsd. €<br>{format_number(hl)} hl"
             for label, value, hl in zip(labels, values, monthly["hectoliters"])]
    fig = go.Figure(go.Bar(
        x=labels, y=values, hovertext=hover, hovertemplate="%{hovertext}<extra></extra>",
        marker=dict(color=colors["accent"], cornerradius=4),
    ))
    # Säulen höchstens ca. 24 px breit – der Rest der Spalte bleibt Luft
    slot_px = 1000 / max(len(labels), 1)
    fig.update_layout(bargap=max(0.2, 1 - 24 / slot_px))
    peak = values.index(max(values))
    fig.add_annotation(x=labels[peak], y=values[peak], yshift=14, showarrow=False,
                       text=f"{format_number(values[peak])} Tsd. €", font=dict(color=colors["text"]))
    fig.update_yaxes(title_text="Tsd. €", tickformat=",.0f")  # ",": Tausendertrennzeichen
    return apply_base_style(fig, colors, height=320)


def ranking_chart(labels: list[str], values: list[float], hover: list[str], colors: dict,
                  value_labels: list[str] | None = None, axis_title: str = "") -> go.Figure:
    """Waagrechte Rangfolge-Balken, größter Wert oben. value_labels = Beschriftung am Balkenende."""
    # Plotly zeichnet die erste Kategorie unten → Reihenfolge umdrehen, damit der größte Wert oben steht
    labels, values, hover = labels[::-1], values[::-1], hover[::-1]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        hovertext=hover, hovertemplate="%{hovertext}<extra></extra>",
        marker=dict(color=colors["accent"], cornerradius=4),
        text=value_labels[::-1] if value_labels else None,
        textposition="outside", cliponaxis=False, textfont=dict(color=colors["text"]),
    ))
    fig.update_layout(bargap=0.3)
    apply_base_style(fig, colors, height=32 * len(labels) + 50)
    fig.update_xaxes(showgrid=True, gridcolor=colors["grid"], title_text=axis_title, tickformat=",.0f")
    fig.update_yaxes(showgrid=False, automargin=True)
    if value_labels:
        fig.update_layout(margin=dict(r=90))  # Platz für die Beschriftung am Balkenende
    return fig


def seasonality_heatmap(index: pd.DataFrame, colors: dict) -> go.Figure:
    """Heatmap Warengruppe × Monat. Blau = unter Durchschnitt, Grau = 100, Kupfer = über Durchschnitt."""
    # Warengruppen mit der stärksten Sommerspitze nach oben
    summer_months = [m for m in (6, 7, 8) if m in index.columns]
    if summer_months:
        index = index.loc[index[summer_months].mean(axis=1).sort_values(ascending=False).index]
    spread = max(abs(index.max().max() - 100), abs(100 - index.min().min()))  # symmetrische Skala um 100
    fig = go.Figure(go.Heatmap(
        z=index.values, x=[MONTH_NAMES[m - 1] for m in index.columns], y=list(index.index),
        zmid=100, zmin=100 - spread, zmax=100 + spread,
        colorscale=[[0, colors["low"]], [0.5, colors["mid"]], [1, colors["high"]]],
        xgap=2, ygap=2,
        hovertemplate="<b>%{y}</b> · %{x}<br>Index %{z:.0f} (100 = Durchschnittsmonat)<extra></extra>",
        colorbar=dict(title=dict(text="Index"), thickness=10, outlinewidth=0),
    ))
    apply_base_style(fig, colors, height=300)
    fig.update_xaxes(showgrid=False, linecolor=colors["surface"])
    fig.update_yaxes(showgrid=False, autorange="reversed")
    return fig


def channel_chart(shares: pd.DataFrame, colors: dict) -> go.Figure:
    """Linien: Anteil der Bestellkanäle je Quartal. WhatsApp hervorgehoben, der Rest grau."""
    fig = go.Figure()
    for channel in ORDER_CHANNELS:  # WhatsApp steht zuletzt → wird obenauf gezeichnet
        part = shares[shares["channel"] == channel]
        color = colors["accent"] if channel == "WhatsApp" else colors["muted"]
        hover = [f"<b>{channel}</b> · {q}<br>{format_number(s * 100)} % der Aufträge"
                 for q, s in zip(part["quarter"], part["share"])]
        fig.add_trace(go.Scatter(
            x=part["quarter"], y=part["share"], name=channel, mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=8, color=color, line=dict(width=2, color=colors["surface"])),
            hovertext=hover, hovertemplate="%{hovertext}<extra></extra>",
        ))
    # Nur die Linie beschriften, um die es geht (Telefon und E-Mail liegen zu dicht beieinander).
    # Beschriftet wird der letzte Punkt mit Daten – Quartale ohne Aufträge haben keinen Anteil.
    whatsapp = shares[(shares["channel"] == "WhatsApp") & shares["share"].notna()]
    if not whatsapp.empty:
        last = whatsapp.iloc[-1]
        fig.add_annotation(x=last["quarter"], y=last["share"], xanchor="left", xshift=10, showarrow=False,
                           text=f"WhatsApp {format_number(last['share'] * 100)} %", font=dict(color=colors["text"]))
    apply_base_style(fig, colors, height=320)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", x=0, y=1.12), margin=dict(r=120, t=40))
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    return fig


def cost_comparison_chart(bars: list[str], segments: list[tuple[str, list[float]]], colors: dict) -> go.Figure:
    """Gestapelte waagrechte Balken, z. B. Kosten pro Jahr vorher/nachher je Kostenart.
    bars = kurze Balkennamen (oben beginnend), segments = [(Kostenart, Wert je Balken), …].
    Farbe nie allein: Summe unter dem Balkennamen, Werte im Segment (wenn Platz ist), Tabellenansicht.
    Die Legende zeichnet die Seite als HTML darüber (ui.chart_legend) – sie bricht auf dem Handy sauber um."""
    totals = [sum(values[i] for _, values in segments) for i in range(len(bars))]
    labels = [f"<b>{bar}</b><br>{format_number(total)} €" for bar, total in zip(bars, totals)]
    fig = go.Figure()
    for (name, values), color in zip(segments, colors["categories"]):
        fig.add_trace(go.Bar(
            y=labels[::-1], x=values[::-1], name=name, orientation="h", customdata=bars[::-1],
            marker=dict(color=color, line=dict(color=colors["surface"], width=2)),  # 2-px-Lücke zwischen Segmenten
            text=[f"{format_number(value)} €" for value in values[::-1]],
            textposition="inside", insidetextanchor="middle", textfont=dict(color=label_color(color)),
            textangle=0,  # nie senkrecht – passt die Zahl nicht, wird sie ausgeblendet (Tooltip und Tabelle bleiben)
            # Tooltip in Python formatiert – gleiche Rundung wie Beschriftung und Rechenweg
            hovertext=[f"{name}: {format_number(value)} €" for value in values[::-1]],
            hovertemplate="<b>%{customdata}</b><br>%{hovertext}<extra></extra>",
        ))
    apply_base_style(fig, colors, height=80 * len(bars) + 60)
    fig.update_layout(barmode="stack", bargap=0.35, barcornerradius=4,
                      uniformtext=dict(minsize=11, mode="hide"))  # zu kleine Segmente ohne Zahl
    fig.update_xaxes(showgrid=True, gridcolor=colors["grid"], tickformat=",.0f", ticksuffix=" €",
                     rangemode="tozero", nticks=5)
    fig.update_yaxes(showgrid=False, automargin=True)
    return fig
