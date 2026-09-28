"""Startseite im Stil des Fiori-Launchpads: Titelbanner, Anwendungskacheln, Datenbasis."""

from contextlib import closing
from datetime import timedelta

import streamlit as st

import ui
from src import analytics
from src.analytics import Filters
from src.database import get_connection
from src.demo_messages import DEMO_MESSAGES
from src.formatting import format_date, format_number
from src.master_data import CUSTOMER_GROUPS
from src.plausibility import run_checks


@st.cache_data
def load_overview() -> dict:
    """Eckdaten für Kacheln und Datenbasis (zwischengespeichert, wird nach neuen Aufträgen geleert)."""
    # closing(...) schließt die Verbindung am Ende des with-Blocks automatisch
    with closing(get_connection()) as conn:
        first, last = analytics.data_period(conn)
        # Umsatz der letzten 12 Monate – dieselbe Berechnung wie im Dashboard
        last_12 = Filters(analytics.shift_year(last, -1) + timedelta(days=1), last, CUSTOMER_GROUPS)
        customers, products, orders = conn.execute(
            "SELECT (SELECT COUNT(*) FROM customers), (SELECT COUNT(*) FROM products), (SELECT COUNT(*) FROM orders)"
        ).fetchone()
        return {
            "customers": customers, "products": products, "orders": orders, "first": first, "last": last,
            "revenue_12m": analytics.kpis(conn, last_12)["revenue"],
            "checks": run_checks(conn),
        }


overview = load_overview()
passed = sum(check.passed for check in overview["checks"])
total = len(overview["checks"])

# ---------- Titelbanner ----------
with st.container(key="card-hero"):
    text, picture = st.columns([1, 1], gap="large", vertical_alignment="center")
    with text:
        st.caption("Bräu am Stein GmbH · Familienbrauerei in Niederbayern (fiktiv)")
        st.title("Vom WhatsApp-Chaos zum sauberen Auftrag")
        st.write(
            "Wirtshäuser, Getränkehändler, Supermärkte und Festveranstalter bestellen per Telefon, "
            "E-Mail und immer öfter per **WhatsApp** – als Freitext, oft im Dialekt. Diese App zeigt, "
            "wie eine **KI** daraus saubere Aufträge macht und was die Vertriebsdaten über das Geschäft verraten."
        )
        st.markdown("**Die KI versteht · der Code entscheidet · der Mensch bestätigt.**")
    with picture:
        ui.illustration("hero_brewery", "Brauerei vor niederbayerischen Hügeln mit Hopfengarten und Maibaum")

# ---------- Anwendungen (Kacheln) ----------
st.subheader("Anwendungen")
left, middle, right = st.columns(3, gap="medium")
with left:
    ui.tile("dashboard", "Vertriebs-Dashboard", "Umsatz der letzten 12 Monate", "chart",
            value=format_number(overview["revenue_12m"] / 1_000_000, 2), unit="Mio. €",
            page="pages/dashboard.py")
with middle:
    ui.tile("orders", "KI-Auftragserfassung", "Freitext → geprüfter Auftrag", "message",
            value=str(len(DEMO_MESSAGES)), unit="Nachrichten",
            page="pages/order_entry.py")
with right:
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
