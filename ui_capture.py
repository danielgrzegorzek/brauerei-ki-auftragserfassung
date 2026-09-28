"""Oberflächen-Bausteine der Auftragserfassung – gemeinsam für den Live-Chat und den Posteingang.

Enthält: API-Schlüssel und Client, Live-Kontingent, KI-Ergebnis → Entwurf, den bearbeitbaren
Auftragsvorschlag (prüfen, bestätigen, speichern) und die Anzeige „Auftrag entsteht“ in fünf Schritten.
Die fachliche Logik steht in src/ – hier nur Anzeige und Bedienung.
"""

import html
import time
from collections.abc import Callable
from contextlib import closing
from datetime import date

import anthropic
import pandas as pd
import streamlit as st

import ui
from src import ai_usage
from src.chat import now_berlin
from src.database import get_connection
from src.extraction import ExtractionResult, IncomingMessage
from src.formatting import format_eur, format_number
from src.message_safety import instruction_warnings
from src.order_capture import (
    ERROR, INFO, WARNING, CheckResult, Draft, Issue, build_draft, check_order, load_customers, load_products,
    save_order,
)

ISSUE_ICONS = {ERROR: "⛔", WARNING: "⚠️", INFO: "ℹ️"}
STATUS_TEXT = {ERROR: "⛔ Fehler", WARNING: "⚠️ bitte prüfen", INFO: "ℹ️ Hinweis"}
SEVERITY = [ERROR, WARNING, INFO]  # Reihenfolge: das Wichtigste zuerst
EURO = st.column_config.NumberColumn(format="euro")
STEP_DELAY = 0.35  # Sekunden je Schritt beim Aufbau von „Auftrag entsteht“
STEP_ICONS = {"ok": "✓", "warn": "!", "error": "✕", "pending": "…"}


@st.cache_data
def master_data() -> tuple[dict, dict]:
    """Kunden und Artikel – ändern sich während des Betriebs nicht."""
    with closing(get_connection()) as conn:
        return load_customers(conn), load_products(conn)


def today() -> date:
    return now_berlin().date()


# ---------- Live-KI: Schlüssel, Client, Kontingent ----------

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


def live_calls_left() -> tuple[int, int]:
    """Verbleibende Live-Auswertungen: (in diesem Besuch, heute insgesamt)."""
    with closing(get_connection()) as conn:
        day_calls = ai_usage.calls_today(conn, today())
    session_calls = st.session_state.get("live_calls", 0)
    return (max(0, ai_usage.MAX_CALLS_PER_SESSION - session_calls),
            max(0, ai_usage.MAX_CALLS_PER_DAY - day_calls))


def live_limit_reason(text: str) -> str | None:
    """Warum gerade keine Live-Auswertung möglich ist – oder None."""
    with closing(get_connection()) as conn:
        day_calls = ai_usage.calls_today(conn, today())
    return ai_usage.limit_reason(text, st.session_state.get("live_calls", 0), day_calls)


def register_live_call() -> None:
    """Vor dem Aufruf zählen – Kosten entstehen auch, wenn die Antwort scheitert."""
    with closing(get_connection()) as conn:
        ai_usage.register_call(conn, today())
    st.session_state.live_calls = st.session_state.get("live_calls", 0) + 1


# ---------- KI-Ergebnis → Entwurf ----------

def lines_table(draft: Draft) -> pd.DataFrame:
    """Ausgangstabelle für den Editor – der Editor merkt sich die Änderungen des Menschen selbst."""
    _, products = master_data()
    return pd.DataFrame({
        "Text aus der Nachricht": [line.original_text for line in draft.lines],
        "Menge": [line.quantity for line in draft.lines],
        "Artikel": [products[line.product_id]["name"] if line.product_id else None for line in draft.lines],
    })


def next_version() -> int:
    """Neue Versionsnummer → neue Widget-Schlüssel → frische Eingabefelder."""
    st.session_state.capture_version = st.session_state.get("capture_version", 0) + 1
    return st.session_state.capture_version


