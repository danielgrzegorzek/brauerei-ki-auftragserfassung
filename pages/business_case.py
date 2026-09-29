"""Business Case: Was bringt die KI-Auftragserfassung im Jahr? – Vorher/Nachher zum Ausprobieren.

Auftragsmenge aus der Datenbank, KI-Kosten gemessen, alles andere vorsichtige Annahmen mit Begründung.
Rechenlogik und Annahmen stehen getestet in src/business_case.py – hier nur Anzeige und Schieberegler.
Oben das Ergebnis, Annahmen und Rechenweg eingeklappt darunter.
"""

from contextlib import closing

import pandas as pd
import streamlit as st

import ui
from src import business_case as bc
from src import charts
from src.database import get_connection
from src.extraction import MODEL
from src.formatting import format_date, format_eur, format_number

PLOTLY_CONFIG = {"displayModeBar": False}
EURO = st.column_config.NumberColumn(format="euro")
EVALUATION_URL = "https://github.com/danielgrzegorzek/brauerei-ki-auftragserfassung/blob/main/docs/EVALUATION.md"
UNIT_FORMATS = {         # Anzeige der Reglerwerte im deutschen Format
    "min": lambda v: f"{format_number(v, 1)} min",
    "%": lambda v: f"{format_number(v, 1)} %",
    "€/h": lambda v: f"{format_number(v)} €/h",
    "€": lambda v: f"{format_number(v)} €",
}
BY_KEY = {assumption.key: assumption for assumption in bc.ASSUMPTIONS}
# Nutzen, der sich nicht in Euro rechnet – als kurze Stichpunkte
BENEFITS = [
    (":material/calendar_month:", "Entlastung in der Hochsaison"),
    (":material/bolt:", "Rückmeldung in Sekunden"),
    (":material/groups:", "Wissen nicht nur im Kopf Einzelner"),
    (":material/database:", "Saubere Daten für Planung und SAP"),
]


@st.cache_data(show_spinner=False)
def load_data() -> dict:
    """Auftragsmengen aus der Datenbank – ändern sich nur mit neuen Daten."""
    with closing(get_connection()) as conn:
        return {"per_channel": bc.orders_last_12_months(conn), "period": bc.period_last_12_months(conn)}


def options(assumption: bc.Assumption) -> list[float]:
    """Werte eines Reglers von Minimum bis Maximum in Schritten."""
    count = round((assumption.maximum - assumption.minimum) / assumption.step)
    return [round(assumption.minimum + i * assumption.step, 2) for i in range(count + 1)]


def slider(key: str) -> None:
    assumption = BY_KEY[key]
    # persist_state: Werte bleiben erhalten, wenn man zu einer anderen Seite wechselt und zurückkommt
    st.select_slider(assumption.label, options=options(assumption), key=f"bc_{key}", persist_state="session",
                     format_func=UNIT_FORMATS[assumption.unit], help=assumption.reason)


def reset() -> None:
    for assumption in bc.ASSUMPTIONS:
        st.session_state[f"bc_{assumption.key}"] = assumption.default
    st.session_state.bc_phone = False


def hours_text(hours: float) -> str:
    """„217 Stunden weniger“ bzw. ehrlich „27 Stunden mehr“ Arbeit."""
    return f"{format_number(abs(hours))} Stunden {'weniger' if hours >= 0 else 'mehr'}"


