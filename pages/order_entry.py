"""KI-Auftragserfassung: Nachricht → KI-Ergebnis → Abgleich → Prüfung → Bestätigung durch den Menschen.

Zwei Modi: Demo (vorbereitete Ergebnisse, kostenlos) und KI live (Claude Sonnet 5, mit Kostenschutz).
"""

from contextlib import closing
from datetime import date

import anthropic
import pandas as pd
import streamlit as st

import ui
from src import ai_usage
from src.database import get_connection
from src.demo_messages import DEMO_MESSAGES
from src.extraction import (
    MODEL, ClaudeExtractor, DemoExtractor, ExtractionError, ExtractionResult, IncomingMessage, OrderExtractor,
)
from src.formatting import format_date, format_eur, format_number
from src.master_data import ORDER_CHANNELS
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


def api_key() -> str | None:
    """API-Schlüssel aus den Secrets (lokal: .streamlit/secrets.toml, Cloud: Secrets-Verwaltung)."""
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY")
    except FileNotFoundError:  # gar keine Secrets-Datei vorhanden (z. B. frisch geklontes Repo)
        return None
    return key if key and key.startswith("sk-ant-") else None


@st.cache_resource
def claude_client(key: str) -> anthropic.Anthropic:
    """Ein API-Client für alle Besucher – mit Zeitlimit, damit die Oberfläche nicht ewig wartet."""
    return anthropic.Anthropic(api_key=key, timeout=60.0, max_retries=1)


def run_extraction(extractor: OrderExtractor, message: IncomingMessage, source_key: tuple, live: bool) -> None:
    """Nachricht auswerten lassen; bei echten KI-Aufrufen vorher zählen (Kosten entstehen auch bei Fehlern)."""
    try:
        if live:
            with closing(get_connection()) as conn:
                ai_usage.register_call(conn, today)
            st.session_state.live_calls = st.session_state.get("live_calls", 0) + 1
            with st.spinner("Claude liest die Nachricht …"):
                result = extractor.extract(message, today)
        else:
            result = extractor.extract(message, today)
    except ExtractionError as error:
        st.session_state.capture = None
        st.session_state.extraction_error = str(error)
        return
    evaluate(result, source_key)


