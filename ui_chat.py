"""Messenger-Ansicht der Auftragserfassung: ein Handy im Chat-Stil mit Live-KI.

Ablauf einer Nachricht:
1. Absenden (Callback) → die Nachricht erscheint rechts im Chat, die Brauerei „schreibt …“
2. Auswertung: Live-KI, wenn Schlüssel und Kontingent es erlauben – sonst Demo-Modus
3. Antwort der Brauerei aus dem Prüfergebnis (src/chat.py), bei Rückfragen mit Schnellantworten
4. Rechts entsteht der Auftrag Schritt für Schritt; der Mensch prüft, ändert und bestätigt
"""

import html
import time
from contextlib import closing
from dataclasses import replace
from datetime import date

import streamlit as st

import ui
import ui_capture as capture_ui
from src import ai_usage, chat
from src.chat import BREWERY, CUSTOMER, NOTICE, ChatMessage, QuickReply
from src.database import get_connection
from src.demo_messages import CHAT_EXAMPLES, DEMO_MESSAGES, INJECTION_EXAMPLE, DemoMessage
from src.extraction import MODEL, MODELS, ClaudeExtractor, DemoExtractor, ExtractionError, IncomingMessage
from src.formatting import format_date, format_eur
from src.order_capture import check_order

EXAMPLE_ICONS = {
    "Dialekt": ":material/record_voice_over:",
    "Tippfehler": ":material/pin:",
    "Volksfest": ":material/celebration:",
    INJECTION_EXAMPLE.title: ":material/gpp_maybe:",
}
DEMO_TEXTS = {message.text for message in DEMO_MESSAGES + CHAT_EXAMPLES}  # dafür gibt es vorbereitete Ergebnisse
DEMO_TYPING_SECONDS = 0.8  # auch im Demo-Modus kurz „schreibt …“ zeigen, sonst kommt die Antwort unnatürlich schnell
INJECTION_EXPLANATION = (
    "**So wehrt die App den Angriff ab:** Die KI übersetzt nur in ein festes Format – Preise, Rabatte oder "
    "„Auftrag bestätigen“ gibt es darin gar nicht. Der Code erkennt die Anweisungen und warnt, die Prüfung "
    "blockiert unrealistische Mengen, und gespeichert wird erst nach Freigabe durch einen Menschen."
)


# ---------- Zustand des Chats (st.session_state) ----------

def clock() -> str:
    return chat.now_berlin().strftime("%H:%M")


def add(role: str, text: str, quick_replies: list[QuickReply] | None = None) -> None:
    st.session_state.chat.append(ChatMessage(role, text, clock(), quick_replies or []))


def init_state() -> None:
    if "chat" not in st.session_state:
        st.session_state.chat = [ChatMessage(NOTICE, chat.PRIVACY_NOTICE, ""),
                                 ChatMessage(BREWERY, chat.WELCOME, clock())]
    if "chat_persona" not in st.session_state:
        st.session_state.chat_persona = next(iter(chat.PERSONAS))


def reset() -> None:
    for key in ("chat", "chat_capture", "chat_example", "chat_pending", "chat_saved"):
        st.session_state.pop(key, None)
    st.session_state.chat_input = ""


def brewery_reply(capture: dict) -> chat.Reply:
    with closing(get_connection()) as conn:
        return chat.reply_for_draft(conn, capture["extracted"], capture["draft"], capture_ui.today(),
                                    capture["answered"], capture["safety"])


# ---------- Callbacks: laufen vor dem Neuzeichnen der Seite ----------

def use_example(example: DemoMessage) -> None:
    """Beispielvorschlag ins Eingabefeld übernehmen und passenden Absender wählen."""
    st.session_state.chat_input = example.text
    st.session_state.chat_persona = next(label for label, sender in chat.PERSONAS.items()
                                         if sender == example.sender)
    st.session_state.chat_example = example.title


def send() -> None:
    """Nachricht absenden: sofort im Chat zeigen, die Auswertung folgt beim Neuzeichnen."""
    text = (st.session_state.get("chat_input") or "").strip()
    if not text:
        return
    add(CUSTOMER, text)
    st.session_state.chat_pending = IncomingMessage(text, chat.PERSONAS[st.session_state.chat_persona], "WhatsApp")


