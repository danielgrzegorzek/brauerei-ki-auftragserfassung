"""Business Case: Was bringt die KI-Auftragserfassung im Jahr? – Vorher/Nachher zum Ausprobieren.

Auftragsmenge aus der Datenbank, KI-Kosten gemessen, alles andere vorsichtige Annahmen mit Begründung.
Rechenlogik und Annahmen stehen getestet in src/business_case.py – hier nur Anzeige und Schieberegler.
"""

from contextlib import closing

import pandas as pd
import streamlit as st

import ui
from src import business_case as bc
from src import charts
from src.database import get_connection
from src.extraction import MODEL
from src.formatting import format_date, format_eur, format_month, format_number

PLOTLY_CONFIG = {"displayModeBar": False}
EURO = st.column_config.NumberColumn(format="euro")
EVALUATION_URL = "https://github.com/danig204/brauerei-ki-auftragserfassung/blob/main/docs/EVALUATION.md"
FALLBACK_AI_COST = 0.01  # nur falls es keine Messung gibt: 1 Cent je Auftrag (vorsichtig)
UNIT_FORMATS = {         # Anzeige der Reglerwerte im deutschen Format
    "min": lambda v: f"{format_number(v, 1)} min",
    "%": lambda v: f"{format_number(v, 1)} %",
    "€/h": lambda v: f"{format_number(v)} €/h",
    "€": lambda v: f"{format_number(v)} €",
}
BY_KEY = {assumption.key: assumption for assumption in bc.ASSUMPTIONS}


@st.cache_data(show_spinner=False)
def load_data() -> dict:
    """Auftragsmengen aus der Datenbank – ändern sich nur mit neuen Daten."""
    with closing(get_connection()) as conn:
        return {
            "per_channel": bc.orders_last_12_months(conn),
            "period": bc.period_last_12_months(conn),
            "monthly_text": dict(bc.orders_by_month(conn, bc.DEFAULT_CHANNELS)),
            "monthly_all": bc.orders_by_month(conn, bc.DEFAULT_CHANNELS + ("Telefon",)),
        }


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


# ---------- Werte bestimmen (die Regler stehen weiter unten, ihre Werte liegen im Session State) ----------

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
ai_cost = measured.eur_per_order if measured else FALLBACK_AI_COST
settings = {assumption.key: st.session_state[f"bc_{assumption.key}"] for assumption in bc.ASSUMPTIONS}
inputs = bc.inputs_from_settings(text_orders, settings, ai_cost, phone_orders)
result = bc.calculate(inputs)
channel_text = "WhatsApp, E-Mail und Telefon" if include_phone else "WhatsApp und E-Mail"

# ---------- Seitenaufbau ----------

ui.page_header("Business Case",
               "Was bringt die KI-Auftragserfassung im Jahr? Auftragszahlen aus der Datenbank, gemessene "
               "KI-Kosten und vorsichtige Annahmen – zum Ausprobieren.",
               "savings")

# 1. Ergebnis zuerst – auch auf dem Handy ganz oben
tiles = st.columns(3)
tiles[0].metric("Eingesparte Arbeitszeit pro Jahr", f"{format_number(result.saved_hours)} h", border=True,
                help=f"Entspricht rund {format_number(result.saved_work_weeks, 1)} Arbeitswochen à "
                     f"{bc.HOURS_PER_WEEK} Stunden.")
tiles[1].metric("Eingesparte Kosten pro Jahr", format_eur(result.saved_eur, 0), border=True,
                help="Arbeitszeit und Fehlerkosten vorher minus nachher – abzüglich KI-Kosten sowie Betrieb "
                     "und Wartung.")
tiles[2].metric("Vermiedene Fehler pro Jahr", format_number(result.avoided_errors), border=True,
                help="Weniger fehlerhafte Aufträge (Nachlieferungen, Gutschriften, Rückfragen).")

