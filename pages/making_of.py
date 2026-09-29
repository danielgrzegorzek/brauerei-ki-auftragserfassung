"""Making-of: meine Rolle in zwei Sätzen, meine Entscheidungen als Zeitleiste, Links zu Portfolio und Code.

Die Inhalte stehen getestet in src/making_of.py – hier nur die Anzeige. Eigenes HTML nur mit festen Texten,
trotzdem durch html.escape.
"""

import html

import streamlit as st

import ui
from src import making_of


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
    st.subheader("Meine Rolle", anchor=False)
    st.markdown(making_of.ROLE_INTRO)
    with st.container(horizontal=True):
        st.link_button("Zu meinem Portfolio", making_of.PORTFOLIO_URL, type="primary", icon=":material/person:")
        st.link_button("Code auf GitHub", making_of.GITHUB_URL, icon=":material/code:")
        st.link_button("Alle Entscheidungen", making_of.DECISIONS_URL, icon=":material/checklist:")
        st.link_button("Evaluationsbericht", making_of.EVALUATION_URL, icon=":material/fact_check:")

with st.container(key="card-making-of-decisions"):
    st.subheader("Meine Entscheidungen", anchor=False)
    ui.raw_html(timeline())