@st.fragment
def calculator() -> None:
    """Ergebnis, Diagramm, Annahmen und Rechenweg. Als Fragment: Ein Regler lädt nur diesen Teil neu."""
    # Werte bestimmen – die Regler stehen weiter unten, ihre Werte liegen im Session State
    for assumption in bc.ASSUMPTIONS:
        if f"bc_{assumption.key}" not in st.session_state:
            st.session_state[f"bc_{assumption.key}"] = assumption.default
    if "bc_phone" not in st.session_state:
        st.session_state.bc_phone = False

    data = load_data()
    include_phone = st.session_state.bc_phone
    text_orders = sum(data["per_channel"].get(channel, 0) for channel in bc.DEFAULT_CHANNELS)
    phone_orders = data["per_channel"].get("Telefon", 0) if include_phone else 0
    measured = bc.measured_ai_cost(MODEL)
    ai_cost = measured.eur_per_order if measured else bc.FALLBACK_AI_COST
    settings = {assumption.key: st.session_state[f"bc_{assumption.key}"] for assumption in bc.ASSUMPTIONS}
    inputs = bc.inputs_from_settings(text_orders, settings, ai_cost, phone_orders)
    result = bc.calculate(inputs)
    channel_text = "WhatsApp, E-Mail und Telefon" if include_phone else "WhatsApp und E-Mail"

    # 1. Drei große Kennzahlen – das Ergebnis zuerst
    with st.container(key="bc-kpis"):
        tiles = st.columns(3)
    tiles[0].metric("Eingesparte Arbeitszeit pro Jahr", f"{format_number(result.saved_hours)} h", border=True,
                    help=f"Entspricht rund {format_number(result.saved_work_weeks, 1)} Arbeitswochen à "
                         f"{bc.HOURS_PER_WEEK} Stunden.")
    tiles[1].metric("Eingesparte Kosten pro Jahr", format_eur(result.saved_eur, 0), border=True,
                    help="Arbeitszeit und Fehlerkosten vorher minus nachher – abzüglich KI-Kosten sowie Betrieb "
                         "und Wartung.")
    tiles[2].metric("Vermiedene Fehler pro Jahr", format_number(result.avoided_errors), border=True,
                    help="Weniger fehlerhafte Aufträge (Nachlieferungen, Gutschriften, Rückfragen).")
    if result.saved_eur < 0:
        st.warning("Mit diesen Annahmen lohnt sich die KI-Erfassung finanziell nicht – der Rechner zeigt das ehrlich.",
                   icon=":material/info:")

    # 2. Vergleich vorher/nachher
    with st.container(key="card-bc-comparison"):
        st.subheader("Kosten pro Jahr – vorher und mit KI", anchor=False)
        segments = [
            ("Arbeitszeit", [result.before.labor_cost, result.after.labor_cost]),
            ("Fehlerkosten", [result.before.error_cost, result.after.error_cost]),
            ("KI & Betrieb", [0.0, result.after.ai_cost + result.after.operating_cost]),
        ]
        colors = charts.PALETTES[ui.theme()]
        chart_tab, table_tab = st.tabs([":material/bar_chart: Diagramm", ":material/table_view: Tabelle"])
        with chart_tab:
            ui.chart_legend([(name, color) for (name, _), color in zip(segments, colors["categories"])])
            st.plotly_chart(charts.cost_comparison_chart(["Vorher", "Mit KI"], segments, colors),
                            config=PLOTLY_CONFIG, key="chart-bc")
        with table_tab:
            rows = [
                ("Arbeitszeit", result.before.labor_cost, result.after.labor_cost),
                ("Fehlerkosten", result.before.error_cost, result.after.error_cost),
                (f"KI-Aufrufe ({'gemessen' if measured else 'angenommen'})", result.before.ai_cost,
                 result.after.ai_cost),
                ("Betrieb & Wartung", result.before.operating_cost, result.after.operating_cost),
                ("Summe", result.before.total, result.after.total),
            ]
            table = pd.DataFrame(rows, columns=["Kostenart", "Vorher", "Mit KI"])
            table["Differenz"] = table["Mit KI"] - table["Vorher"]
            st.dataframe(table, hide_index=True, column_config={"Vorher": EURO, "Mit KI": EURO, "Differenz": EURO})

    # 3. Nutzen, der sich nicht in Euro rechnet – nur Stichpunkte
    with st.container(key="bc-benefits", horizontal=True, vertical_alignment="center"):
        st.caption("Außerdem, ohne Euro-Wert:", width="content")
        for icon, title in BENEFITS:
            st.badge(title, icon=icon, color="gray")

    # 4. Annahmen – eingeklappt, jede mit Begründung (Fragezeichen am Regler)
    # key: Die Warnung bei negativem Ergebnis kommt und geht – ohne festen Schlüssel würde der Bereich dabei
    # zuklappen, mitten beim Verschieben eines Reglers
    with st.expander("Annahmen anpassen", icon=":material/tune:", key="bc-assumptions"):
        st.toggle("Telefonaufträge einbeziehen", key="bc_phone", persist_state="session",
                  help="Standard: nur WhatsApp und E-Mail. Telefonaufträge rechnen wir vorsichtig mit eigenen "
                       "Minuten (es schreibt weiterhin jemand mit) und ohne geringere Fehlerquote.")
        time_column, error_column, cost_column = st.columns(3, gap="large")
        with time_column:
            st.markdown("**Zeit je Auftrag**")
            slider("minutes_manual")
            slider("minutes_ai")
            if include_phone:
                slider("minutes_ai_phone")
        with error_column:
            st.markdown("**Fehler**")
            for key in ("error_rate_manual", "error_rate_ai", "cost_per_error"):
                slider(key)
        with cost_column:
            st.markdown("**Kosten**")
            for key in ("hourly_rate", "operating_cost"):
                slider(key)
        st.button("Auf vorsichtige Standardwerte zurücksetzen", icon=":material/restart_alt:", on_click=reset,
                  key="bc_reset")

    # 5. Rechenweg mit Datengrundlage – eingeklappt
    with st.expander("Rechenweg", icon=":material/calculate:", key="bc-steps"):
        st.markdown(
            f"Bei **{format_number(inputs.all_orders)} Aufträgen** im Jahr über {channel_text}: "
            f"**{hours_text(result.saved_hours)}** Erfassungsarbeit ({format_eur(result.saved_labor_cost, 0)}) und "
            f"{format_number(result.avoided_errors)} Fehler weniger ({format_eur(result.saved_error_cost, 0)}), "
            f"abzüglich KI-Kosten ({format_eur(result.after.ai_cost, 0)}) sowie Betrieb und Wartung "
            f"({format_eur(result.after.operating_cost, 0)})."
        )
        for step in bc.calculation_steps(inputs, result, ai_cost_measured=measured is not None):
            st.markdown(step)
        start, end = data["period"]
        counts = " · ".join(
            f"{channel} {format_number(data['per_channel'].get(channel, 0))}"
            + ("" if channel in bc.DEFAULT_CHANNELS or include_phone else " (nicht gezählt)")
            for channel in ("WhatsApp", "E-Mail", "Telefon"))
        source = measured.source_text if measured else "keine Messung vorhanden – vorsichtig 1 Cent angenommen"
        st.caption(f"**Aus der Datenbank:** Aufträge vom {format_date(start)} bis {format_date(end)} (simulierte "
                   f"Daten): {counts}. **Gemessen:** KI-Kosten {format_number(ai_cost * 100, 2)} Cent je Auftrag – "
                   f"{source} ([Evaluation]({EVALUATION_URL})); Umrechnung vorsichtig 1 US-$ = 1 €. "
                   "**Angenommen:** alle Werte unter „Annahmen anpassen“. Nicht enthalten: das einmalige "
                   "Einführungsprojekt.")


# ---------- Seitenaufbau ----------

ui.page_header("Business Case",
               "Was die KI-Auftragserfassung im Jahr bringt – mit Daten aus der Datenbank und vorsichtigen Annahmen.",
               "savings")
calculator()
