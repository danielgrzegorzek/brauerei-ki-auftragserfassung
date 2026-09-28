"""Vertriebs-Dashboard: Filter, Kennzahlen und Diagramme."""

from contextlib import closing
from datetime import date, timedelta

import streamlit as st

import ui
from src import analytics, charts
from src.analytics import Filters
from src.database import get_connection
from src.formatting import format_change, format_date, format_eur_compact, format_number
from src.master_data import CUSTOMER_GROUPS

PLOTLY_CONFIG = {"displayModeBar": False}  # keine Plotly-Werkzeugleiste – ruhigeres Bild
EURO = st.column_config.NumberColumn(format="euro")
NUMBER = st.column_config.NumberColumn(format="localized")


def percent(part: float, whole: float) -> str:
    return f"{format_number(part / whole * 100)} %" if whole else "–"


def chart_section(key: str, title: str, insight: str, fig, table, column_config: dict | None = None) -> None:
    """Einheitlicher Abschnitt als Karte: Überschrift, Kernaussage, Reiter „Diagramm“ und „Tabelle“."""
    with st.container(key=f"card-{key}"):
        st.markdown(f"#### {title}")
        st.caption(insight)
        chart_tab, table_tab = st.tabs([":material/bar_chart: Diagramm", ":material/table_view: Tabelle"])
        with chart_tab:
            st.plotly_chart(fig, config=PLOTLY_CONFIG, key=f"chart-{key}")
        with table_tab:
            st.dataframe(table, hide_index=True, column_config=column_config)


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
            "groups": analytics.revenue_by_customer_group(conn, filters),
            "products": analytics.revenue_by_product(conn, filters),
            "top_customers": analytics.top_customers(conn, filters, limit=10),
            "seasonality": analytics.seasonality_index(conn, filters),
            "channels": analytics.channel_share_by_quarter(conn, filters),
            "empties": analytics.open_empties_by_customer(conn, filters.end, filters.customer_groups),
        }
        if compare:
            previous = analytics.previous_year(filters)
            data["kpis_previous"] = analytics.kpis(conn, previous)
            data["deposit_previous"] = analytics.open_deposit(conn, previous.end, filters.customer_groups)
    return data


first_day, last_day = load_period()

ui.page_header("Vertriebs-Dashboard",
               "Umsatz, Absatz und Leergut – alle Umsätze netto, ohne Mehrwertsteuer und ohne Pfand.", "chart")

# ---------- Filterleiste (Fiori „Filter Bar“): eine Karte oben, gilt für alles darunter ----------
# Letztes volles Kalenderjahr in den Daten (z. B. 2025, solange 2026 noch läuft)
full_year = last_day.year if (last_day.month, last_day.day) == (12, 31) else last_day.year - 1
PERIOD_OPTIONS = ["Letzte 12 Monate", "Gesamter Zeitraum", f"Kalenderjahr {full_year}", "Benutzerdefiniert"]
with st.container(key="card-filters"):
    filter_left, filter_right = st.columns([3, 2])
    with filter_left:
        period_choice = st.segmented_control("Zeitraum", PERIOD_OPTIONS, default="Letzte 12 Monate",
                                             required=True, wrap=True)
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
    st.caption(f"{format_date(start)} – {format_date(end)}"
               + (" · Veränderung gegenüber dem Vorjahreszeitraum" if compare else " · kein Vorjahresvergleich möglich"))

data = load_dashboard_data(filters, compare)
if data["kpis"]["orders"] == 0:
    st.info("Im gewählten Zeitraum gibt es für diese Kundengruppen keine Aufträge.")
    st.stop()

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
    # Monate ohne Aufträge: 0 statt „Division durch null“
    "avg_order_value": (monthly["revenue"] / monthly["orders"]).fillna(0).round().tolist(),
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

# ---------- Diagramme ----------
# Farben passend zum hellen oder dunklen Design, das der Betrachter eingestellt hat
colors = charts.PALETTES["dark" if st.context.theme.type == "dark" else "light"]
total_revenue = kpis["revenue"]

# Umsatz je Monat
month_labels = [charts.month_label(m) for m in monthly["month"]]
peak, low = monthly["revenue"].idxmax(), monthly["revenue"].idxmin()
chart_section(
    "monthly", "Umsatz je Monat",
    f"Stärkster Monat: {month_labels[peak]} ({format_eur_compact(monthly['revenue'][peak])}), "
    f"schwächster: {month_labels[low]} ({format_eur_compact(monthly['revenue'][low])}).",
    charts.monthly_revenue_chart(monthly, colors),
    monthly.assign(month=month_labels).rename(columns={
        "month": "Monat", "revenue": "Umsatz", "hectoliters": "Absatz (hl)", "orders": "Aufträge"}),
    {"Umsatz": EURO, "Absatz (hl)": NUMBER, "Aufträge": NUMBER},
)

left, right = st.columns(2, gap="large")
with left:
    groups_df = data["groups"]
    top_group = groups_df.iloc[0]
    chart_section(
        "groups", "Umsatz nach Kundengruppe",
        f"{top_group['customer_group']} bringt {percent(top_group['revenue'], total_revenue)} des Umsatzes.",
        charts.ranking_chart(
            groups_df["customer_group"].tolist(), (groups_df["revenue"] / 1000).tolist(),
            [f"<b>{g}</b><br>{format_eur_compact(r)} · {percent(r, total_revenue)}<br>{format_number(o)} Aufträge"
             for g, r, o in zip(groups_df["customer_group"], groups_df["revenue"], groups_df["orders"])],
            colors, value_labels=[format_eur_compact(r) for r in groups_df["revenue"]], axis_title="Tsd. €",
        ),
        groups_df.rename(columns={"customer_group": "Kundengruppe", "revenue": "Umsatz", "orders": "Aufträge"}),
        {"Umsatz": EURO, "Aufträge": NUMBER},
    )
