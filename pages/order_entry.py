"""KI-Auftragserfassung (Demo-Modus): Nachricht → KI-Ergebnis → Abgleich → Prüfung → Bestätigung durch den Menschen."""

from contextlib import closing
from datetime import date

import pandas as pd
import streamlit as st

from src.database import get_connection
from src.demo_messages import DEMO_MESSAGES, DemoMessage
from src.formatting import format_date, format_eur
from src.order_capture import (
    ERROR, INFO, WARNING, Issue, build_draft, captured_orders, check_order, delete_captured_orders,
    load_customers, load_products, save_order,
)

CHANNEL_ICONS = {"WhatsApp": ":material/chat:", "E-Mail": ":material/mail:", "Telefon": ":material/call:"}
ISSUE_ICONS = {ERROR: "⛔", WARNING: "⚠️", INFO: "ℹ️"}
STATUS_TEXT = {ERROR: "⛔ Fehler", WARNING: "⚠️ bitte prüfen", INFO: "ℹ️ Hinweis"}
SEVERITY = [ERROR, WARNING, INFO]  # Reihenfolge: das Wichtigste zuerst
EURO = st.column_config.NumberColumn(format="euro")

today = date.today()
with closing(get_connection()) as conn:
    customers = load_customers(conn)
    products = load_products(conn)
product_names = {pid: product["name"] for pid, product in products.items()}
ids_by_name = {name: pid for pid, name in product_names.items()}


def show_issues(issues) -> None:
    """Hinweise als farbige Boxen – immer mit Symbol und Text, nie nur über die Farbe. Fehler zuerst."""
    for issue in sorted(issues, key=lambda issue: SEVERITY.index(issue.level)):
        box = {ERROR: st.error, WARNING: st.warning, INFO: st.info}[issue.level]
        box(issue.text, icon=ISSUE_ICONS[issue.level])


def evaluate(index: int) -> None:
    """„KI“-Auswertung (Demo: vorbereitetes Ergebnis) und Abgleich mit den Stammdaten."""
    extracted = DEMO_MESSAGES[index].extract(today)
    with closing(get_connection()) as conn:
        draft = build_draft(conn, extracted)
    version = st.session_state.get("capture_version", 0) + 1
    st.session_state.capture_version = version
    st.session_state.capture = {
        "message_index": index,
        "extracted": extracted,
        "draft": draft,
        "version": version,
        # Ausgangstabelle für den Editor – bleibt unverändert, der Editor merkt sich die Änderungen selbst
        "lines_df": pd.DataFrame({
            "Text aus der Nachricht": [line.original_text for line in draft.lines],
            "Menge": [line.quantity for line in draft.lines],
            "Artikel": [product_names.get(line.product_id) for line in draft.lines],
        }),
    }


