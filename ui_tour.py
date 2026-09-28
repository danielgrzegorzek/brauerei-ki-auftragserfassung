"""Geführte Tour: ein Band oben auf jeder Seite – Schritt, kurzer Text, Zurück / Weiter / Beenden.

Der Inhalt steht in src/tour.py; hier nur Anzeige und Seitenwechsel. app.py ruft show() vor jeder Seite auf,
gestartet wird die Tour mit dem Knopf auf der Startseite (start()).
"""

from contextlib import closing

import streamlit as st

import ui
from src.business_case import default_result, orders_last_12_months
from src.database import get_connection
from src.extraction import MODEL
from src.tour import TourStep, tour_steps


@st.cache_data(show_spinner=False)
def load_steps() -> list[TourStep]:
    """Die Schritte mit Zahlen aus den Daten – dieselben wie auf Startseite und Business-Case-Seite."""
    with closing(get_connection()) as conn:
        _, result = default_result(conn, MODEL)
        all_orders = sum(orders_last_12_months(conn).values())
    return tour_steps(all_orders, result.saved_hours, result.saved_eur)


def start() -> None:
    st.session_state.tour_step = 0


def go(index: int, current, pages: dict, steps: list[TourStep]) -> None:
    """Zu Schritt index – auf dessen Seite wechseln, falls nötig."""
    st.session_state.tour_step = index
    target = pages[steps[index].page]
    if target.url_path != current.url_path:
        st.switch_page(target)
    st.rerun()


def show(current, pages: dict) -> None:
    """Zeigt das Tour-Band, solange die Tour läuft. current = aktuelle Seite, pages = {Schlüssel: st.Page}."""
    index = st.session_state.get("tour_step")
    if index is None:
        return
    steps = load_steps()
    step, last = steps[index], index == len(steps) - 1
    target = pages[step.page]
    with st.container(key="tour-panel"):
        dots = "".join(f'<span class="tour-dot{" active" if i == index else ""}"></span>' for i in range(len(steps)))
        ui.raw_html(f'<div class="tour-head"><span class="tour-count">Tour · Schritt {index + 1} von {len(steps)}'
                    f'</span><span class="tour-dots" aria-hidden="true">{dots}</span></div>')
        st.markdown(f"**{step.title}** – {step.text}")
        if target.url_path != current.url_path:  # jemand hat zwischendurch selbst navigiert
            st.page_link(target, label="Zu diesem Schritt springen", icon=":material/arrow_forward:")
        with st.container(horizontal=True, key="tour-buttons"):
            back = st.button("Zurück", icon=":material/arrow_back:", disabled=index == 0, key="tour_back")
            forward = st.button("Tour abschließen" if last else "Weiter", type="primary", key="tour_next",
                                icon=":material/check:" if last else ":material/arrow_forward:")
            end = st.button("Tour beenden", type="tertiary", icon=":material/close:", key="tour_end")
    if end or (forward and last):
        st.session_state.tour_step = None
        if forward:
            st.toast("Danke fürs Mitkommen – probieren Sie jetzt selbst weiter!", icon=":material/celebration:")
        st.rerun()
    if back or forward:
        go(index - 1 if back else index + 1, current, pages, steps)
