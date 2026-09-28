"""Plotly-Diagramme für das Dashboard.

Gestaltungsregeln: eine Akzentfarbe (Blau, geprüft auf Kontrast und Farbsehschwäche),
Grau für Nebensächliches, dünne Linien (2 px), Balken mit 4 px abgerundetem Ende,
dezente Gitterlinien und nur ausgewählte Beschriftungen direkt im Diagramm.
"""

import pandas as pd
import plotly.graph_objects as go

from src.formatting import format_number
from src.master_data import ORDER_CHANNELS

MONTH_NAMES = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

# Farben je Hell-/Dunkelmodus. Im dunklen Modus eigene, hellere Stufen – nicht einfach invertiert.
PALETTES = {
    "light": {"accent": "#2a78d6", "muted": "#b4b2a9", "text": "#52514e", "grid": "#e1e0d9",
              "surface": "#ffffff", "low": "#256abf", "mid": "#f0efec", "high": "#e34948"},
    "dark": {"accent": "#3987e5", "muted": "#5f5e5a", "text": "#c3c2b7", "grid": "#2c2c2a",
             "surface": "#0e1117", "low": "#3987e5", "mid": "#383835", "high": "#e66767"},
}


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
        font=dict(color=colors["text"]),
        hoverlabel=dict(align="left"),
    )
    fig.update_xaxes(showgrid=False, linecolor=colors["grid"], zeroline=False)
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
    """Heatmap Warengruppe × Monat. Blau = unter Durchschnitt, Grau = 100, Rot = über Durchschnitt."""
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