def new_capture(result: ExtractionResult, message: IncomingMessage, source_key: tuple | None = None) -> dict:
    """KI-Ergebnis mit den Stammdaten abgleichen und als neuen Entwurf zusammenstellen."""
    with closing(get_connection()) as conn:
        draft = build_draft(conn, result.order)
    return {
        "source_key": source_key,   # zu welcher Auswahl der Entwurf gehört (Posteingang)
        "result": result,
        "extracted": result.order,
        "message": message,
        "safety": instruction_warnings(message.text),  # Prüfung auf Anweisungen – unabhängig von der KI
        "draft": draft,
        "version": next_version(),
        "lines_df": lines_table(draft),
        "answered": set(),          # per Schnellantwort geklärte Positionen (Chat)
        "animate": False,           # „Auftrag entsteht“ einmal Schritt für Schritt zeigen (Chat)
    }


# ---------- Anzeige ----------

def show_issues(issues: list[Issue]) -> None:
    """Hinweise als farbige Boxen – immer mit Symbol und Text, nie nur über die Farbe. Fehler zuerst."""
    for issue in sorted(issues, key=lambda issue: SEVERITY.index(issue.level)):
        box = {ERROR: st.error, WARNING: st.warning, INFO: st.info}[issue.level]
        box(issue.text, icon=ISSUE_ICONS[issue.level])


def order_steps(customer_id: str | None, result: CheckResult,
                extra_issues: list[Issue] = ()) -> list[tuple[str, str, str]]:
    """Die fünf Schritte „Auftrag entsteht“ als (Zustand, Bezeichnung, Wert).
    extra_issues: weitere Hinweise außerhalb der Prüfung, z. B. die Sicherheitswarnung."""
    customers, _ = master_data()
    issues = result.all_issues() + list(extra_issues)
    errors = sum(issue.level == ERROR for issue in issues)
    warnings = sum(issue.level == WARNING for issue in issues)
    assigned = sum(line.product_id is not None for line in result.lines)
    all_assigned = bool(result.lines) and assigned == len(result.lines)
    return [
        ("ok" if customer_id else "error", "Kunde",
         customers[customer_id]["name"] if customer_id else "nicht im Kundenstamm"),
        ("ok" if all_assigned else "warn", "Positionen", f"{assigned} von {len(result.lines)} zugeordnet"),
        ("error" if errors else "warn" if warnings else "ok", "Prüfung",
         f"{errors} Fehler · {warnings} Warnungen" if errors or warnings else "alles in Ordnung"),
        ("ok", "Pfand", format_eur(result.deposit_total)),
        ("error" if errors else "ok", "Summe inkl. Pfand",
         format_eur(result.net_total + result.deposit_total) + (" · gesperrt" if errors else "")),
    ]


def steps_html(steps: list[tuple[str, str, str]], shown: int) -> str:
    """Fortschrittsleiste wie der Fiori-„Process Flow“: die ersten `shown` Schritte fertig, der Rest offen."""
    parts = []
    for number, (state, label, value) in enumerate(steps, start=1):
        if number > shown:
            state, value = "pending", "…"
        parts.append(
            f'<div class="order-step {state}"><span class="order-step-icon" aria-hidden="true">'
            f'{STEP_ICONS[state]}</span><span class="order-step-text"><span class="order-step-label">'
            f'{number} · {html.escape(label)}</span><span class="order-step-value">{html.escape(value)}</span>'
            f'</span></div>'
        )
    return f'<div class="order-steps" role="list">{"".join(parts)}</div>'


def show_steps(placeholder, steps: list[tuple[str, str, str]], animate: bool = False) -> None:
    """Zeigt die Schritte – beim ersten Mal nacheinander, damit man sieht, wie der Auftrag entsteht."""
    if animate:
        for shown in range(1, len(steps) + 1):
            placeholder.markdown(steps_html(steps, shown), unsafe_allow_html=True)
            time.sleep(STEP_DELAY)
    else:
        placeholder.markdown(steps_html(steps, len(steps)), unsafe_allow_html=True)


