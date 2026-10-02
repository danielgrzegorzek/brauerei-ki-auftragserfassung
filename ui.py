"""Gemeinsame Oberflächen-Bausteine im eigenen Design „Papier, Tinte, Kupfer“.

Die Seiten in pages/ nutzen nur diese Funktionen. Gestaltet wird zentral: Design-Variablen in
assets/tokens.css, Regeln in assets/style.css, Grundfarben und Schriften für Streamlit in .streamlit/config.toml.

Hinweis: Eigenes HTML wird mit st.markdown(..., unsafe_allow_html=True) eingefügt. st.html filtert
<style> und <svg> heraus. Es wird nur eigenes, festes HTML eingefügt; Zahlen und Texte laufen
durch html.escape.
"""

import base64
import html
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"


def theme() -> str:
    """'light' oder 'dark' – je nach Einstellung des Betrachters."""
    return "dark" if st.context.theme.type == "dark" else "light"


def tokens() -> str:
    """Design-Variablen (hell und dunkel nebeneinander über light-dark()) als CSS-Text."""
    return (ASSETS / "tokens.css").read_text(encoding="utf-8")


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
    """Lädt Design-Variablen und Stylesheet und setzt das Logo in die Kopfleiste.
    color-scheme auf der ganzen Seite: So gelten auch in Menüs und Tooltips außerhalb der App-Fläche
    die Farben des gewählten Modus."""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    raw_html(f"<style>{tokens()}\n:root {{ color-scheme: {theme()}; }}\n{css}</style>")
    # Ohne icon_image: das ist nur für eine geschlossene Seitenleiste – wir haben die Navigation oben
    st.logo(str(ASSETS / f"logo_{theme()}.svg"), size="large")


def svg_uri(name: str) -> str:
    """SVG aus assets/ als Daten-URL. Design-Variablen und Farbmodus werden als <style> in das SVG
    selbst geschrieben – denn in ein <img> wirkt das Stylesheet der Seite nicht hinein."""
    source = (ASSETS / f"{name}.svg").read_text(encoding="utf-8")
    rules = (ASSETS / "illustrations.css").read_text(encoding="utf-8")
    end_of_tag = source.index(">", source.index("<svg")) + 1  # Ende des öffnenden <svg …>-Tags
    # CDATA: SVG ist XML – ohne CDATA würde z. B. „<img>“ in einem CSS-Kommentar als Element gelesen
    style = f"<style><![CDATA[{tokens()}\nsvg {{ color-scheme: {theme()}; }}\n{rules}]]></style>"
    themed = source[:end_of_tag] + style + source[end_of_tag:]
    return "data:image/svg+xml;base64," + base64.b64encode(themed.encode("utf-8")).decode("ascii")


def img(name: str, alt: str = "") -> str:
    return f'<img src="{svg_uri(name)}" alt="{html.escape(alt)}">'


def page_header(title: str, subtitle: str, pictogram: str) -> None:
    """Seitenkopf: Piktogramm, Titel und ein Satz – direkt auf dem Seitenhintergrund."""
    with st.container(key="page-header"):
        raw_html(
            f'<div class="page-head"><div class="page-pictogram">{img("pict_" + pictogram)}</div>'
            f"<div><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div></div>"
        )


def illustrated_message(name: str, title: str, text: str) -> None:
    """Leerzustand: Illustration, Überschrift, kurzer Hinweis."""
    raw_html(
        f'<div class="empty-state">{img(name)}'
        f'<div class="title">{html.escape(title)}</div><div class="text">{html.escape(text)}</div></div>'
    )


def image_uri(name: str) -> str:
    """SVG mit festen Farben als Daten-URL – für Bildspalten in Tabellen (Kasten- und Fass-Symbol)."""
    encoded = base64.b64encode((ASSETS / f"{name}.svg").read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"