# Ein Satz, der aufgeht: Arbeitszeit + Fehler − KI − Betrieb = Ergebnis
summary = (
    f"Bei **{format_number(inputs.all_orders)} Aufträgen** im Jahr über {channel_text}: "
    f"**{hours_text(result.saved_hours)}** Erfassungsarbeit ({format_eur(result.saved_labor_cost, 0)}) und "
    f"{format_number(result.avoided_errors)} Fehler weniger ({format_eur(result.saved_error_cost, 0)}), "
    f"abzüglich KI-Kosten ({format_eur(result.after.ai_cost, 0)}) sowie Betrieb und Wartung "
    f"({format_eur(result.after.operating_cost, 0)})"
)
if result.saved_eur >= 0:
    st.markdown(f"{summary} – bleiben **{format_eur(result.saved_eur, 0)} pro Jahr**.")
else:
    st.warning(f"{summary} – ergibt **{format_eur(result.saved_eur, 0)} pro Jahr**. Mit diesen Annahmen lohnt "
               "sich die KI-Erfassung finanziell nicht; der Rechner zeigt das bewusst ehrlich an.",
               icon=":material/info:")

left, right = st.columns([2, 3], gap="medium")

# 2. Annahmen – jede mit Begründung (Fragezeichen am Regler)
with left, st.container(key="card-bc-assumptions"):
    st.subheader("Annahmen")
    st.caption("Vorsichtige Standardwerte mit Begründung (Fragezeichen). Verschieben Sie die Regler – "
               "die Rechnung passt sich sofort an.")
    st.toggle("Telefonaufträge einbeziehen", key="bc_phone", persist_state="session",
              help="Standard: nur WhatsApp und E-Mail. Telefonaufträge rechnen wir vorsichtig mit eigenen "
                   "Minuten (es schreibt weiterhin jemand mit) und ohne geringere Fehlerquote.")
    st.markdown("**Zeit je Auftrag**")
    slider("minutes_manual")
    slider("minutes_ai")
    if include_phone:
        slider("minutes_ai_phone")
    st.markdown("**Fehler**")
    for key in ("error_rate_manual", "error_rate_ai", "cost_per_error"):
        slider(key)
    st.markdown("**Kosten**")
    for key in ("hourly_rate", "operating_cost"):
        slider(key)
    st.button("Auf vorsichtige Standardwerte zurücksetzen", icon=":material/restart_alt:", on_click=reset,
              key="bc_reset")

# 3. Vergleich vorher/nachher mit Rechenweg
with right, st.container(key="card-bc-comparison"):
    st.subheader("Kosten pro Jahr – vorher und nachher")
    share = result.after.total / result.before.total * 100 if result.before.total else 0
    lever = (" – die eingesparte Arbeitszeit ist der große Hebel"
             if result.saved_labor_cost > max(result.saved_error_cost, 0) else "")
    st.caption(f"Mit KI fallen {format_number(share)} % der bisherigen Kosten an. Die KI-Aufrufe selbst "
               f"kosten nur {format_eur(result.after.ai_cost, 0)} im Jahr{lever}.")
    bars = ["Vorher", "Mit KI"]
    segments = [
        ("Arbeitszeit", [result.before.labor_cost, result.after.labor_cost]),
        ("Fehlerkosten", [result.before.error_cost, result.after.error_cost]),
        ("KI & Betrieb", [0.0, result.after.ai_cost + result.after.operating_cost]),
    ]
    colors = charts.PALETTES[ui.theme()]
    chart_tab, table_tab = st.tabs([":material/bar_chart: Diagramm", ":material/table_view: Tabelle"])
    with chart_tab:
        ui.chart_legend([(name, color) for (name, _), color in zip(segments, colors["categories"])])
        st.plotly_chart(charts.cost_comparison_chart(bars, segments, colors), config=PLOTLY_CONFIG,
                        key="chart-bc")
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
        st.dataframe(table, hide_index=True,
                     column_config={"Vorher": EURO, "Mit KI": EURO, "Differenz": EURO})
    with st.expander("Rechenweg", icon=":material/calculate:"):
        for step in bc.calculation_steps(inputs, result, ai_cost_measured=measured is not None):
            st.markdown(step)
        start, end = data["period"]
        source = measured.source_text if measured else "keine Messung vorhanden – vorsichtig 1 Cent angenommen"
        st.caption(f"Auftragsmenge aus den (simulierten) Daten vom {format_date(start)} bis {format_date(end)} "
                   f"({channel_text}). KI-Kosten: {source}; Umrechnung vorsichtig 1 US-$ = 1 €. "
                   "Nicht enthalten: das einmalige Einführungsprojekt.")