def choose(choice: QuickReply) -> None:
    """Schnellantwort: Artikel im Entwurf setzen (ohne KI) und neu antworten."""
    add(CUSTOMER, choice.label)
    capture = st.session_state.chat_capture
    _, products = capture_ui.master_data()
    # Auf dem aktuellen Stand aufbauen – Änderungen des Menschen im Formular bleiben erhalten
    table = capture.get("current_df", capture["lines_df"]).copy()
    if choice.line_index in table.index:
        table.loc[choice.line_index, "Artikel"] = products[choice.product_id]["name"]
    draft = chat.apply_quick_reply(capture["draft"], choice)
    customer_id = capture.get("current_customer", draft.customer_id)
    draft = replace(draft, customer_id=customer_id,
                    delivery_date=capture.get("current_date", draft.delivery_date),
                    customer_hints=draft.customer_hints if customer_id == draft.customer_id else [])
    capture.update(draft=draft, lines_df=table, version=capture_ui.next_version(),
                   answered=capture["answered"] | {choice.line_index})
    reply = brewery_reply(capture)
    add(BREWERY, reply.text, reply.quick_replies)


def order_saved(order_id: int, customer_name: str, delivery_date: date, net_total: float) -> None:
    """Erst jetzt – nach der Freigabe durch den Menschen – bestätigt die Brauerei verbindlich."""
    add(BREWERY, chat.confirmation_text(order_id, delivery_date))
    st.session_state.chat_capture = None
    st.session_state.chat_saved = (
        f"Auftrag **{order_id}** für **{customer_name}** gespeichert – {format_eur(net_total)} netto, "
        f"Lieferung am {format_date(delivery_date)}. Die Bestätigung steht im Chat, der Auftrag im Dashboard."
    )


# ---------- Auswertung mit Rückfall auf den Demo-Modus ----------

def process(message: IncomingMessage, live: bool) -> None:
    result = None
    if live:
        reason = capture_ui.live_limit_reason(message.text)
        if reason:  # Kontingent erschöpft → freundlicher Hinweis, weiter im Demo-Modus
            add(NOTICE, reason)
            live = False
        else:
            capture_ui.register_live_call()
            try:
                result = ClaudeExtractor(capture_ui.claude_client(capture_ui.api_key())).extract(
                    message, capture_ui.today())
            except ExtractionError as error:
                add(NOTICE, f"Die Live-KI ist gerade nicht erreichbar: {error}")
                live = False
    if result is None and not live:
        if message.text in DEMO_TEXTS:
            time.sleep(DEMO_TYPING_SECONDS)
            result = DemoExtractor().extract(message, capture_ui.today())
        else:
            add(NOTICE, chat.DEMO_ONLY_NOTICE)
    if result is not None:
        capture = capture_ui.new_capture(result, message)
        capture["animate"] = True
        st.session_state.chat_capture = capture
        reply = brewery_reply(capture)
        add(BREWERY, reply.text, reply.quick_replies)


# ---------- Anzeige ----------

def bubble(message: ChatMessage) -> str:
    """Eine Sprechblase als HTML – Text immer maskiert (html.escape), damit kein fremdes HTML durchkommt."""
    text = html.escape(message.text).replace("\n", "<br>").replace("$", "&#36;")
    if message.role == NOTICE:
        return f'<div class="chat-notice">{text}</div>'
    side = "out" if message.role == CUSTOMER else "in"
    ticks = '<span class="chat-ticks" title="gelesen">✓✓</span>' if side == "out" else ""
    return (f'<div class="chat-row {side}"><div class="chat-bubble {side}">{text}'
            f'<span class="chat-meta">{message.time}{ticks}</span></div></div>')


def phone_html(messages: list[ChatMessage], typing: bool) -> str:
    rows = [bubble(message) for message in messages]
    if typing:
        rows.append('<div class="chat-row in"><div class="chat-bubble in chat-typing" title="schreibt …">'
                    '<span></span><span></span><span></span></div></div>')
    status = "schreibt …" if typing else "Bestellservice · online"
    # Neueste Nachricht unten: Der Verlauf steht in einem Container mit „column-reverse“ –
    # so zeigt der Chat ohne JavaScript immer das Ende des Verlaufs.
    return (f'<div class="chat-header"><img src="{ui.svg_uri("logo_icon")}" alt="">'
            f'<div><strong>Bräu am Stein</strong><span>{status}</span></div></div>'
            f'<div class="chat-scroll"><div class="chat-list">{"".join(rows)}</div></div>')


