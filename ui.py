"""Gemeinsame Oberflächen-Bausteine, angelehnt an die SAP-Fiori-Designrichtlinien (Theme „Horizon“).

Die Seiten in pages/ nutzen nur diese Funktionen; das CSS steht gesammelt in assets/style.css.
Eigene Farben, eigenes Logo – kein SAP-Logo, keine SAP-Schrift.

Hinweis: Eigenes HTML wird mit st.markdown(..., unsafe_allow_html=True) eingefügt. st.html filtert
<style> und <svg> heraus. Es wird nur eigenes, festes HTML eingefügt; Zahlen und Texte laufen
durch html.escape.
"""

import base64
import html
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"

# CSS-Variablen je Modus. Die Grundfarben stehen auch in .streamlit/config.toml.
COLORS = {
    "light": {
        "--fiori-card": "#ffffff",
        "--fiori-card-border": "transparent",
        "--fiori-border": "#d9d9d9",
        "--fiori-text": "#1d2d3e",
        "--fiori-label": "#556b82",
        "--fiori-accent": "#0070f2",
        "--fiori-accent-soft": "#e5f2ff",
        "--fiori-shadow": "0 0 0.125rem rgba(34, 53, 72, 0.15), 0 0.125rem 0.5rem rgba(34, 53, 72, 0.10)",
        "--fiori-shadow-hover": "0 0.25rem 1rem rgba(34, 53, 72, 0.22)",
        "--ill-line": "#a9b4be", "--ill-foam": "#ffffff",   # Leerzustands-Illustration
        # Messenger-Ansicht (angelehnt an gängige Chat-Apps, ohne fremde Marken)
        "--chat-bg": "#efeae2", "--chat-in": "#ffffff", "--chat-out": "#d9fdd3", "--chat-text": "#111b21",
        "--chat-meta": "#5b6b75", "--chat-ticks": "#0070f2", "--chat-notice-bg": "#fff5c4",
        "--chat-notice-text": "#4a5a64", "--chat-header-bg": "#0070f2", "--chat-header-text": "#ffffff",
        "--phone-frame": "#1d2d3e",
        # Fortschritt „Auftrag entsteht“ – Zustand immer auch über Symbol und Text erkennbar
        "--step-ok": "#256f3a", "--step-warn": "#b44f00", "--step-error": "#aa0808",
    },
    "dark": {
        "--fiori-card": "#1d232a",
        "--fiori-card-border": "#2c3440",
        "--fiori-border": "#2c3440",
        "--fiori-text": "#eaecee",
        "--fiori-label": "#a9b4be",
        "--fiori-accent": "#1b90ff",
        "--fiori-accent-soft": "#1c2b3b",
        "--fiori-shadow": "none",
        "--fiori-shadow-hover": "0 0 0 1px #3a4552, 0 0.25rem 1rem rgba(0, 0, 0, 0.4)",
        "--ill-line": "#5b738b", "--ill-foam": "#eaecee",
        "--chat-bg": "#0b141a", "--chat-in": "#202c33", "--chat-out": "#005c4b", "--chat-text": "#e9edef",
        "--chat-meta": "#a3b1ba", "--chat-ticks": "#53bdeb", "--chat-notice-bg": "#182229",
        "--chat-notice-text": "#ffd279", "--chat-header-bg": "#1d232a", "--chat-header-text": "#eaecee",
        "--phone-frame": "#3a4552",
        "--step-ok": "#6dd58c", "--step-warn": "#ffab6e", "--step-error": "#ff8888",
    },
}


def theme() -> str:
    """'light' oder 'dark' – je nach Einstellung des Betrachters."""
    return "dark" if st.context.theme.type == "dark" else "light"


def variables() -> str:
    """Farbvariablen des aktuellen Modus als CSS-Text: '--fiori-card: #fff; …'"""
    return "; ".join(f"{name}: {value}" for name, value in COLORS[theme()].items())


def raw_html(markup: str) -> None:
    """Fügt eigenes HTML ein (siehe Hinweis oben)."""
    st.markdown(markup, unsafe_allow_html=True)


def chart_legend(items: list[tuple[str, str]]) -> None:
    """Legende als HTML über einem Diagramm: [(Bezeichnung, Farbe), …] – bricht auf schmalen Bildschirmen um."""
    entries = "".join(f'<span class="chart-legend-item" role="listitem"><span class="chart-legend-swatch" '
                      f'style="background:{html.escape(color)}"></span>{html.escape(label)}</span>'
                      for label, color in items)
    raw_html(f'<div class="chart-legend" role="list">{entries}</div>')


def apply_style() -> None:
    """Lädt das Stylesheet mit den Farben des aktuellen Modus und setzt das Logo in die Kopfleiste."""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    raw_html(f"<style>:root {{ {variables()} }}\n{css}</style>")
    # Ohne icon_image: das ist nur für eine geschlossene Seitenleiste – wir haben die Navigation oben
    st.logo(str(ASSETS / f"logo_{theme()}.svg"), size="large")


def svg_uri(name: str) -> str:
    """SVG aus assets/ als Daten-URL. Die Farben des aktuellen Modus werden als <style> in das SVG
    selbst geschrieben – denn in ein <img> wirkt das Stylesheet der Seite nicht hinein."""
    source = (ASSETS / f"{name}.svg").read_text(encoding="utf-8")
    rules = (ASSETS / "illustrations.css").read_text(encoding="utf-8")
    end_of_tag = source.index(">", source.index("<svg")) + 1  # Ende des öffnenden <svg …>-Tags
    # CDATA: SVG ist XML – ohne CDATA würde z. B. „<img>“ in einem CSS-Kommentar als Element gelesen
    style = f"<style><![CDATA[svg {{ {variables()} }}\n{rules}]]></style>"
    themed = source[:end_of_tag] + style + source[end_of_tag:]
    return "data:image/svg+xml;base64," + base64.b64encode(themed.encode("utf-8")).decode("ascii")


def img(name: str, alt: str = "") -> str:
    return f'<img src="{svg_uri(name)}" alt="{html.escape(alt)}">'


def page_header(title: str, subtitle: str, pictogram: str) -> None:
    """Seitenkopf: Piktogramm, Titel und ein Satz – direkt auf dem Seitenhintergrund."""
    with st.container(key="page-header"):
        raw_html(
            f'<div class="fiori-page-header"><div class="fiori-pictogram">{img("pict_" + pictogram)}</div>'
            f"<div><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div></div>"
        )


def illustrated_message(name: str, title: str, text: str) -> None:
    """Leerzustand wie die Fiori-„Illustrated Message“: Illustration, Überschrift, kurzer Hinweis."""
    raw_html(
        f'<div class="fiori-illustrated-message">{img(name)}'
        f'<div class="title">{html.escape(title)}</div><div class="text">{html.escape(text)}</div></div>'
    )


def image_uri(name: str) -> str:
    """SVG mit festen Farben als Daten-URL – für Bildspalten in Tabellen (Kasten- und Fass-Symbol)."""
    encoded = base64.b64encode((ASSETS / f"{name}.svg").read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"