def show_proposal(capture: dict, message: DemoMessage) -> None:
    """Auftragsvorschlag: KI-Ergebnis, änderbare Felder, Prüfung und Bestätigung."""
    draft, extracted, version = capture["draft"], capture["extracted"], capture["version"]
    with st.expander("KI-Ergebnis als Rohdaten (JSON)", icon=":material/data_object:"):
        st.json(extracted.to_dict())
        st.caption("Genau dieses Format liefert die KI – nur „verstanden“, noch ohne Artikelnummern und Preise. "
                   "Zuordnung und Prüfung übernimmt danach normaler, getesteter Python-Code.")
    if extracted.note:
        st.info(f"KI-Hinweis zum Auftrag: {extracted.note}", icon=":material/smart_toy:")

    # 1. Kunde und Liefertermin – vom Menschen änderbar.
    # Die Versionsnummer im Schlüssel sorgt dafür, dass eine neue Auswertung frische Felder bekommt.
    customer_ids = list(customers)
    col_customer, col_date = st.columns([3, 2])
    with col_customer:
        customer_id = st.selectbox(
            "Kunde", customer_ids,
            index=customer_ids.index(draft.customer_id) if draft.customer_id else None,
            format_func=lambda cid: f"{customers[cid]['name']} · {customers[cid]['city']} ({cid})",
            placeholder="Kunden auswählen …",
            key=f"customer_{version}",
        )
        if customer_id:
            st.caption(f"Kundengruppe: {customers[customer_id]['group']}")
    with col_date:
        delivery_date = st.date_input("Liefertermin", value=draft.delivery_date, format="DD.MM.YYYY",
                                      key=f"date_{version}")
        if extracted.delivery_date_text:
            st.caption(f"In der Nachricht: „{extracted.delivery_date_text}“")
    if customer_id == draft.customer_id:  # Abgleich-Hinweise nur, solange die Zuordnung unverändert ist
        show_issues(draft.customer_hints)

    # 2. Positionen – bearbeitbare Tabelle
    st.markdown("##### Positionen")
    edited = st.data_editor(
        capture["lines_df"],
        key=f"lines_{version}",
        num_rows="dynamic",  # Zeilen hinzufügen und löschen erlaubt
        hide_index=True,
        disabled=["Text aus der Nachricht"],
        placeholder="– bitte wählen –",
        column_config={
            "Menge": st.column_config.NumberColumn(min_value=0, step=1, format="%d", width="small"),
            "Artikel": st.column_config.SelectboxColumn(options=list(product_names.values()), width="medium"),
        },
    )
    rows = edited.to_dict("records")
    lines = []
    for row in rows:
        product_id = ids_by_name.get(row["Artikel"])
        quantity = 0 if pd.isna(row["Menge"]) else int(row["Menge"])
        if product_id is None and quantity == 0 and not isinstance(row["Text aus der Nachricht"], str):
            continue  # neu hinzugefügte, noch leere Zeile ignorieren
        lines.append((product_id, quantity))

    # Hinweise aus dem Abgleich – nur für Positionen, deren Artikel der Mensch nicht geändert hat
    for position, (line, row) in enumerate(zip(draft.lines, rows), start=1):
        if line.hints and ids_by_name.get(row["Artikel"]) == line.product_id:
            with st.expander(f"Pos. {position * 10}: „{line.original_text}“ – so hat das System zugeordnet",
                             expanded=any(hint.level != INFO for hint in line.hints)):
                for hint in line.hints:
                    st.markdown(f"{ISSUE_ICONS[hint.level]} {hint.text}")

    # 3. Prüfung – läuft bei jeder Änderung neu
    with closing(get_connection()) as conn:
        result = check_order(conn, customer_id, delivery_date, lines, today)

    st.markdown("##### Prüfung")
    st.dataframe(
        pd.DataFrame([
            {
                "Pos.": position * 10,
                "Artikel": product_names.get(line.product_id, "–"),
                "Menge": line.quantity,
                "Einzelpreis": line.unit_price,
                "Summe": line.net_value if line.unit_price else None,
                # Kurzer Status (schwerster Hinweis) – die vollständigen Texte stehen darunter
                "Status": next((STATUS_TEXT[level] for level in SEVERITY
                                if any(i.level == level for i in line.issues)), "✅ in Ordnung"),
            }
            for position, line in enumerate(result.lines, start=1)
        ]),
        hide_index=True,
        column_config={"Einzelpreis": EURO, "Summe": EURO},
    )
    line_issues = [Issue(issue.level, f"Pos. {position * 10}: {issue.text}")
                   for position, line in enumerate(result.lines, start=1) for issue in line.issues]
    show_issues(line_issues + result.issues)

    totals = st.columns(3)
    totals[0].metric("Warenwert netto", format_eur(result.net_total))
    totals[1].metric("Pfand", format_eur(result.deposit_total),
                     help="Wird bei der Lieferung berechnet und bei Rückgabe des Leerguts erstattet.")
    totals[2].metric("Gesamt netto inkl. Pfand", format_eur(result.net_total + result.deposit_total))

    # 4. Bestätigung durch den Menschen
    warnings = sum(issue.level == WARNING for issue in result.all_issues())
    if result.has_errors:
        st.caption("⛔ Bitte zuerst alle Fehler beheben – erst dann kann der Auftrag gespeichert werden.")
    elif warnings:
        st.caption(f"⚠️ {warnings} Warnung(en) – bitte prüfen. Speichern ist trotzdem möglich.")
    if st.button("Auftrag bestätigen & speichern", type="primary", icon=":material/check:",
                 disabled=result.has_errors, width="stretch"):
        with closing(get_connection()) as conn:
            order_id = save_order(conn, customer_id, delivery_date, message.channel, lines, today)
        st.cache_data.clear()  # Dashboard und Startseite sollen den neuen Auftrag sofort zeigen
        st.session_state.capture = None
        st.session_state.last_saved = (
            f"Auftrag **{order_id}** für **{customers[customer_id]['name']}** gespeichert – "
            f"{format_eur(result.net_total)} netto, Lieferung am {format_date(delivery_date)}. "
            "Er erscheint jetzt auch im Dashboard."
        )
        st.rerun()


