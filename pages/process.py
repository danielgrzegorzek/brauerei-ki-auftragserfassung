"""Prozess & SAP-Übergabe: Ist- und Soll-Prozess und der bestätigte Auftrag als Kundenauftrag für SAP S/4HANA.

Inhalt und Regeln stehen getestet in src/process.py und src/sap_mapping.py – hier nur die Anzeige.
Die Übergabe ist aufgebaut wie eine Fiori-„Object Page“ (Kopf, Reiter, Fußleiste mit Aktion) – nachgebaut mit
Streamlit und eigenem CSS. Sie ist eine Simulation: Es ist kein SAP-System angebunden, nichts wird gesendet.
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
# Zustand der Übergabe → Text und Farbe des Status im Kopf (wie der Fiori-„Object Status“)
STATUS = {
    "incomplete": ("Unvollständig", "error"),
    "ready": ("Bereit zur Übergabe", "info"),
    "simulated": ("Übergabe simuliert", "success"),
}


def swimlane(steps: list[process.ProcessStep], show_issues: bool = False) -> str:
    """Schwimmbahnen je Rolle (wie in BPMN): Schritte von links nach rechts, jede Rolle in ihrer Bahn.
    show_issues: Schwachstellen (Ist) als Warnsymbol, der Text erscheint als Tooltip.
    Auf schmalen Bildschirmen macht das CSS daraus eine nummerierte Liste mit Rollen-Etikett."""
    # lang="de": Der Browser trennt lange deutsche Wörter dann richtig („Eingangs-bestätigung“)
    parts = [f'<div class="swimlane" lang="de" style="--steps: {len(steps)}" role="list">']
    for row, lane in enumerate(process.LANES, start=1):
        parts.append(f'<div class="lane-band" style="grid-row: {row}" aria-hidden="true"></div>'
                     f'<div class="lane-label" style="grid-row: {row}" aria-hidden="true">{html.escape(lane)}</div>')
    for number, step in enumerate(steps, start=1):
        meta = [step.kind] + ([f"{format_number(step.minutes, 1)} min"] if step.minutes else []) \
            + (["Medienbruch"] if step.media_break else [])
        issue = ""
        if show_issues and step.note:
            # tabindex: Tooltip auch per Tastatur und durch Antippen auf dem Handy.
            # Screenreader lesen den Text über aria-label; der sichtbare Tooltip ist für sie ausgeblendet.
            text = html.escape(f"Schwachstelle: {step.note}")
            issue = (f'<span class="step-issue" tabindex="0" role="img" aria-label="{text}">'
                     f'<span class="step-issue-icon" aria-hidden="true">!</span>'
                     f'<span class="step-issue-tip" aria-hidden="true">{text}</span></span>')
        parts.append(
            f'<div class="step {KIND_CLASSES[step.kind]}" role="listitem" '
            f'style="grid-row: {process.LANES.index(step.lane) + 1}; grid-column: {number + 1}">'
            f'<span class="step-top"><span class="step-no">{number}</span>'
            f'<span class="step-lane">{html.escape(step.lane)}</span>{issue}</span>'
            f'<strong>{html.escape(step.title)}</strong>'
            f'<span class="step-meta">{html.escape(" · ".join(meta))}</span></div>'
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


def definition_list(fields: list[tuple[str, str]], css_class: str) -> str:
    """Bezeichnung und Wert als <dl> – für den Kopf und die Organisationsdaten."""
    rows = "".join(f"<div><dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd></div>" for label, value in fields)
    return f'<dl class="{css_class}">{rows}</dl>'


def form(groups: list[tuple[str, list[tuple[str, str]]]]) -> str:
    """Fiori-Formular im Anzeigemodus: Gruppen mit Überschrift, darunter Bezeichnung und Wert."""
    sections = "".join(
        f'<section><div class="sap-form-title" role="heading" aria-level="5">{html.escape(title)}</div>'
        f'{definition_list(fields, "sap-form-fields")}</section>'
        for title, fields in groups
    )
    return f'<div class="sap-form">{sections}</div>'


def object_header(order: sap_mapping.OrderForSap, payload: dict, status: str) -> str:
    """Kopf der Object Page: Art und Kennzeichnung, Titel mit Status, darunter die Schlüsselwerte."""
    title = f"App-Auftrag {order.order_id}" if order.order_id else "Beispielauftrag"
    label, css = STATUS[status]
    fields = [
        ("Auftraggeber", payload["SoldToParty"]),
        ("Wunschlieferdatum", format_date(order.delivery_date) if order.delivery_date else "–"),
        ("Positionen", str(len(payload["to_Item"]))),
        ("Vertriebsbereich", " / ".join((payload["SalesOrganization"], payload["DistributionChannel"] or "–",
                                         payload["OrganizationDivision"]))),
    ]
    if order.net_value:  # nur gespeicherte Aufträge haben einen Nettowert aus der App
        fields.append(("Erwarteter Nettowert", format_eur(order.net_value)))
    return (
        '<div class="sap-op-overline">Kundenauftrag · Simulation, kein SAP-Produkt</div>'
        '<div class="sap-op-titlebar"><div>'
        f'<div class="sap-op-title" role="heading" aria-level="4">{html.escape(title)}</div>'
        f'<div class="sap-op-subtitle">{html.escape(order.customer_name)} · {html.escape(order.customer_group)}</div>'
        f'</div><span class="sap-status {css}">{html.escape(label)}</span></div>'
        + definition_list(fields, "sap-op-attributes")
    )


def simulate(handover: tuple) -> None:
    """„Übergabe simulieren“: nur merken, welcher Auftrag mit welchem Inhalt – gesendet wird nichts."""
    st.session_state.sap_simulated = handover


@st.fragment
def sap_handover() -> None:
    """Übergabe an SAP als Object Page. Als Fragment: Auftragswahl und Aktion laden nur diesen Teil neu."""
    st.subheader("Übergabe an SAP S/4HANA", anchor=False)
    options, labels = order_options()
    preselect = st.session_state.pop("sap_order_id", None)
    if preselect in options:  # gerade in der Auftragserfassung gespeichert → gleich diesen zeigen
        st.session_state.sap_choice = preselect
    elif st.session_state.get("sap_choice") not in options:  # z. B. nach Neustart der App nicht mehr vorhanden
        st.session_state.pop("sap_choice", None)
    with st.container(key="sap-toolbar", horizontal=True, vertical_alignment="bottom"):
        choice = st.selectbox("Auftrag", options, format_func=labels.get, key="sap_choice", persist_state="session",
                              width=460, help="Das Beispiel oder in der KI-Auftragserfassung bestätigte Aufträge.")
        st.page_link("pages/order_entry.py", label="Eigenen Auftrag erfassen", icon=":material/add:")

    with closing(get_connection()) as conn:
        order = (sap_mapping.example_order(conn, capture_ui.today()) if choice == EXAMPLE
                 else sap_mapping.load_order(conn, choice))
    payload = sap_mapping.sales_order_payload(order)
    missing = sap_mapping.missing_fields(payload)
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    # Auswahl UND Inhalt merken: Nach „Demo zurücksetzen“ vergibt die App Auftragsnummern neu –
    # ein anderer Auftrag mit derselben Nummer gilt dann nicht als schon übergeben
    handover = (choice, json_text)
    status = ("incomplete" if missing else
              "simulated" if st.session_state.get("sap_simulated") == handover else "ready")
    _, products = capture_ui.master_data()
    product_names = {pid: product["name"] for pid, product in products.items()}

    with st.container(key="card-sap"):
        ui.raw_html(object_header(order, payload, status))
        items_tab, org_tab, mapping_tab, payload_tab = st.tabs([
            ":material/list: Positionen", ":material/domain: Organisationsdaten",
            ":material/swap_horiz: Feld-Mapping", ":material/data_object: Nutzdaten (JSON)"])

        with items_tab:
            items = pd.DataFrame([{"Pos.": item["SalesOrderItem"], "Material": item["Material"],
                                   "Bezeichnung": product_names.get(item["Material"], ""),
                                   "Menge": int(item["RequestedQuantity"]), "ME": item["RequestedQuantityUnit"]}
                                  for item in payload["to_Item"]])
            if items.empty:
                st.caption("Keine Positionen.")
            else:
                st.dataframe(items, hide_index=True)

        with org_tab:
            ui.raw_html(form([
                ("Vertriebsbereich", [
                    ("Verkaufsorganisation", payload["SalesOrganization"]),
                    ("Vertriebsweg", f"{payload['DistributionChannel'] or '–'} · {order.customer_group}"),
                    ("Sparte", payload["OrganizationDivision"])]),
                ("Auftrag", [
                    ("Verkaufsbelegart", f"{payload['SalesOrderType']} · Terminauftrag"),
                    ("Bestellnummer des Kunden", payload["PurchaseOrderByCustomer"]),
                    ("Wunschlieferdatum", format_date(order.delivery_date) if order.delivery_date else "–")]),
                ("Partner", [
                    ("Auftraggeber", f"{payload['SoldToParty']} · {order.customer_name}")]),
            ]))
            with st.expander("SAP-Begriffe kurz erklärt", icon=":material/help:"):
                st.markdown(
                    "- **Vertriebsbereich** = Verkaufsorganisation + Vertriebsweg + Sparte – bestimmt in SAP u. a. "
                    "Preislisten und Zuständigkeiten.\n"
                    "- **Verkaufsorganisation:** wer verkauft (hier: Bräu am Stein Inland).\n"
                    "- **Vertriebsweg:** wie die Ware zum Kunden kommt – abgeleitet aus der Kundengruppe.\n"
                    "- **Sparte:** Produktbereich; 00 = spartenübergreifend.\n"
                    "- **Auftraggeber:** der Geschäftspartner in SAP; den Warenempfänger ermittelt SAP selbst.\n\n"
                    "Alle Nummern sind Beispielwerte eines fiktiven Systems."
                )

        with mapping_tab:
            mapping = sap_mapping.field_mapping(order, payload, product_names)
            # Statische Tabelle statt st.dataframe: bricht lange Werte um, statt sie abzuschneiden
            st.table(pd.DataFrame(mapping).drop(columns="Erklärung"), hide_index=True, border="horizontal")
            with st.expander("Erklärungen zu den Feldern", icon=":material/help:"):
                st.markdown("\n".join(f"- **{row['SAP-Begriff']}** (`{row['SAP-Feld']}`): {row['Erklärung']}"
                                      for row in mapping))

        with payload_tab:
            st.code(json_text, language="json")
            with st.expander("HTTP-Aufruf an API_SALES_ORDER_SRV", icon=":material/send:"):
                st.code(sap_mapping.http_request(payload), language="http")
            with st.expander("Was SAP danach selbst macht", icon=":material/info:"):
                st.markdown(
                    "- **Preisfindung** über die Konditionstechnik (Preise je Vertriebsweg, Kunde, Artikel)\n"
                    "- **Leergut:** Positionen für Kästen und Fässer über Leergutstücklisten (Getränke-Branchenlösung)\n"
                    "- **Verfügbarkeitsprüfung, Kreditlimitprüfung** und die **Auftragsbestätigung** an den Kunden\n"
                    "- Danach: **Lieferung → Warenausgang → Rechnung** (Order-to-Cash)\n\n"
                    "Die Demo bestätigt im Chat vereinfacht schon beim Speichern – in echt erst nach der Antwort von "
                    "SAP. **Alternative IDoc (ORDERS05):** der klassische Weg für elektronischen Datenaustausch; für "
                    "neue Anbindungen an S/4HANA empfiehlt SAP die Standard-APIs („Clean Core“)."
                )

        # Fußleiste wie bei Fiori: links das Ergebnis als Message Strip, rechts die Aktionen
        with st.container(key="sap-footer", horizontal=True, vertical_alignment="center"):
            if status == "incomplete":
                st.error(f"Unvollständig – es fehlt: {', '.join(missing)}.", icon=":material/error:")
            elif status == "simulated":
                st.success("Übergabe simuliert: SAP würde mit „201 Created“ antworten. Gesendet wurde nichts.",
                           icon=":material/check_circle:")
            else:
                positions = "1 Position" if len(order.lines) == 1 else f"{len(order.lines)} Positionen"
                st.info(f"Vollständig: {positions} für {order.customer_name}. Noch nichts übergeben.",
                        icon=":material/info:")
            st.download_button("JSON herunterladen", json_text, icon=":material/download:", mime="application/json",
                               file_name=f"kundenauftrag_{order.order_id or 'beispiel'}.json",
                               disabled=bool(missing), on_click="ignore")
            st.button("Übergabe simulieren", type="primary", icon=":material/send:", key="sap_simulate",
                      on_click=simulate, args=(handover,), disabled=bool(missing))


# ================= Seitenaufbau =================

ui.page_header("Prozess & SAP-Übergabe",
               "Wie eine Bestellung heute läuft, wie sie mit KI läuft – und wie sie als Kundenauftrag in SAP ankommt.",
               "process")

# 1. Vorher → nachher, nur als Kennzahlen (Details im Fragezeichen)
before, after = process.figures(process.AS_IS), process.figures(process.TO_BE)
with st.container(key="process-kpis"):  # CSS: unter 1100 px 2 × 2 statt vier gequetschter Spalten
    tiles = st.columns(4)
tiles[0].metric("Manuelle Schritte je Auftrag", f"{before.manual_steps} → {after.manual_steps}", border=True)
tiles[1].metric("Arbeitszeit je Auftrag", f"{format_number(before.minutes)} → {format_number(after.minutes)} min",
                border=True,
                help=f"Dieselben Annahmen wie im Business Case, für Bestellungen per {' und '.join(DEFAULT_CHANNELS)}. "
                     f"Bei Anrufen schreibt weiterhin jemand mit – rund {format_number(DEFAULTS['minutes_ai_phone'])} "
                     f"statt {format_number(DEFAULTS['minutes_manual'])} Minuten.")
tiles[2].metric("Medienbrüche", f"{before.media_breaks} → {after.media_breaks}", border=True,
                help="Stellen, an denen jemand Informationen von einem System ins andere überträgt.")
tiles[3].metric("Erste Rückmeldung", "Std. → Sek.", border=True,
                help="Sekunden statt Stunden: Eingangsbestätigung oder Rückfrage an den Kunden im Chat – verbindlich "
                     "wird es nach der Freigabe.")

# 2. Ablauf als Schwimmbahnen
with st.container(key="card-process-flow"):
    st.subheader("Ablauf – heute und mit KI", anchor=False)
    as_is_tab, to_be_tab = st.tabs([":material/history: Heute (Ist)", ":material/auto_awesome: Mit KI (Soll)"])
    with as_is_tab:
        ui.raw_html(swimlane(process.AS_IS, show_issues=True))
    with to_be_tab:
        ui.raw_html(swimlane(process.TO_BE))

# 3. Übergabe an SAP S/4HANA
sap_handover()
