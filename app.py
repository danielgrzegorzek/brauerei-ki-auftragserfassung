"""Einstiegspunkt der App: Seiteneinstellungen, Datenbank sicherstellen, Navigation.

app.py ist der „Rahmen“: Er läuft bei jedem Seitenaufruf und zeigt dann die gewählte Seite.
Start (PowerShell):  .venv\\Scripts\\python.exe -m streamlit run app.py
"""

import streamlit as st

import ui
import ui_tour
from src.data_setup import ensure_database

# Muss der erste Streamlit-Befehl sein: Titel im Browser-Tab, Symbol (eigenes Logo), breites Layout
st.set_page_config(page_title="Bräu am Stein", page_icon="assets/logo_icon.svg", layout="wide")


@st.cache_resource(show_spinner="Datenbank wird beim ersten Start erzeugt …")
def init_database() -> None:
    """Stellt sicher, dass die Datenbank existiert – läuft nur einmal pro Serverprozess."""
    ensure_database()


init_database()
ui.apply_style()  # Fiori-inspirierte Gestaltung und Logo – gilt für alle Seiten

pages = {  # Schlüssel = Dateiname – so verweist auch die Tour (src/tour.py) auf die Seiten
    "home": st.Page("pages/home.py", title="Start", icon=":material/home:", default=True),
    "dashboard": st.Page("pages/dashboard.py", title="Dashboard", icon=":material/bar_chart:"),
    "order_entry": st.Page("pages/order_entry.py", title="KI-Auftragserfassung", icon=":material/smart_toy:"),
    "process": st.Page("pages/process.py", title="Prozess & SAP", icon=":material/account_tree:"),
    "business_case": st.Page("pages/business_case.py", title="Business Case", icon=":material/savings:"),
}
page = st.navigation(list(pages.values()), position="top")
ui_tour.show(page, pages)  # geführte Tour: Band oben auf der Seite – nur, solange sie läuft
page.run()
