"""Prozess & SAP-Übergabe: Ist- und Soll-Prozess und wie ein bestätigter Auftrag in SAP S/4HANA ankommt.

Inhalt und Regeln stehen getestet in src/process.py und src/sap_mapping.py – hier nur die Anzeige.
Die Übergabe ist eine Simulation: Es ist kein SAP-System angebunden.
"""

import html
import json
from contextlib import closing
from datetime import date

import pandas as pd
import streamlit as st

import ui
import ui_capture as capture_ui
from src import process, sap_mapping
from src.business_case import DEFAULT_CHANNELS, DEFAULTS
from src.database import get_connection
from src.formatting import format_date, format_eur, format_number
from src.order_capture import captured_orders

EXAMPLE = "example"  # Auswahl „Beispiel (nicht gespeichert)“
KIND_CLASSES = {process.MANUAL: "step-manual", process.AUTOMATIC: "step-auto", process.CUSTOMER: "step-customer"}


def swimlane(steps: list[process.ProcessStep]) -> str:
    """Schwimmbahnen je Rolle (wie in BPMN): Schritte von links nach rechts, jede Rolle in ihrer Bahn.
    Auf schmalen Bildschirmen macht das CSS daraus eine nummerierte Liste mit Rollen-Etikett."""
    # lang="de": Der Browser trennt lange deutsche Wörter dann richtig („Eingangs-bestätigung“)
    parts = [f'<div class="swimlane" lang="de" style="--steps: {len(steps)}" role="list">']
    for row, lane in enumerate(process.LANES, start=1):
        parts.append(f'<div class="lane-band" style="grid-row: {row}" aria-hidden="true"></div>'
                     f'<div class="lane-label" style="grid-row: {row}" aria-hidden="true">{html.escape(lane)}</div>')
    for number, step in enumerate(steps, start=1):
        meta = [step.kind] + ([f"{format_number(step.minutes, 1)} min"] if step.minutes else []) \
            + (["Medienbruch"] if step.media_break else [])
        parts.append(
            f'<div class="step {KIND_CLASSES[step.kind]}" role="listitem" '
            f'style="grid-row: {process.LANES.index(step.lane) + 1}; grid-column: {number + 1}">'
            f'<span class="step-top"><span class="step-no">{number}</span>'
            f'<span class="step-lane">{html.escape(step.lane)}</span></span>'
            f'<strong>{html.escape(step.title)}</strong>'
            f'<span class="step-meta">{html.escape(" · ".join(meta))}</span>'
            f'<span class="step-note">{html.escape(step.note)}</span></div>'
        )
    parts.append("</div>")
    return "".join(parts)


def order_options() -> tuple[list, dict]:
    """Das Beispiel und die gespeicherten Aufträge (neueste zuerst) – mit Anzeigetext.
    Das Beispiel steht vorn: Die Datenbank teilen sich alle Besucher, der neueste Auftrag ist oft ein fremder."""
    with closing(get_connection()) as conn:
        saved = captured_orders(conn)
    labels = {EXAMPLE: "Beispiel: Stammwirt per WhatsApp (nicht gespeichert)"}
    labels |= {order_id: f"Auftrag {order_id} · {name} · Lieferung {format_date(date.fromisoformat(day))}"
               for order_id, name, day, *_ in saved}
    return list(labels), labels


# ================= Seitenaufbau =================

ui.page_header("Prozess & SAP-Übergabe",
               "Wie eine Bestellung heute läuft, wie sie mit KI läuft – und wie der bestätigte Auftrag als "
               "Kundenauftrag in SAP S/4HANA ankommt.",
               "process")

# 1. Kennzahlen: heute → mit KI
before, after = process.figures(process.AS_IS), process.figures(process.TO_BE)
tiles = st.columns(4)
tiles[0].metric("Manuelle Schritte je Auftrag", format_number(after.manual_steps), border=True,
                delta=f"-{before.manual_steps - after.manual_steps} gegenüber heute", delta_color="inverse")
tiles[1].metric("Arbeitszeit je Auftrag", f"{format_number(after.minutes)} min", border=True,
                delta=f"-{format_number(before.minutes - after.minutes)} min gegenüber heute", delta_color="inverse",
                help="Dieselben Annahmen wie im Business Case.")
tiles[2].metric("Medienbrüche", format_number(after.media_breaks), border=True,
                delta=f"-{before.media_breaks - after.media_breaks} gegenüber heute", delta_color="inverse",
                help="Stellen, an denen jemand Informationen von einem System ins andere überträgt.")
tiles[3].metric("Erste Rückmeldung an den Kunden", "Sekunden", border=True, delta="statt Stunden",
                delta_color="off", delta_arrow="off",
                help="Eingangsbestätigung oder Rückfrage im Chat – verbindlich wird es nach der Freigabe.")
st.caption(f"Gilt für Bestellungen per {' und '.join(DEFAULT_CHANNELS)}. Bei Anrufen schreibt weiterhin jemand "
           f"mit – rund {format_number(DEFAULTS['minutes_ai_phone'])} statt "
           f"{format_number(DEFAULTS['minutes_manual'])} Minuten (siehe Business Case).")