with right:
    products_df = data["products"]
    top_product = products_df.iloc[0]
    chart_section(
        "products", "Umsatz nach Artikel",
        f"Umsatzstärkster Artikel: {top_product['product']} "
        f"({percent(top_product['revenue'], total_revenue)} des Umsatzes).",
        charts.ranking_chart(
            products_df["product"].tolist(), (products_df["revenue"] / 1000).tolist(),
            [f"<b>{p}</b><br>{format_eur_compact(r)}<br>{format_number(q)} Stück · {format_number(hl)} hl"
             for p, r, q, hl in zip(products_df["product"], products_df["revenue"],
                                    products_df["quantity"], products_df["hectoliters"])],
            colors, axis_title="Tsd. €",
        ),
        products_df.rename(columns={"product": "Artikel", "product_group": "Warengruppe", "quantity": "Menge",
                                    "hectoliters": "Absatz (hl)", "revenue": "Umsatz"}),
        {"Umsatz": EURO, "Menge": NUMBER, "Absatz (hl)": NUMBER},
    )

left, right = st.columns(2, gap="large")
with left:
    season = data["seasonality"]
    summer = [m for m in (6, 7, 8) if m in season.columns]
    if summer:
        summer_peak = season[summer].mean(axis=1)
        insight = (f"Stärkste Sommerspitze: {summer_peak.idxmax()} – im Sommer "
                   f"{format_number(summer_peak.max())} % eines Durchschnittsmonats.")
    else:
        insight = "Der gewählte Zeitraum enthält keine Sommermonate."
    table = season.round(0).rename(columns=lambda m: charts.MONTH_NAMES[m - 1]).reset_index()
    chart_section(
        "season", "Saisonalität je Warengruppe",
        insight + " Index 100 = Durchschnittsmonat (Absatz in hl).",
        charts.seasonality_heatmap(season, colors),
        table.rename(columns={"product_group": "Warengruppe"}),
    )
with right:
    channels = data["channels"]
    whatsapp = channels[(channels["channel"] == "WhatsApp") & channels["share"].notna()]
    first, last = whatsapp.iloc[0], whatsapp.iloc[-1]
    trend_text = ("steigt" if last["share"] > first["share"] else
                  "sinkt" if last["share"] < first["share"] else "bleibt gleich")
    chart_section(
        "channels", "Bestellkanäle je Quartal",
        f"Der WhatsApp-Anteil {trend_text}: {format_number(first['share'] * 100)} % ({first['quarter']}) → "
        f"{format_number(last['share'] * 100)} % ({last['quarter']}).",
        charts.channel_chart(channels, colors),
        channels.assign(share=channels["share"] * 100).rename(columns={
            "quarter": "Quartal", "channel": "Kanal", "orders": "Aufträge", "share": "Anteil (%)"}),
        {"Aufträge": NUMBER, "Anteil (%)": st.column_config.NumberColumn(format="%.1f")},
    )

left, right = st.columns(2, gap="large")
with left:
    top = data["top_customers"]
    chart_section(
        "top-customers", "Top-10-Kunden",
        f"Die 10 umsatzstärksten Kunden stehen für {percent(top['revenue'].sum(), total_revenue)} des Umsatzes.",
        charts.ranking_chart(
            top["customer"].tolist(), (top["revenue"] / 1000).tolist(),
            [f"<b>{c}</b><br>{g} · {city}<br>{format_eur_compact(r)} · {format_number(o)} Aufträge"
             for c, g, city, r, o in zip(top["customer"], top["customer_group"], top["city"],
                                         top["revenue"], top["orders"])],
            colors, axis_title="Tsd. €",
        ),
        top.rename(columns={"customer": "Kunde", "customer_group": "Kundengruppe", "city": "Ort",
                            "revenue": "Umsatz", "orders": "Aufträge"}),
        {"Umsatz": EURO, "Aufträge": NUMBER},
    )
with right:
    empties = data["empties"]
    top_empties = empties.head(10)
    chart_section(
        "empties", f"Offenes Leergut am {format_date(end)}",
        f"{len(empties)} Kunden haben Leergut offen; die 10 größten stehen für "
        f"{percent(top_empties['deposit_eur'].sum(), empties['deposit_eur'].sum())} des offenen Pfands.",
        charts.ranking_chart(
            top_empties["customer"].tolist(), top_empties["deposit_eur"].tolist(),
            [f"<b>{c}</b><br>{g}<br>{format_number(k)} Kästen · {format_number(f)} Fässer<br>"
             f"{format_eur_compact(d)} Pfand"
             for c, g, k, f, d in zip(top_empties["customer"], top_empties["customer_group"],
                                      top_empties["crates"], top_empties["kegs"], top_empties["deposit_eur"])],
            colors, value_labels=[format_eur_compact(d) for d in top_empties["deposit_eur"]], axis_title="€ Pfand",
        ),
        empties.rename(columns={"customer": "Kunde", "customer_group": "Kundengruppe", "city": "Ort",
                                "crates": "Kästen", "kegs": "Fässer", "deposit_eur": "Pfand"}),
        {"Pfand": EURO, "Kästen": NUMBER, "Fässer": NUMBER},
    )
