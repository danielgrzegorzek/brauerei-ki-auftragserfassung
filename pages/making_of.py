"""Making-of: Demo-Video, meine Rolle in zwei Sätzen, meine Entscheidungen als Zeitleiste, Links zu Portfolio und Code.

Die Inhalte stehen getestet in src/making_of.py – hier nur die Anzeige. Eigenes HTML nur mit festen Texten,
trotzdem durch html.escape.
"""

import html

import streamlit as st

import ui
from src import making_of

# Demo-Video: die veröffentlichte Datei der Portfolio-Seite – so liegt es nicht noch einmal in diesem Repository
DEMO_VIDEO = f"{making_of.PORTFOLIO_URL}/assets/demo.mp4"
DEMO_POSTER = f"{making_of.PORTFOLIO_URL}/assets/demo-poster.jpg"


def demo_video() -> str:
    """Stummes Demo-Video, das von selbst in Schleife läuft – mit Steuerleiste zum Anhalten und für Vollbild."""
    return (f'<video class="making-of-video" src="{DEMO_VIDEO}" poster="{DEMO_POSTER}" autoplay muted loop '
            'playsinline controls preload="metadata" aria-label="Demo-Video, 45 Sekunden, ohne Ton: Bestellung im '
            'Dialekt, geprüfter Auftrag, Kundenauftrag für SAP S/4HANA, Business Case, Making-of"></video>')


def timeline() -> str:
    """Senkrechte Zeitleiste, eine Zeile je Entscheidung: Phase als Etikett, daneben der Titel."""
    entries = "".join(
        f'<li><span class="making-of-phase">{html.escape(decision.phase)}</span>'
        f"<strong>{html.escape(decision.title)}</strong></li>"
        for decision in making_of.DECISIONS
    )
    return f'<ol class="making-of-timeline">{entries}</ol>'


# ================= Seitenaufbau =================

ui.page_header("Making-of", "Wie diese App entstanden ist und welche Entscheidungen dahinterstehen.", "making_of")

with st.container(key="card-making-of-role"):
    text, video = st.columns(2, gap="large", vertical_alignment="center")  # auf dem Handy untereinander
    with text:
        st.subheader("Meine Rolle", anchor=False)
        st.markdown(making_of.ROLE_INTRO)
        with st.container(horizontal=True):
            st.link_button("Zu meinem Portfolio", making_of.PORTFOLIO_URL, type="primary", icon=":material/person:")
            st.link_button("Code auf GitHub", making_of.GITHUB_URL, icon=":material/code:")
            st.link_button("Alle Entscheidungen", making_of.DECISIONS_URL, icon=":material/checklist:")
            st.link_button("Evaluationsbericht", making_of.EVALUATION_URL, icon=":material/fact_check:")
    with video:
        ui.raw_html(demo_video())

with st.container(key="card-making-of-decisions"):
    st.subheader("Meine Entscheidungen", anchor=False)
    ui.raw_html(timeline())