# 4. Datengrundlage – was gemessen ist und was angenommen
with st.container(key="card-bc-data"):
    st.subheader("Datengrundlage")
    columns = st.columns(4)
    for column, channel in zip(columns, ("WhatsApp", "E-Mail", "Telefon")):
        counted = channel in bc.DEFAULT_CHANNELS or include_phone
        column.metric(f"{channel}-Aufträge (12 Monate)", format_number(data["per_channel"].get(channel, 0)),
                      border=True, help="gezählt" if counted else "nicht gezählt – oben zuschaltbar")
    columns[3].metric("KI-Kosten je Auftrag", f"{format_number(ai_cost * 100, 2)} Cent", border=True,
                      help=measured.source_text if measured else "keine Messung vorhanden – angenommen")
    st.caption(f"**Aus der Datenbank:** Auftragsmengen der letzten 12 Monate (simulierte Daten). **Gemessen:** "
               f"KI-Kosten aus der [Evaluation]({EVALUATION_URL}). **Angenommen:** alle Werte unter „Annahmen“.")

# 5. Nutzen, der sich nicht in Euro rechnet
with st.container(key="card-bc-benefits"):
    st.subheader("Nutzen, der sich nicht in Euro rechnet")
    # Saison über ALLE Kanäle – so viel Arbeit kommt tatsächlich im Innendienst an
    (busy_month, busy), (quiet_month, quiet) = bc.busiest_and_quietest(data["monthly_all"])
    busy_text = data["monthly_text"].get(busy_month, 0)
    busy_saved = busy_text * (inputs.minutes_manual - inputs.minutes_ai) / 60
    if include_phone:
        busy_saved += (busy - busy_text) * (inputs.minutes_manual - inputs.minutes_ai_phone) / 60
    benefits = [
        (":material/calendar_month:", "Entlastung in der Hochsaison",
         f"Im stärksten Monat ({format_month(busy_month)}) kamen {format_number(busy)} Bestellungen über alle "
         f"Kanäle – {format_number((busy / quiet - 1) * 100)} % mehr als im ruhigsten "
         f"({format_month(quiet_month)}). Mit KI sind das allein in diesem Monat rund {hours_text(busy_saved)} "
         f"Erfassungsarbeit ({channel_text})."),
        (":material/bolt:", "Schnellere Rückmeldung an die Wirte",
         "Eingangsbestätigung oder Rückfrage in Sekunden statt nach Feierabend – auch am Wochenende vor dem Fest."),
        (":material/groups:", "Weniger Abhängigkeit von einzelnen Personen",
         "Wer welche Fassgröße bestellt, steht in der Bestellhistorie und nicht nur im Kopf eines Mitarbeiters – "
         "Urlaub und Krankheit bremsen die Erfassung nicht."),
        (":material/database:", "Saubere Daten für Planung und Vertrieb",
         "Jede Bestellung kommt strukturiert ins System – Grundlage für Dashboard, Absatzplanung und die "
         "spätere Übergabe an SAP."),
    ]
    for row in (benefits[:2], benefits[2:]):
        for column, (icon, title, text) in zip(st.columns(2, gap="medium"), row):
            with column:
                st.markdown(f"##### {icon} {title}")
                st.markdown(text)