# 2. Ablauf als Schwimmbahnen
with st.container(key="card-process-flow"):
    st.subheader("Ablauf – heute und mit KI")
    st.caption("Jede Bahn ist eine Rolle. Farbiger Rand: orange = manuell, grün = automatisch, blau = Kunde "
               "(steht zusätzlich als Text an jedem Schritt).")
    as_is_tab, to_be_tab = st.tabs([":material/history: Heute (Ist)", ":material/auto_awesome: Mit KI (Soll)"])
    with as_is_tab:
        ui.raw_html(swimlane(process.AS_IS))
    with to_be_tab:
        ui.raw_html(swimlane(process.TO_BE))

# 3. Übergabe an SAP S/4HANA
with st.container(key="card-sap"):
    st.subheader("Übergabe an SAP S/4HANA")
    st.markdown(
        "Nach der Freigabe durch den Menschen geht der Auftrag als **Kundenauftrag** an SAP – über die "
        "Standard-Schnittstelle `API_SALES_ORDER_SRV` (OData, JSON). Kopf und Positionen kommen in **einem** "
        "Aufruf an. **Preise und Leergut schicken wir nicht mit:** Die ermittelt SAP selbst."
    )
    options, labels = order_options()
    preselect = st.session_state.pop("sap_order_id", None)
    if preselect in options:  # gerade in der Auftragserfassung gespeichert → gleich diesen zeigen
        st.session_state.sap_choice = preselect
    elif st.session_state.get("sap_choice") not in options:  # z. B. nach Neustart der App nicht mehr vorhanden
        st.session_state.pop("sap_choice", None)
    choice = st.selectbox("Auftrag", options, format_func=labels.get, key="sap_choice", persist_state="session",
                          help="Das Beispiel oder Aufträge, die in der KI-Auftragserfassung bestätigt und "
                               "gespeichert wurden.")
    with closing(get_connection()) as conn:
        order = (sap_mapping.example_order(conn, capture_ui.today()) if choice == EXAMPLE
                 else sap_mapping.load_order(conn, choice))
    payload = sap_mapping.sales_order_payload(order)
    missing = sap_mapping.missing_fields(payload)
    if missing:
        st.error(f"Unvollständig – es fehlt: {', '.join(missing)}.", icon=":material/error:")
    else:
        net = f" · erwarteter Nettowert laut App {format_eur(order.net_value)}" if order.net_value else ""
        positions = "1 Position" if len(order.lines) == 1 else f"{len(order.lines)} Positionen"
        st.success(f"Vollständig – bereit zur Übergabe: {positions} für "
                   f"{order.customer_name}{net}.", icon=":material/check_circle:")

    _, products = capture_ui.master_data()
    st.markdown("##### Feld-Mapping: App → SAP")
    # Statische Tabelle statt st.dataframe: bricht lange Werte um, statt sie abzuschneiden
    st.table(pd.DataFrame(sap_mapping.field_mapping(
        order, payload, {pid: product["name"] for pid, product in products.items()})),
        hide_index=True, border="horizontal")
    st.caption("Verkaufsorganisation, Vertriebsweg und Sparte zusammen ergeben den **Vertriebsbereich** – "
               "er bestimmt in SAP u. a. Preislisten und Zuständigkeiten. Alle Nummern sind Beispielwerte.")

    body_tab, request_tab = st.tabs([":material/data_object: JSON (Kundenauftrag)",
                                     ":material/send: HTTP-Aufruf"])
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    with body_tab:
        st.code(json_text, language="json")
    with request_tab:
        st.code(sap_mapping.http_request(payload), language="http")
    st.download_button("JSON herunterladen", json_text, icon=":material/download:", mime="application/json",
                       file_name=f"kundenauftrag_{order.order_id or 'beispiel'}.json", disabled=bool(missing))
    st.caption("Simulation – es ist kein SAP-System angebunden. In echt antwortet SAP mit „201 Created“ und der "
               "neuen Kundenauftragsnummer; erst danach ginge die verbindliche Bestätigung an den Kunden. Die Demo "
               "bestätigt im Chat vereinfacht schon beim Speichern – mit der Auftragsnummer der App.")

    with st.expander("Was SAP danach selbst macht – und die klassische Alternative", icon=":material/info:"):
        st.markdown(
            "- **Preisfindung** über die Konditionstechnik (Preise je Vertriebsweg, Kunde, Artikel)\n"
            "- **Leergut:** Positionen für Kästen und Fässer über Leergutstücklisten (Getränke-Branchenlösung)\n"
            "- **Verfügbarkeitsprüfung:** Ist genug Ware da, um zum Wunschtermin zu liefern?\n"
            "- **Kreditlimitprüfung** und die **Auftragsbestätigung** an den Kunden\n"
            "- Danach der übliche Ablauf im Vertrieb: **Lieferung → Warenausgang → Rechnung** (Order-to-Cash)\n\n"
            "**Alternative IDoc (ORDERS05):** Der klassische Weg für elektronischen Datenaustausch in SAP – ein "
            "festes Nachrichtenformat, oft über eine Middleware. Für neue Anbindungen an S/4HANA empfiehlt SAP "
            "die veröffentlichten Standard-APIs („Clean Core“: keine Eigenentwicklung im Kern)."
        )
    st.page_link("pages/order_entry.py", label="Selbst einen Auftrag erfassen und hier übergeben",
                 icon=":material/arrow_forward:")
