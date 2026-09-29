"""Startseite im Stil des Fiori-Launchpads: worum es geht, Tour-Knopf und Kacheln mit je einer fachlichen Kennzahl."""

import html
from contextlib import closing
from datetime import timedelta

import streamlit as st

import ui
import ui_tour
from src import analytics, process
from src.analytics import Filters
from src.business_case import default_result
from src.database import get_connection
from src.demo_messages import DEMO_MESSAGES
from src.extraction import MODEL
from src.formatting import format_number
from src.master_data import CUSTOMER_GROUPS


@st.cache_data(show_spinner=False)
def load_figures() -> dict:
    """Kennzahlen der Kacheln (zwischengespeichert, nach neuen Aufträgen geleert) – nur einfache Zahlen im Cache."""
    # closing(...) schließt die Verbindung am Ende des with-Blocks automatisch
    with closing(get_connection()) as conn:
        _, last = analytics.history_period(conn)  # nur die Historie – Demo-Aufträge verschieben nichts
        # Umsatz der letzten 12 Monate – dieselbe Berechnung wie im Dashboard
        last_12 = Filters(analytics.shift_year(last, -1) + timedelta(days=1), last, CUSTOMER_GROUPS)
        _, business_case = default_result(conn, MODEL)
        return {"revenue_12m": analytics.kpis(conn, last_12)["revenue"], "saved_eur": business_case.saved_eur}


def tile(page: str, title: str, pictogram: str, value: str = "", unit: str = "") -> None:
    """Launchpad-Kachel: Titel, Symbol und höchstens eine Kennzahl. Der Titel ist der Link –
    das CSS spannt ihn über die ganze Kachel, so ist sie überall klickbar."""
    with st.container(key=f"tile-{pictogram}"):
        st.page_link(page, label=title)
        kpi = (f'<div class="tile-kpi"><span class="tile-value">{html.escape(value)}</span>'
               f'<span class="tile-unit">{html.escape(unit)}</span></div>') if value else ""
        ui.raw_html(f'<div class="tile-content">{ui.img("pict_" + pictogram)}{kpi}</div>')


with st.container(key="home-hero"):
    st.title("Vom WhatsApp-Chaos zum sauberen Auftrag", anchor=False)
    st.markdown("Eine KI macht aus Bestellungen per WhatsApp, E-Mail und Telefon in Sekunden einen geprüften "
                "Auftrag – der Mensch bestätigt.")
    st.button("In 60 Sekunden durch die App", type="primary", icon=":material/play_circle:",
              on_click=ui_tour.start, key="tour_start")

with st.skeleton(height=190):  # Platzhalter statt leerer Fläche, falls die Zahlen beim ersten Aufruf dauern
    figures = load_figures()

before, after = process.figures(process.AS_IS), process.figures(process.TO_BE)
with st.container(key="launchpad", horizontal=True):
    # \u00ad = weiches Trennzeichen: Wird die Kachel zu schmal, trennt der Browser dort („Auftrags-erfassung“)
    tile("pages/order_entry.py", "KI-Auftrags\u00aderfassung", "message",
         str(len(DEMO_MESSAGES)), "Nachrichten im Posteingang")
    tile("pages/dashboard.py", "Vertriebs-Dashboard", "chart",
         format_number(figures["revenue_12m"] / 1_000_000, 2), "Mio. € Umsatz, letzte 12 Monate")
    tile("pages/process.py", "Prozess & SAP-Übergabe", "process",
         f"{before.manual_steps} → {after.manual_steps}", "manuelle Schritte je Auftrag")
    tile("pages/business_case.py", "Business Case", "savings",
         format_number(figures["saved_eur"] / 1000, 1), "Tsd. € Ersparnis pro Jahr")
    tile("pages/making_of.py", "Making-of", "making_of")