# ================= Seitenaufbau =================

st.title("KI-Auftragserfassung")
st.caption("Freitext rein, sauberer Auftrag raus – die KI schlägt vor, der Mensch prüft und bestätigt.")

left, right = st.columns([2, 3], gap="large")

with left:
    st.subheader("Posteingang")
    index = st.radio(
        "Nachricht auswählen", range(len(DEMO_MESSAGES)),
        format_func=lambda i: f"{CHANNEL_ICONS[DEMO_MESSAGES[i].channel]} {DEMO_MESSAGES[i].title}",
    )
    message = DEMO_MESSAGES[index]
    with st.container(border=True):
        st.markdown(f"{CHANNEL_ICONS[message.channel]} **{message.channel}** · {message.sender}")
        st.markdown(message.text.replace("\n", "  \n"))  # Zeilenumbrüche der Nachricht erhalten
    st.caption(f"**Das zeigt dieses Beispiel:** {message.shows}")
    if st.button("Mit KI auswerten", type="primary", icon=":material/smart_toy:", width="stretch"):
        evaluate(index)
    st.caption(
        "**Demo-Modus:** Das KI-Ergebnis ist vorbereitet und hat genau das Format, das die echte KI liefert. "
        "Alles danach – Abgleich, Prüfung, Speichern – läuft live. Mit API-Schlüssel wertet später Claude "
        "beliebige Nachrichten aus."
    )

with right:
    st.subheader("Auftragsvorschlag")
    saved = st.session_state.pop("last_saved", None)
    if saved:
        st.success(saved, icon=":material/check_circle:")
    capture = st.session_state.get("capture")
    if capture is None or capture["message_index"] != index:
        st.info("Links eine Nachricht auswählen und auf **Mit KI auswerten** klicken.", icon=":material/arrow_back:")
    else:
        show_proposal(capture, message)

st.divider()
st.subheader("Erfasste Aufträge")
with closing(get_connection()) as conn:
    saved_orders = captured_orders(conn)
if saved_orders:
    table = pd.DataFrame(saved_orders, columns=["Auftrag", "Kunde", "Liefertermin", "Kanal", "Positionen", "Netto"])
    table["Liefertermin"] = [format_date(date.fromisoformat(day)) for day in table["Liefertermin"]]
    st.dataframe(table, hide_index=True,
                 column_config={"Netto": EURO, "Auftrag": st.column_config.NumberColumn(format="%d")})
    if st.button("Demo zurücksetzen", icon=":material/restart_alt:",
                 help="Löscht alle hier erfassten Aufträge. Die simulierte Historie bleibt erhalten."):
        with closing(get_connection()) as conn:
            delete_captured_orders(conn)
        st.cache_data.clear()
        st.rerun()
else:
    st.caption("Noch keine Aufträge erfasst.")
st.caption("In der Online-Demo werden erfasste Aufträge beim Neustart der App zurückgesetzt.")
