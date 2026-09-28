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
        "--ill-sky": "#e5f2ff", "--ill-sun": "#ffc933", "--ill-cloud": "#ffffff",
        "--ill-hill-far": "#bfe3c9", "--ill-hill": "#86cb9c", "--ill-pole": "#8a6a4f", "--ill-hop": "#3f9a5b",
        "--ill-wall": "#fdfaf5", "--ill-wall-2": "#f1ebe1", "--ill-roof": "#c65a35", "--ill-chimney": "#9aa8b5",
        "--ill-window": "#5b738b", "--ill-door": "#8a5a36", "--ill-crate-dark": "#0057c2",
        "--ill-keg": "#c5ccd3", "--ill-keg-ring": "#8696a9", "--ill-line": "#a9b4be", "--ill-foam": "#ffffff",
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
        "--ill-sky": "#1c2b3b", "--ill-sun": "#ffc933", "--ill-cloud": "#2b3d52",
        "--ill-hill-far": "#2e4b3b", "--ill-hill": "#3b6a4e", "--ill-pole": "#a98b6f", "--ill-hop": "#5fbf7a",
        "--ill-wall": "#d8d2c7", "--ill-wall-2": "#c7c0b3", "--ill-roof": "#b0502f", "--ill-chimney": "#6f7f8f",
        "--ill-window": "#34495e", "--ill-door": "#6e4a2f", "--ill-crate-dark": "#0f6fd0",
        "--ill-keg": "#9aa8b5", "--ill-keg-ring": "#5b738b", "--ill-line": "#5b738b", "--ill-foam": "#eaecee",
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


def illustration(name: str, alt: str) -> None:
    raw_html(f'<div class="fiori-illustration">{img(name, alt)}</div>')


def page_header(title: str, subtitle: str, pictogram: str) -> None:
    """Seitenkopf wie die Fiori-„Object Page“: Piktogramm, Titel, Untertitel auf einer Karte."""
    with st.container(key="page-header"):
        raw_html(
            f'<div class="fiori-page-header"><div class="fiori-pictogram">{img("pict_" + pictogram)}</div>'
            f"<div><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div></div>"
        )


def tile(key: str, title: str, subtitle: str, pictogram: str,
         value: str | None = None, unit: str = "", page: str | None = None) -> None:
    """Launchpad-Kachel: Titel, Untertitel, Piktogramm und Kennzahl. Mit page ist die ganze Kachel ein Link."""
    value_html = f'<span class="value">{html.escape(value)}</span>' if value else ""
    with st.container(key=f"tile-{key}"):
        raw_html(
            f'<div class="fiori-tile-title">{html.escape(title)}</div>'
            f'<div class="fiori-tile-subtitle">{html.escape(subtitle)}</div>'
            f'<div class="fiori-tile-footer">{img("pict_" + pictogram)}'
            f'<div class="fiori-tile-kpi">{value_html}<span class="unit">{html.escape(unit)}</span></div></div>'
        )
        if page:
            st.page_link(page, label="Öffnen", icon=":material/arrow_forward:")


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
