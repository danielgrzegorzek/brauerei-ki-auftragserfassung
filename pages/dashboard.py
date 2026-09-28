"""Vertriebs-Dashboard: Filter, Kennzahlen und Diagramme."""

from contextlib import closing
from datetime import date, timedelta

import streamlit as st

from src import analytics
from src.analytics import Filters
from src.database import get_connection
from src.formatting import format_change, format_date, format_eur_compact, format_number
from src.master_data import CUSTOMER_GROUPS


@st.cache_data(show_spinner=False)
def load_period():
    with closing(get_connection()) as conn:
        return analytics.data_period(conn)


@st.cache_data(show_spinner="Daten werden geladen …")
def load_dashboard_data(filters: Filters, compare: bool) -> dict:
    """Lädt alle Auswertungen für die gewählten Filter – zwischengespeichert je Filterkombination."""
    with closing(get_connection()) as conn:
        data = {
            "kpis": analytics.kpis(conn, filters),
            "deposit": analytics.open_deposit(conn, filters.end, filters.customer_groups),
            "monthly": analytics.revenue_by_month(conn, filters),
            "deposit_monthly": analytics.open_deposit_by_month(conn, filters),
        }
        if compare:
            previous = analytics.previous_year(filters)
            data["kpis_previous"] = analytics.kpis(conn, previous)
            data["deposit_previous"] = analytics.open_deposit(conn, previous.end, filters.customer_groups)
    return data


first_day, last_day = load_period()

st.title("Vertriebs-Dashboard")
st.caption("Alle Umsätze netto, ohne Mehrwertsteuer und ohne Pfand.")

# ---------- Filter: eine Zeile oben, gilt für alles darunter ----------
# Letztes volles Kalenderjahr in den Daten (z. B. 2025, solange 2026 noch läuft)
full_year = last_day.year if (last_day.month, last_day.day) == (12, 31) else last_day.year - 1
PERIOD_OPTIONS = ["Letzte 12 Monate", "Gesamter Zeitraum", f"Kalenderjahr {full_year}", "Benutzerdefiniert"]
filter_left, filter_right = st.columns([3, 2])
with filter_left:
    period_choice = st.segmented_control("Zeitraum", PERIOD_OPTIONS, default="Letzte 12 Monate",
                                         required=True)
    if period_choice == "Letzte 12 Monate":
        start, end = analytics.shift_year(last_day, -1) + timedelta(days=1), last_day
    elif period_choice == "Gesamter Zeitraum":
        start, end = first_day, last_day
    elif period_choice == f"Kalenderjahr {full_year}":
        start, end = date(full_year, 1, 1), date(full_year, 12, 31)
    else:
        picked = st.date_input("Von – bis", value=(first_day, last_day), min_value=first_day,
                               max_value=last_day, format="DD.MM.YYYY")
        if len(picked) != 2:
            st.info("Bitte ein Start- und ein Enddatum wählen.")
            st.stop()
        start, end = picked
with filter_right:
    groups = st.pills("Kundengruppen", CUSTOMER_GROUPS, selection_mode="multi", default=CUSTOMER_GROUPS,
                      wrap=True)

if not groups:
    st.info("Bitte mindestens eine Kundengruppe auswählen.")
    st.stop()

filters = Filters(start, end, tuple(groups))
# Vorjahresvergleich nur, wenn der ganze Vorjahreszeitraum in den Daten liegt
compare = analytics.previous_year(filters).start >= first_day
data = load_dashboard_data(filters, compare)

st.caption(f"{format_date(start)} – {format_date(end)}"
           + (" · Veränderung gegenüber dem Vorjahreszeitraum" if compare else " · kein Vorjahresvergleich möglich"))

# ---------- Kennzahlen ----------
kpis = data["kpis"]
previous = data.get("kpis_previous", {})


def change(key: str) -> str | None:
    return format_change(kpis[key], previous[key]) if compare else None


# Monatswerte für die kleinen Verlaufslinien in den Kacheln
monthly = data["monthly"]
trend = {
    "revenue": monthly["revenue"].round().tolist(),
    "orders": monthly["orders"].tolist(),
    "hectoliters": monthly["hectoliters"].round().tolist(),
    "avg_order_value": (monthly["revenue"] / monthly["orders"]).round().tolist(),
    "deposit": data["deposit_monthly"]["deposit_eur"].round().tolist(),
}
tile_style = {"border": True, "chart_type": "area"}

tiles = st.columns(5)
tiles[0].metric("Umsatz", format_eur_compact(kpis["revenue"]), change("revenue"),
                chart_data=trend["revenue"], help="Nettoumsatz aller Auftragspositionen im Zeitraum",
                **tile_style)
tiles[1].metric("Aufträge", format_number(kpis["orders"]), change("orders"),
                chart_data=trend["orders"], **tile_style)
tiles[2].metric("Absatz", f"{format_number(kpis['hectoliters'])} hl", change("hectoliters"),
                chart_data=trend["hectoliters"], help="Verkaufte Menge in Hektolitern (1 hl = 100 Liter)",
                **tile_style)
tiles[3].metric("Ø Auftragswert", format_eur_compact(kpis["avg_order_value"]), change("avg_order_value"),
                chart_data=trend["avg_order_value"], **tile_style)
tiles[4].metric("Offenes Pfand", format_eur_compact(data["deposit"]),
                format_change(data["deposit"], data["deposit_previous"]) if compare else None,
                delta_color="inverse", chart_data=trend["deposit"],
                help=f"Leergut, das am {format_date(end)} noch bei den Kunden steht, bewertet mit Pfand. "
                     "Ein Anstieg ist schlecht (rot).",
                **tile_style)
