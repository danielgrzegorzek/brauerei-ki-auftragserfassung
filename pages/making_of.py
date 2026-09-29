"""Making-of: warum es dieses Projekt gibt, wer was gemacht hat, Entscheidungen, Evaluation, Gelerntes.

Die Inhalte stehen getestet in src/making_of.py – hier nur die Anzeige. Eigenes HTML nur mit festen Texten,
trotzdem durch html.escape.
"""

import html
from pathlib import Path

import streamlit as st

import ui
from src import making_of
from src.formatting import format_date, format_number

DECISIONS_FILE = Path(__file__).parent.parent / "docs" / "ENTSCHEIDUNGEN.md"


def bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def timeline() -> str:
    """Senkrechte Zeitleiste: Phase als Etikett, Titel, ein bis zwei Sätze."""
    entries = "".join(
        f'<li><span class="making-of-phase">{html.escape(decision.phase)}</span>'
        f"<strong>{html.escape(decision.title)}</strong><p>{html.escape(decision.text)}</p></li>"
        for decision in making_of.DECISIONS
    )
    return f'<ol class="making-of-timeline">{entries}</ol>'


def evaluation_steps() -> str:
    """Die Messläufe nebeneinander (auf dem Handy untereinander): Ergebnis, Befund, Änderung."""
    steps = "".join(
        f'<div class="making-of-run{" done" if step.hits == step.total else ""}">'
        f'<span class="making-of-run-label">{html.escape(step.run)}</span>'
        f'<span class="making-of-run-score">{step.hits} / {step.total}</span>'
        f"<p><strong>Gefunden:</strong> {html.escape(step.found)}</p>"
        f"<p><strong>Geändert:</strong> {html.escape(step.fix)}</p></div>"
        for step in making_of.EVALUATION_STEPS
    )
    return f'<div class="making-of-runs" role="list">{steps}</div>'


# ================= Seitenaufbau =================

ui.page_header("Making-of", f"Wie diese App entstanden ist – ein Portfolio-Projekt von {making_of.AUTHOR}.",
               "making_of")

# 1. Warum dieses Projekt
with st.container(key="card-making-of-why"):
    st.subheader("Warum dieses Projekt")
    st.markdown(making_of.WHY)
    for column, (title, text, pictogram) in zip(st.columns(3), making_of.BRIDGE):
        with column:
            ui.raw_html(f'<div class="making-of-bridge">{ui.img("pict_" + pictogram)}'
                        f"<div><strong>{html.escape(title)}</strong><p>{html.escape(text)}</p></div></div>")

# 2. Meine Rolle – ehrlich
with st.container(key="card-making-of-role"):
    st.subheader("Meine Rolle")
    st.markdown(making_of.ROLE_INTRO)
    mine, claude = st.columns(2, gap="large")
    with mine:
        st.markdown("##### :material/person: Das habe ich gemacht")
        st.markdown(bullet_list(making_of.MY_PART))
    with claude:
        st.markdown("##### :material/smart_toy: Das hat Claude Code gemacht")
        st.markdown(bullet_list(making_of.CLAUDE_PART))

# 3. Meine Entscheidungen als Zeitleiste
with st.container(key="card-making-of-decisions"):
    st.subheader("Meine Entscheidungen")
    st.caption("Eine Auswahl – alle Designentscheidungen mit Begründung und Alternative stehen im Repository.")
    ui.raw_html(timeline())

# 4. Highlight: Evaluation 4/7 → 7/7
with st.container(key="card-making-of-evaluation"):
    st.subheader("Messen statt glauben: von 4 auf 7 von 7")
    st.markdown("Ein Skript schickt die sieben Beispielnachrichten live an die KI und vergleicht das Ergebnis mit "
                "dem geprüften Soll: gleicher Kunde, gleicher Liefertermin, gleiche Artikel und Mengen.")
    ui.raw_html(evaluation_steps())
    st.markdown(f"**{making_of.EVALUATION_LESSON}**")
    st.page_link(making_of.EVALUATION_URL, label="Evaluationsbericht auf GitHub", icon=":material/open_in_new:")

# 5. Was ich gelernt habe
with st.container(key="card-making-of-learnings"):
    st.subheader("Was ich gelernt habe")
    for row in (making_of.LEARNINGS[:2], making_of.LEARNINGS[2:]):
        for column, (title, text) in zip(st.columns(2, gap="large"), row):
            column.markdown(f"**{title}**  \n{text}")

# 6. Kennzahlen des Projekts
st.subheader("Das Projekt in Zahlen")
decisions = making_of.count_decisions(DECISIONS_FILE.read_text(encoding="utf-8"))
figures = st.columns(4)
figures[0].metric("Automatische Tests", format_number(making_of.TESTS), border=True,
                  help="pytest – KI-Aufrufe nur mit Schein-Client, ohne Kosten.")
figures[1].metric("Commits", format_number(making_of.COMMITS), border=True,
                  help="Ein Commit pro Arbeitsschritt – jede Änderung einzeln nachvollziehbar.")
figures[2].metric("Dokumentierte Entscheidungen", format_number(decisions), border=True,
                  help="Jede mit Begründung und verworfener Alternative (docs/ENTSCHEIDUNGEN.md).")
figures[3].metric("Phasen abgeschlossen", making_of.PHASES_DONE, border=True,
                  help="Von Setup und Datenbasis bis zur SAP-Übergabe. Offen: Regel-Parser als Vergleich, "
                       "Demo-Video.")
st.caption(f"Tests und Commits: Stand {format_date(making_of.FIGURES_AS_OF)}.")

# 7. Weiter
with st.container(key="card-making-of-links"):
    st.subheader("Mehr über mich und den Code")
    with st.container(horizontal=True):
        st.link_button("Zu meinem Portfolio", making_of.PORTFOLIO_URL, type="primary", icon=":material/person:")
        st.link_button("Code auf GitHub", making_of.GITHUB_URL, icon=":material/code:")
        st.link_button("Alle Entscheidungen", making_of.DECISIONS_URL, icon=":material/checklist:")
