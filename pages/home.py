"""Startseite im Stil des Fiori-Launchpads: worum es geht, drei Highlights, Tour, Anwendungen, Datenbasis."""

from contextlib import closing
from datetime import timedelta

import streamlit as st

import ui
import ui_tour
from src import analytics
from src.analytics import Filters
from src.business_case import default_result, measured_ai_cost
from src.database import get_connection
from src.extraction import MODEL
from src.formatting import format_date, format_eur, format_number
from src.master_data import CUSTOMER_GROUPS
from src.plausibility import run_checks


@st.cache_data
def load_overview() -> dict:
    """Eckdaten für Highlights, Kacheln und Datenbasis (zwischengespeichert, nach neuen Aufträgen geleert)."""
    # closing(...) schließt die Verbindung am Ende des with-Blocks automatisch
    with closing(get_connection()) as conn:
        first, last = analytics.data_period(conn)
        # Umsatz der letzten 12 Monate – dieselbe Berechnung wie im Dashboard
        last_12 = Filters(analytics.shift_year(last, -1) + timedelta(days=1), last, CUSTOMER_GROUPS)
        customers, products, orders = conn.execute(
            "SELECT (SELECT COUNT(*) FROM customers), (SELECT COUNT(*) FROM products), "
            "(SELECT COUNT(*) FROM orders WHERE source = 'Historie')"
        ).fetchone()
        _, business_case = default_result(conn, MODEL)
        return {
            "customers": customers, "products": products, "orders": orders, "first": first, "last": last,
            "revenue_12m": analytics.kpis(conn, last_12)["revenue"],
            "checks": run_checks(conn),
            "saved_hours": business_case.saved_hours, "saved_eur": business_case.saved_eur,
        }


overview = load_overview()
evaluation = measured_ai_cost(MODEL)
passed = sum(check.passed for check in overview["checks"])
total = len(overview["checks"])

# ---------- Titelbanner: in einem Satz, worum es geht ----------
with st.container(key="card-hero"):
    text, picture = st.columns([1, 1], gap="large", vertical_alignment="center")
    with text:
        st.caption("Bräu am Stein GmbH · Familienbrauerei in Niederbayern (fiktiv)")
        st.title("Vom WhatsApp-Chaos zum sauberen Auftrag")
        st.markdown("Bestellungen kommen per WhatsApp, E-Mail und Telefon als Freitext – **eine KI macht daraus "
                    "in Sekunden einen geprüften Auftrag, der Mensch bestätigt.**")
        with st.container(horizontal=True, key="hero-actions", vertical_alignment="center"):
            st.button("In 60 Sekunden durch die App", type="primary", icon=":material/play_circle:",
                      on_click=ui_tour.start, key="tour_start")
            st.page_link("pages/order_entry.py", label="Direkt ausprobieren", icon=":material/smart_toy:")
    with picture:
        ui.illustration("hero_brewery", "Brauerei vor niederbayerischen Hügeln mit Hopfengarten und Maibaum")

# ---------- Drei Highlights mit je einer Kennzahl ----------
highlights = st.columns(3)
if evaluation:
    highlights[0].metric("Aufträge in der KI-Evaluation richtig erkannt", f"{evaluation.hits} von {evaluation.total}",
                         border=True, help=f"Live gemessen mit {evaluation.model_name} – inklusive Dialekt, "
                                           "Tippfehler und einem abgewehrten Angriffsversuch.")
highlights[1].metric("Stunden Tipparbeit gespart pro Jahr", format_number(overview["saved_hours"]), border=True,
                     help=f"Vorsichtig gerechnet, rund {format_eur(overview['saved_eur'], 0)} pro Jahr nach Abzug "
                          "von KI-Kosten sowie Betrieb und Wartung – Details im Business Case.")
highlights[2].metric("Aufträge analysiert", format_number(overview["orders"]), border=True,
                     help=f"Zwei Jahre simulierte Vertriebsdaten ({format_date(overview['first'])} bis "
                          f"{format_date(overview['last'])}) – Grundlage für Dashboard und Business Case.")

# ---------- Anwendungen (Kacheln) ----------
st.subheader("Anwendungen")
columns = st.columns(4, gap="medium")
with columns[0]:
    ui.tile("orders", "KI-Auftragserfassung", "Live-Chat: Freitext → geprüfter Auftrag", "message",
            value="< 1", unit="Cent je Auftrag", page="pages/order_entry.py")
with columns[1]:
    ui.tile("business-case", "Business Case", "Vorher/nachher zum Ausprobieren", "savings",
            value=format_number(overview["saved_eur"] / 1000, 1), unit="Tsd. € pro Jahr",
            page="pages/business_case.py")
with columns[2]:
    ui.tile("dashboard", "Vertriebs-Dashboard", "Umsatz der letzten 12 Monate", "chart",
            value=format_number(overview["revenue_12m"] / 1_000_000, 2), unit="Mio. €",
            page="pages/dashboard.py")
with columns[3]:
    ui.tile("soon", "Prozess & SAP-Übergabe", "Ist/Soll, Übergabe an S/4HANA", "process",
            unit="Demnächst")

# ---------- Datenbasis ----------
st.subheader("Datenbasis")
cols = st.columns(4)
cols[0].metric("Kunden", overview["customers"])
cols[1].metric("Artikel", overview["products"])
cols[2].metric("Aufträge", format_number(overview["orders"]))
cols[3].metric("Plausibilitäts-Check", f"{passed} / {total}", help="Automatische fachliche Prüfungen der Daten")
st.caption(
    f"Simulierte Aufträge vom {format_date(overview['first'])} bis {format_date(overview['last'])} "
    "– mit Saisonalität, Preiserhöhung zum 01.01.2026, Leergut-Kreislauf und steigendem WhatsApp-Anteil."
)

with st.expander(f"Plausibilitäts-Check im Detail ({passed} / {total} bestanden)"):
    st.write("Automatische Prüfungen, ob die simulierten Daten fachlich Sinn ergeben:")
    for check in overview["checks"]:
        icon = ":material/check_circle:" if check.passed else ":material/error:"
        st.markdown(f"{icon} **{check.name}** – {check.detail}")

st.caption("Alle Firmen, Personen und Zahlen sind frei erfunden. "
           "Oberfläche angelehnt an die SAP-Fiori-Designrichtlinien.")
