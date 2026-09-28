"""Kostenschutz für die öffentliche Live-App: Grenzen je Nachricht, je Besuch und je Tag.

Die Tagesgrenze ist der eigentliche Schutz (gilt für alle Besucher zusammen). Die Besuchsgrenze
lässt sich durch Neuladen umgehen – sie verhindert nur, dass ein einzelner Besuch alles aufbraucht.
Zusätzliche harte Obergrenze: Ausgabenlimit in der Anthropic Console.
"""

import sqlite3
from datetime import date

MAX_MESSAGE_LENGTH = 1000   # Zeichen je Nachricht
MAX_CALLS_PER_SESSION = 5   # Live-Auswertungen je Besuch
MAX_CALLS_PER_DAY = 30      # Live-Auswertungen je Tag, alle Besucher zusammen


def calls_today(conn: sqlite3.Connection, today: date) -> int:
    row = conn.execute("SELECT calls FROM ai_usage WHERE day = ?", (today.isoformat(),)).fetchone()
    return row[0] if row else 0


def register_call(conn: sqlite3.Connection, today: date) -> None:
    """Zählt einen KI-Aufruf. „ON CONFLICT … DO UPDATE“: neue Zeile anlegen oder vorhandene hochzählen."""
    with conn:
        conn.execute(
            "INSERT INTO ai_usage (day, calls) VALUES (?, 1) "
            "ON CONFLICT(day) DO UPDATE SET calls = calls + 1",
            (today.isoformat(),),
        )


def limit_reason(text: str, session_calls: int, day_calls: int) -> str | None:
    """Grund, warum gerade keine Live-Auswertung möglich ist – oder None, wenn alles passt."""
    if not text.strip():
        return "Bitte zuerst eine Nachricht eingeben."
    if len(text) > MAX_MESSAGE_LENGTH:
        return f"Die Nachricht ist zu lang (höchstens {MAX_MESSAGE_LENGTH} Zeichen)."
    if session_calls >= MAX_CALLS_PER_SESSION:
        return (f"In diesem Besuch sind höchstens {MAX_CALLS_PER_SESSION} Live-Auswertungen möglich. "
                "Der Demo-Modus funktioniert weiterhin.")
    if day_calls >= MAX_CALLS_PER_DAY:
        return "Das Tageslimit für Live-Auswertungen ist erreicht. Der Demo-Modus funktioniert weiterhin."
    return None