def evaluate(result: ExtractionResult, source_key: tuple) -> None:
    """KI-Ergebnis mit den Stammdaten abgleichen und als neuen Entwurf merken."""
    extracted = result.order
    with closing(get_connection()) as conn:
        draft = build_draft(conn, extracted)
    version = st.session_state.get("capture_version", 0) + 1
    st.session_state.capture_version = version
    st.session_state.capture = {
        "source_key": source_key,  # zu welcher Auswahl (Modus + Nachricht) der Entwurf gehört
        "result": result,
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


def show_proposal(capture: dict, message: IncomingMessage) -> None:
    """Auftragsvorschlag: KI-Ergebnis, änderbare Felder, Prüfung und Bestätigung."""
    draft, extracted, version = capture["draft"], capture["extracted"], capture["version"]
    result: ExtractionResult = capture["result"]
    if result.input_tokens:  # echter KI-Aufruf: Herkunft, Verbrauch und Dauer offenlegen
        st.badge(f"Live ausgewertet von Claude · {format_number(result.seconds, 1)} s · "
                 f"ca. {format_number(result.cost_usd * 100, 2)} US-Cent", icon=":material/bolt:", color="blue")
    else:
        st.badge("Demo · vorbereitetes KI-Ergebnis", icon=":material/science:", color="gray")
    with st.expander("KI-Ergebnis als Rohdaten (JSON)", icon=":material/data_object:"):
        st.json(extracted.to_dict())
        st.caption("Genau dieses Format liefert die KI – nur „verstanden“, noch ohne Artikelnummern und Preise. "
                   "Zuordnung und Prüfung übernimmt danach normaler, getesteter Python-Code.")
        if result.input_tokens:
            st.caption(f"Quelle: {result.source} · {format_number(result.input_tokens)} Tokens rein, "
                       f"{format_number(result.output_tokens)} Tokens raus")
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
                # Kleines Symbol: Kasten oder Fass (leer, solange kein Artikel gewählt ist)
                "Gebinde": ui.image_uri("crate" if products[line.product_id]["unit"] == "Kasten" else "keg")
                           if line.product_id else None,
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
        column_config={"Einzelpreis": EURO, "Summe": EURO,
                       "Gebinde": st.column_config.ImageColumn(width="small")},
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

ui.page_header("KI-Auftragserfassung",
               "Freitext rein, sauberer Auftrag raus – die KI schlägt vor, der Mensch prüft und bestätigt.",
               "message")

# Zwei Karten nebeneinander: Liste links, Details rechts (Fiori „Flexible Column Layout“)
left, right = st.columns([2, 3], gap="medium")

CUSTOM = "custom"  # Auswahl „Eigene Nachricht schreiben“ (nur im Live-Modus)

with left, st.container(key="card-inbox"):
    st.subheader("Posteingang")
    secret_key = api_key()
    mode = st.segmented_control(
        "Modus", ["Demo", "KI live"], default="Demo", required=True,
        help="Demo: vorbereitete KI-Ergebnisse, kostenlos. KI live: Claude Sonnet 5 wertet die Nachricht "
             "wirklich aus – auch eigene Texte.",
    )
    live = mode == "KI live" and secret_key is not None
    if mode == "KI live" and secret_key is None:
        st.warning("Für den Live-Modus ist kein API-Schlüssel hinterlegt – es läuft der Demo-Modus.",
                   icon=":material/key_off:")

    options = list(range(len(DEMO_MESSAGES))) + ([CUSTOM] if live else [])
    choice = st.radio(
        "Nachricht auswählen", options,
        format_func=lambda o: ":material/edit: Eigene Nachricht schreiben" if o == CUSTOM
        else f"{CHANNEL_ICONS[DEMO_MESSAGES[o].channel]} {DEMO_MESSAGES[o].title}",
    )
    if choice == CUSTOM:
        text = st.text_area("Nachricht", max_chars=ai_usage.MAX_MESSAGE_LENGTH, height=150,
                            placeholder="z. B.: Servus, bräucht bis Samstag 3 Fass Weizen und 8 Kistn Radler. Gruß, Hans")
        sender_col, channel_col = st.columns([3, 2])
        sender = sender_col.text_input("Absender", placeholder="z. B. Gasthof Huber")
        channel = channel_col.selectbox("Kanal", ORDER_CHANNELS, index=ORDER_CHANNELS.index("WhatsApp"))
        st.caption(":material/shield: Der Text wird zur Auswertung an Anthropic (Claude-API) übertragen – "
                   "bitte keine echten Namen, Telefonnummern oder anderen personenbezogenen Daten eingeben.")
        message = IncomingMessage(text, sender, channel)
    else:
        demo = DEMO_MESSAGES[choice]
        message = IncomingMessage(demo.text, demo.sender, demo.channel)
        with st.container(key="message-bubble"):  # Nachricht als Sprechblase
            st.markdown(f"{CHANNEL_ICONS[demo.channel]} **{demo.channel}** · {demo.sender}")
            st.markdown(demo.text.replace("\n", "  \n"))  # Zeilenumbrüche der Nachricht erhalten
        st.caption(f"**Das zeigt dieses Beispiel:** {demo.shows}")
    # Zu welcher Auswahl ein Entwurf gehört – ändert sich Modus oder Text, verschwindet der alte Vorschlag
    source_key = (live, choice, message.text, message.sender, message.channel)

    if live:
        with closing(get_connection()) as conn:
            day_calls = ai_usage.calls_today(conn, today)
        session_calls = st.session_state.get("live_calls", 0)
        reason = ai_usage.limit_reason(message.text, session_calls, day_calls)
        if st.button("Mit Claude auswerten", type="primary", icon=":material/bolt:", width="stretch",
                     disabled=reason is not None):
            run_extraction(ClaudeExtractor(claude_client(secret_key)), message, source_key, live=True)
            st.rerun()  # Seite neu zeichnen, damit die Zähler unten schon den neuen Stand zeigen
        if reason and message.text.strip():
            st.caption(f"⚠️ {reason}")
        st.caption(
            f"**KI live** mit {MODEL}: Eine Auswertung kostet etwa 1 US-Cent. Zum Schutz vor hohen Kosten: "
            f"in diesem Besuch noch {max(0, ai_usage.MAX_CALLS_PER_SESSION - session_calls)}, heute insgesamt "
            f"noch {max(0, ai_usage.MAX_CALLS_PER_DAY - day_calls)} Live-Auswertungen."
        )
    else:
        if st.button("Mit KI auswerten", type="primary", icon=":material/smart_toy:", width="stretch"):
            run_extraction(DemoExtractor(), message, source_key, live=False)
        st.caption(
            "**Demo-Modus:** Das KI-Ergebnis ist vorbereitet und hat genau das Format, das die echte KI liefert. "
            "Alles danach – Abgleich, Prüfung, Speichern – läuft live. Im Modus **KI live** wertet Claude "
            "die Nachrichten wirklich aus – auch eigene Texte."
        )

with right, st.container(key="card-proposal"):
    st.subheader("Auftragsvorschlag")
    saved = st.session_state.pop("last_saved", None)
    if saved:
        st.success(saved, icon=":material/check_circle:")
    error = st.session_state.pop("extraction_error", None)
    if error:
        st.error(error, icon=":material/error:")
    capture = st.session_state.get("capture")
    if capture is None or capture.get("source_key") != source_key:
        # Leerzustand wie die Fiori-„Illustrated Message“
        ui.illustrated_message("empty_inbox", "Noch keine Nachricht ausgewertet",
                               "Wähle links eine Nachricht und lass sie von der KI auswerten.")
    else:
        show_proposal(capture, message)

with st.container(key="card-captured"):
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
