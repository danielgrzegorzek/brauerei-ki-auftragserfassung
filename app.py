"""Einstiegspunkt der App: Seiteneinstellungen, Datenbank sicherstellen, Navigation.

app.py ist der „Rahmen“: Er läuft bei jedem Seitenaufruf und zeigt dann die gewählte Seite.
Start (PowerShell):  .venv\\Scripts\\python.exe -m streamlit run app.py
"""

import streamlit as st

import ui
from src.data_setup import ensure_database

# Muss der erste Streamlit-Befehl sein: Titel im Browser-Tab, Symbol, breites Layout
st.set_page_config(page_title="Bräu am Stein", page_icon="🍺", layout="wide")


@st.cache_resource(show_spinner="Datenbank wird beim ersten Start erzeugt …")
def init_database() -> None:
    """Stellt sicher, dass die Datenbank existiert – läuft nur einmal pro Serverprozess."""
    ensure_database()


init_database()
ui.apply_style()  # Fiori-inspirierte Gestaltung und Logo – gilt für alle Seiten

pages = [
    st.Page("pages/home.py", title="Start", icon=":material/home:", default=True),
    st.Page("pages/dashboard.py", title="Dashboard", icon=":material/bar_chart:"),
    st.Page("pages/order_entry.py", title="KI-Auftragserfassung", icon=":material/smart_toy:"),
]
st.navigation(pages, position="top").run()
