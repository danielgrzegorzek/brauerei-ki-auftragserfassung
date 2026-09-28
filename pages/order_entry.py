"""KI-Auftragserfassung: Nachricht → KI-Ergebnis → Abgleich → Prüfung → Bestätigung durch den Menschen.

Zwei Reiter:
- Live-Chat:   Messenger-Ansicht mit Live-KI und Rückfall auf den Demo-Modus (ui_chat.py)
- Posteingang: die 7 Beispielnachrichten aus WhatsApp, E-Mail und Telefon
Gemeinsame Bausteine (Auftragsvorschlag, Kontingent, Schlüssel) stehen in ui_capture.py.
"""

from contextlib import closing
from datetime import date

import pandas as pd
import streamlit as st

import ui
import ui_capture as capture_ui
import ui_chat
from src import ai_usage
from src.database import get_connection
from src.demo_messages import DEMO_MESSAGES
from src.extraction import (
    MODEL, MODELS, ClaudeExtractor, DemoExtractor, ExtractionError, IncomingMessage, OrderExtractor,
)
from src.formatting import format_date, format_eur
from src.master_data import ORDER_CHANNELS
from src.order_capture import captured_orders, delete_captured_orders

CHANNEL_ICONS = {"WhatsApp": ":material/chat:", "E-Mail": ":material/mail:", "Telefon": ":material/call:"}
CUSTOM = "custom"  # Auswahl „Eigene Nachricht schreiben“ (nur im Live-Modus)


def inbox_extract(extractor: OrderExtractor, message: IncomingMessage, source_key: tuple, live: bool) -> None:
    """Nachricht aus dem Posteingang auswerten lassen und als Entwurf merken."""
    try:
        if live:
            capture_ui.register_live_call()
            with st.spinner(f"{MODELS[MODEL].name} liest die Nachricht …"):
                result = extractor.extract(message, capture_ui.today())
        else:
            result = extractor.extract(message, capture_ui.today())
    except ExtractionError as error:
        st.session_state.inbox_capture = None
        st.session_state.inbox_error = str(error)
        return
    st.session_state.inbox_capture = capture_ui.new_capture(result, message, source_key)


def inbox_saved(order_id: int, customer_name: str, delivery_date: date, net_total: float) -> None:
    st.session_state.inbox_capture = None
    st.session_state.inbox_saved = (
        f"Auftrag **{order_id}** für **{customer_name}** gespeichert – {format_eur(net_total)} netto, "
        f"Lieferung am {format_date(delivery_date)}. Er erscheint jetzt auch im Dashboard."
    )