def show_proposal(capture: dict, key_prefix: str,
                  on_saved: Callable[[int, str, date, float], None]) -> tuple[str | None, CheckResult]:
    """Auftragsvorschlag: KI-Ergebnis, änderbare Felder, Prüfung und Bestätigung.
    Gibt den aktuell gewählten Kunden und das Prüfergebnis zurück (für „Auftrag entsteht“)."""
    customers, products = master_data()
    product_names = {pid: product["name"] for pid, product in products.items()}
    ids_by_name = {name: pid for pid, name in product_names.items()}
    draft, extracted, version = capture["draft"], capture["extracted"], capture["version"]
    result: ExtractionResult = capture["result"]

    if result.input_tokens:  # echter KI-Aufruf: Herkunft, Verbrauch und Dauer offenlegen
        st.badge(f"Live ausgewertet von {result.source} · {format_number(result.seconds, 1)} s · "
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
    if capture["safety"]:  # Angriffsversuch: sichtbar machen und erklären
        show_issues(capture["safety"])
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
            key=f"{key_prefix}customer_{version}",
        )
        if customer_id:
            st.caption(f"Kundengruppe: {customers[customer_id]['group']}")
    with col_date:
        delivery_date = st.date_input("Liefertermin", value=draft.delivery_date, format="DD.MM.YYYY",
                                      key=f"{key_prefix}date_{version}")
        if extracted.delivery_date_text:
            st.caption(f"In der Nachricht: „{extracted.delivery_date_text}“")
    if customer_id == draft.customer_id:  # Abgleich-Hinweise nur, solange die Zuordnung unverändert ist
        show_issues(draft.customer_hints)

    # 2. Positionen – bearbeitbare Tabelle
    st.markdown("##### Positionen")
    edited = st.data_editor(
        capture["lines_df"],
        key=f"{key_prefix}lines_{version}",
        num_rows="dynamic",  # Zeilen hinzufügen und löschen erlaubt
        hide_index=True,
        disabled=["Text aus der Nachricht"],
        placeholder="– bitte wählen –",
        column_config={
            "Menge": st.column_config.NumberColumn(min_value=0, step=1, format="%d", width="small"),
            "Artikel": st.column_config.SelectboxColumn(options=list(product_names.values()), width="medium"),
        },
    )
    # Aktuellen Stand merken – eine Schnellantwort im Chat baut darauf auf, statt Änderungen zu verwerfen
    capture.update(current_customer=customer_id, current_date=delivery_date, current_df=edited)
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
        checked = check_order(conn, customer_id, delivery_date, lines, today())

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
            for position, line in enumerate(checked.lines, start=1)
        ]),
        hide_index=True,
        column_config={"Einzelpreis": EURO, "Summe": EURO,
                       "Gebinde": st.column_config.ImageColumn(width="small")},
    )
    line_issues = [Issue(issue.level, f"Pos. {position * 10}: {issue.text}")
                   for position, line in enumerate(checked.lines, start=1) for issue in line.issues]
    show_issues(line_issues + checked.issues)

    totals = st.columns(3)
    totals[0].metric("Warenwert netto", format_eur(checked.net_total))
    totals[1].metric("Pfand", format_eur(checked.deposit_total),
                     help="Wird bei der Lieferung berechnet und bei Rückgabe des Leerguts erstattet.")
    totals[2].metric("Gesamt netto inkl. Pfand", format_eur(checked.net_total + checked.deposit_total))

    # 4. Bestätigung durch den Menschen
    warnings = sum(issue.level == WARNING for issue in checked.all_issues())
    if checked.has_errors:
        st.caption("⛔ Bitte zuerst alle Fehler beheben – erst dann kann der Auftrag gespeichert werden.")
    elif warnings:
        st.caption(f"⚠️ {warnings} Warnung(en) – bitte prüfen. Speichern ist trotzdem möglich.")
    if st.button("Auftrag bestätigen & speichern", type="primary", icon=":material/check:",
                 disabled=checked.has_errors, width="stretch", key=f"{key_prefix}save_{version}"):
        with closing(get_connection()) as conn:
            order_id = save_order(conn, customer_id, delivery_date, capture["message"].channel, lines, today())
        st.cache_data.clear()  # Dashboard und Startseite sollen den neuen Auftrag sofort zeigen
        on_saved(order_id, customers[customer_id]["name"], delivery_date, checked.net_total)
        st.rerun()
    return customer_id, checked