def mode_info(key: str | None, session_left: int, day_left: int) -> bool:
    """Kennzeichen Live-KI / Demo-Modus – gibt zurück, ob die Live-KI verwendet wird."""
    available = key is not None and session_left > 0 and day_left > 0
    live = available and st.toggle("Live-KI verwenden", value=True, key="chat_live",
                                   help="Aus: vorbereitete Ergebnisse der Beispielvorschläge, ohne Kosten.")
    if live:
        st.badge(f"Live-KI · {MODELS[MODEL].name}", icon=":material/bolt:", color="green")
    else:
        st.badge("Demo-Modus", icon=":material/science:", color="gray")
        if key is None:
            st.caption("Kein API-Schlüssel hinterlegt – die Beispielvorschläge liefern vorbereitete KI-Ergebnisse "
                       "im selben Format wie die Live-KI.")
        elif not available:
            st.caption("Das Live-Kontingent ist aufgebraucht – die Beispielvorschläge funktionieren weiterhin.")
    return live


def chat_view() -> None:
    init_state()
    key = capture_ui.api_key()
    session_left, day_left = capture_ui.live_calls_left()
    left, right = st.columns([2, 3], gap="medium")

    with left, st.container(key="card-chat"):
        st.subheader("Bestellung per Messenger")
        live = mode_info(key, session_left, day_left)

        st.markdown("**Beispiel ausprobieren** – oder selbst eine Bestellung schreiben:")
        with st.container(horizontal=True, key="chat-examples"):
            for example in CHAT_EXAMPLES:
                st.button(example.title, icon=EXAMPLE_ICONS[example.title], key=f"example_{example.title}",
                          on_click=use_example, args=(example,))
        chosen = next((e for e in CHAT_EXAMPLES if e.title == st.session_state.get("chat_example")), None)
        if chosen is INJECTION_EXAMPLE:
            st.info(INJECTION_EXPLANATION, icon=":material/shield:")
        elif chosen:
            st.caption(f"**{chosen.title}:** {chosen.shows}")
        st.selectbox("Du schreibst als", list(chat.PERSONAS), key="chat_persona")

        with st.container(key="phone"):
            pending = st.session_state.pop("chat_pending", None)
            ui.raw_html(phone_html(st.session_state.chat, typing=pending is not None))
            if pending is not None:
                process(pending, live)
                st.rerun()  # neu zeichnen: Antwort im Chat, Auftrag rechts
            last = st.session_state.chat[-1]
            if last.role == BREWERY and last.quick_replies and st.session_state.get("chat_capture"):
                with st.container(horizontal=True, key="quick-replies"):
                    for number, choice in enumerate(last.quick_replies):
                        st.button(choice.label, key=f"quick_{len(st.session_state.chat)}_{number}",
                                  on_click=choose, args=(choice,))
            st.chat_input("Nachricht schreiben …", key="chat_input", max_chars=ai_usage.MAX_MESSAGE_LENGTH,
                          on_submit=send)

        if live:
            st.caption(f"Kostenschutz: in diesem Besuch noch {session_left}, heute insgesamt noch {day_left} "
                       "Live-Auswertungen. Eine Auswertung kostet weniger als 1 US-Cent.")
        st.button("Chat neu starten", icon=":material/restart_alt:", on_click=reset, key="chat_reset")

    with right, st.container(key="card-chat-order"):
        st.subheader("Auftrag entsteht")
        saved = st.session_state.pop("chat_saved", None)
        if saved:
            st.success(saved, icon=":material/check_circle:")
        capture = st.session_state.get("chat_capture")
        if capture is None:
            ui.illustrated_message("empty_inbox", "Noch keine Bestellung im Chat",
                                   "Tippe links auf einen Vorschlag oder schreib selbst eine Bestellung – "
                                   "hier entsteht dann der Auftrag.")
            return
        steps = st.empty()  # „Auftrag entsteht“ oben – wird nach der Prüfung mit dem aktuellen Stand gefüllt
        if capture["animate"]:  # nur beim ersten Anzeigen: Schritt für Schritt aufbauen
            draft = capture["draft"]
            with closing(get_connection()) as conn:
                first = check_order(conn, draft.customer_id, draft.delivery_date,
                                    [(line.product_id, line.quantity) for line in draft.lines], capture_ui.today())
            capture_ui.show_steps(steps, capture_ui.order_steps(draft.customer_id, first, capture["safety"]),
                                  animate=True)
            capture["animate"] = False
        customer_id, checked = capture_ui.show_proposal(capture, "chat_", order_saved)
        capture_ui.show_steps(steps, capture_ui.order_steps(customer_id, checked, capture["safety"]))
