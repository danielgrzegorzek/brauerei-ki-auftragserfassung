"""Startseite: Worum geht es, was kann man ausprobieren, wie gut sind die Daten?"""

from contextlib import closing
from datetime import date

import streamlit as st

from src.database import get_connection
from src.formatting import format_date, format_number
from src.plausibility import run_checks


@st.cache_data
def load_overview() -> dict:
    """Eckdaten der Datenbasis und Ergebnis des Plausibilitäts-Checks (zwischengespeichert)."""
    # closing(...) schließt die Verbindung am Ende des with-Blocks automatisch
    with closing(get_connection()) as conn:
        customers, products, orders, first, last = conn.execute("""
            SELECT (SELECT COUNT(*) FROM customers), (SELECT COUNT(*) FROM products),
                   (SELECT COUNT(*) FROM orders), (SELECT MIN(order_date) FROM orders),
                   (SELECT MAX(order_date) FROM orders)
        """).fetchone()
        checks = run_checks(conn)
    return {"customers": customers, "products": products, "orders": orders,
            "first": date.fromisoformat(first), "last": date.fromisoformat(last), "checks": checks}


overview = load_overview()

st.title("🍺 Bräu am Stein")
st.subheader("Vom WhatsApp-Chaos zum sauberen Auftrag")
st.write(
    "Die **Bräu am Stein GmbH** ist eine (fiktive) Familienbrauerei in Niederbayern mit rund "
    "150 Mitarbeitern. Wirtshäuser, Getränkehändler, Supermärkte und Festveranstalter bestellen "
    "per Telefon, E-Mail und immer öfter per **WhatsApp** – als Freitext, oft im Dialekt. "
    "Der Vertriebsinnendienst tippt alles von Hand ab, inklusive Leergut und Pfand."
)
st.write(
    "Diese App zeigt, wie eine **KI** solche Nachrichten in saubere Aufträge umwandelt, "
    "die ein Mensch nur noch prüft und bestätigt – und was die Vertriebsdaten über das "
    "Geschäft verraten."
)

left, middle, right = st.columns(3, border=True)
with left:
    st.markdown("#### :material/bar_chart: Dashboard")
    st.write("Umsatz, Saisonalität, Top-Kunden, Bestellkanäle und offenes Leergut.")
    st.page_link("pages/dashboard.py", label="Zum Dashboard", icon=":material/arrow_forward:")
with middle:
    st.markdown("#### :material/smart_toy: KI-Auftragserfassung")
    st.write("Freitext → strukturierter Auftrag → Prüfung gegen Stammdaten → Bestätigung. "
             "Mit Demo-Modus, der ohne API-Schlüssel funktioniert.")
    st.page_link("pages/order_entry.py", label="Zur Auftragserfassung", icon=":material/arrow_forward:")
with right:
    st.markdown("#### :material/account_tree: Prozess & ERP")
    st.write("Ist- vs. Soll-Prozess und die Übergabe des Auftrags an SAP S/4HANA.")
    st.caption("Kommt in Kürze.")

st.markdown("#### Datenbasis")
passed = sum(check.passed for check in overview["checks"])
total = len(overview["checks"])
cols = st.columns(4)
cols[0].metric("Kunden", overview["customers"])
cols[1].metric("Artikel", overview["products"])
cols[2].metric("Aufträge", format_number(overview["orders"]))
cols[3].metric("Plausibilitäts-Check", f"{passed} / {total} bestanden")
st.caption(
    f"Simulierte Aufträge vom {format_date(overview['first'])} bis {format_date(overview['last'])} "
    "– mit Saisonalität, "
    "Preiserhöhung zum 01.01.2026, Leergut-Kreislauf und steigendem WhatsApp-Anteil. "
    "Alle Firmen, Personen und Zahlen sind frei erfunden."
)

with st.expander(f"Plausibilitäts-Check im Detail ({passed} / {total} bestanden)"):
    st.write("Automatische Prüfungen, ob die simulierten Daten fachlich Sinn ergeben:")
    for check in overview["checks"]:
        icon = ":material/check_circle:" if check.passed else ":material/error:"
        st.markdown(f"{icon} **{check.name}** – {check.detail}")
