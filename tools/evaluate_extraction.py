"""Mini-Evaluation: Wie gut liest Claude die 7 Beispielnachrichten aus?

Vergleicht die echte KI-Antwort mit dem vorbereiteten Soll-Ergebnis – einzeln (Kunde, Termin,
Positionen) und als Endergebnis nach dem Abgleich mit den Stammdaten (gleicher Kunde, gleiche
Artikel und Mengen, gleicher Termin). Schreibt einen Bericht nach docs/EVALUATION.md.

Aufruf (PowerShell, kostet ca. 1 US-Cent je Nachricht):
    .venv\\Scripts\\python.exe -m tools.evaluate_extraction
Der API-Schlüssel wird aus .streamlit/secrets.toml gelesen und nie ausgegeben.
"""

import sys
import tomllib
from collections import Counter
from contextlib import closing
from datetime import date
from pathlib import Path

import anthropic

from src.database import get_connection
from src.demo_messages import DEMO_MESSAGES
from src.extraction import MODEL, ClaudeExtractor, ExtractionError, IncomingMessage
from src.formatting import format_date, format_number
from src.order_capture import build_draft
from src.order_models import ExtractedOrder

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "EVALUATION.md"


def item_keys(order: ExtractedOrder) -> Counter:
    """Positionen als vergleichbare Schlüssel (Sorte, Einheit, Größe, Menge) – Reihenfolge egal."""
    return Counter((i.beverage, i.unit, i.size_liters, i.quantity) for i in order.items)


def final_order(conn, order: ExtractedOrder) -> tuple:
    """Endergebnis nach dem Abgleich: Kunde, Termin und Artikel mit Menge."""
    draft = build_draft(conn, order)
    return draft.customer_id, draft.delivery_date, sorted((str(l.product_id), l.quantity) for l in draft.lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    with open(ROOT / ".streamlit" / "secrets.toml", "rb") as file:
        api_key = tomllib.load(file)["ANTHROPIC_API_KEY"]
    extractor = ClaudeExtractor(anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=2))
    today = date.today()

    rows, notes = [], []
    total_cost = total_seconds = 0.0
    with closing(get_connection()) as conn:
        for demo in DEMO_MESSAGES:
            expected = demo.extract(today)
            try:
                result = extractor.extract(IncomingMessage(demo.text, demo.sender, demo.channel), today)
            except ExtractionError as error:
                rows.append((demo.title, "–", "–", "–", "✗ Fehler", "–"))
                notes.append(f"- **{demo.title}:** {error}")
                continue
            actual = result.order
            total_cost += result.cost_usd
            total_seconds += result.seconds

            customer_ok = build_draft(conn, actual).customer_id == build_draft(conn, expected).customer_id
            date_ok = actual.delivery_date == expected.delivery_date
            matched = sum((item_keys(actual) & item_keys(expected)).values())
            final_ok = final_order(conn, actual) == final_order(conn, expected)
            rows.append((demo.title, "✓" if customer_ok else "✗", "✓" if date_ok else "✗",
                         f"{matched} / {len(expected.items)}", "✓" if final_ok else "✗",
                         f"{format_number(result.seconds, 1)} s"))
            if not final_ok:
                notes.append(f"- **{demo.title}:** KI-Kunde „{actual.customer_name}“ · "
                             f"Soll {final_order(conn, expected)} · Ist {final_order(conn, actual)}")

    ok = sum(row[4] == "✓" for row in rows)
    lines = [
        "# Evaluation der KI-Auswertung",
        "",
        f"Modell: `{MODEL}` · Stand: {format_date(today)} · Skript: `tools/evaluate_extraction.py`",
        "",
        "Die 7 Beispielnachrichten der Demo werden live von Claude ausgewertet und mit den geprüften",
        "Soll-Ergebnissen verglichen. **Endergebnis** = nach dem Abgleich mit den Stammdaten entsteht",
        "derselbe Auftrag (gleicher Kunde, gleicher Liefertermin, gleiche Artikel und Mengen).",
        "",
        "| Nachricht | Kunde | Termin | Positionen | Endergebnis | Dauer |",
        "|---|---|---|---|---|---|",
        *[f"| {' | '.join(row)} |" for row in rows],
        "",
        f"**Ergebnis: {ok} von {len(rows)} Aufträgen identisch zum Soll** · "
        f"Kosten gesamt ca. {format_number(total_cost * 100, 1)} US-Cent · "
        f"Ø {format_number(total_seconds / max(len(rows), 1), 1)} s je Nachricht",
    ]
    if notes:
        lines += ["", "## Abweichungen", "", *notes]
    lines += ["", "Hinweis: Sprachmodelle antworten nicht immer identisch – ein erneuter Lauf kann leicht abweichen."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