def inbox_view() -> None:
    # Zwei Karten nebeneinander: Liste links, Details rechts (Fiori „Flexible Column Layout“)
    left, right = st.columns([2, 3], gap="medium")

    with left, st.container(key="card-inbox"):
        st.subheader("Posteingang")
        secret_key = capture_ui.api_key()
        mode = st.segmented_control(
            "Modus", ["Demo", "KI live"], default="Demo", required=True, key="inbox_mode",
            help=f"Demo: vorbereitete KI-Ergebnisse, kostenlos. KI live: {MODELS[MODEL].name} wertet die "
                 "Nachricht wirklich aus – auch eigene Texte.",
        )
        live = mode == "KI live" and secret_key is not None
        if mode == "KI live" and secret_key is None:
            st.warning("Für den Live-Modus ist kein API-Schlüssel hinterlegt – es läuft der Demo-Modus.",
                       icon=":material/key_off:")

        options = list(range(len(DEMO_MESSAGES))) + ([CUSTOM] if live else [])
        choice = st.radio(
            "Nachricht auswählen", options, key="inbox_choice",
            format_func=lambda o: ":material/edit: Eigene Nachricht schreiben" if o == CUSTOM
            else f"{CHANNEL_ICONS[DEMO_MESSAGES[o].channel]} {DEMO_MESSAGES[o].title}",
        )
        if choice == CUSTOM:
            text = st.text_area("Nachricht", max_chars=ai_usage.MAX_MESSAGE_LENGTH, height=150,
                                placeholder="z. B.: Servus, bräucht bis Samstag 3 Fass Weizen und 8 Kistn Radler. "
                                            "Gruß, Hans")
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
            session_left, day_left = capture_ui.live_calls_left()
            reason = capture_ui.live_limit_reason(message.text)
            if st.button("Mit Claude auswerten", type="primary", icon=":material/bolt:", width="stretch",
                         disabled=reason is not None):
                inbox_extract(ClaudeExtractor(capture_ui.claude_client(secret_key)), message, source_key, live=True)
                st.rerun()  # Seite neu zeichnen, damit die Zähler unten schon den neuen Stand zeigen
            if reason and message.text.strip():
                st.caption(f"⚠️ {reason}")
            st.caption(
                f"**KI live** mit {MODELS[MODEL].name}: Eine Auswertung kostet weniger als 1 US-Cent. Zum Schutz "
                f"vor hohen Kosten: in diesem Besuch noch {session_left}, heute insgesamt noch {day_left} "
                "Live-Auswertungen."
            )
        else:
            if st.button("Mit KI auswerten", type="primary", icon=":material/smart_toy:", width="stretch"):
                inbox_extract(DemoExtractor(), message, source_key, live=False)
            st.caption(
                "**Demo-Modus:** Das KI-Ergebnis ist vorbereitet und hat genau das Format, das die echte KI liefert. "
                "Alles danach – Abgleich, Prüfung, Speichern – läuft live. Im Modus **KI live** wertet Claude "
                "die Nachrichten wirklich aus – auch eigene Texte."
            )

    with right, st.container(key="card-proposal"):
        st.subheader("Auftragsvorschlag")
        saved = st.session_state.pop("inbox_saved", None)
        if saved:
            st.success(saved, icon=":material/check_circle:")
        error = st.session_state.pop("inbox_error", None)
        if error:
            st.error(error, icon=":material/error:")
        capture = st.session_state.get("inbox_capture")
        if capture is None or capture.get("source_key") != source_key:
            # Leerzustand wie die Fiori-„Illustrated Message“
            ui.illustrated_message("empty_inbox", "Noch keine Nachricht ausgewertet",
                                   "Wähle links eine Nachricht und lass sie von der KI auswerten.")
        else:
            capture_ui.show_proposal(capture, "inbox_", inbox_saved)


# ================= Seitenaufbau =================

ui.page_header("KI-Auftragserfassung",
               "Freitext rein, sauberer Auftrag raus – die KI schlägt vor, der Mensch prüft und bestätigt.",
               "message")

chat_tab, inbox_tab = st.tabs([":material/smartphone: Live-Chat", ":material/inbox: Posteingang (7 Beispiele)"])
with chat_tab:
    ui_chat.chat_view()
with inbox_tab:
    inbox_view()

with st.container(key="card-captured"):
    st.subheader("Erfasste Aufträge")
    with closing(get_connection()) as conn:
        saved_orders = captured_orders(conn)
    if saved_orders:
        table = pd.DataFrame(saved_orders, columns=["Auftrag", "Kunde", "Liefertermin", "Kanal", "Positionen", "Netto"])
        table["Liefertermin"] = [format_date(date.fromisoformat(day)) for day in table["Liefertermin"]]
        st.dataframe(table, hide_index=True,
                     column_config={"Netto": capture_ui.EURO, "Auftrag": st.column_config.NumberColumn(format="%d")})
        if st.button("Demo zurücksetzen", icon=":material/restart_alt:",
                     help="Löscht alle hier erfassten Aufträge. Die simulierte Historie bleibt erhalten."):
            with closing(get_connection()) as conn:
                delete_captured_orders(conn)
            st.cache_data.clear()
            st.rerun()
    else:
        st.caption("Noch keine Aufträge erfasst.")
    st.caption("In der Online-Demo werden erfasste Aufträge beim Neustart der App zurückgesetzt.")
