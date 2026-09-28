# Evaluation der KI-Auswertung

Modell: `claude-sonnet-5` · Stand: 28.09.2026 · Skript: `tools/evaluate_extraction.py`

Die 7 Beispielnachrichten der Demo werden live von Claude ausgewertet und mit den geprüften
Soll-Ergebnissen verglichen. **Endergebnis** = nach dem Abgleich mit den Stammdaten entsteht
derselbe Auftrag (gleicher Kunde, gleicher Liefertermin, gleiche Artikel und Mengen).

| Nachricht | Kunde | Termin | Positionen | Endergebnis | Dauer |
|---|---|---|---|---|---|
| Stammwirt bestellt per WhatsApp | ✓ | ✓ | 2 / 2 | ✓ | 2,6 s |
| Großhändler bestellt per E-Mail | ✓ | ✓ | 4 / 4 | ✓ | 3,7 s |
| Biergarten schreibt im Dialekt | ✓ | ✓ | 3 / 3 | ✓ | 2,5 s |
| Feuerwehrfest – Telefonnotiz | ✓ | ✓ | 4 / 4 | ✓ | 4,4 s |
| Supermarkt möchte Fässer | ✓ | ✓ | 3 / 3 | ✓ | 3,8 s |
| Tippfehler bei der Menge | ✓ | ✓ | 2 / 2 | ✓ | 2,1 s |
| Neukunde mit unbekanntem Artikel | ✓ | ✓ | 2 / 2 | ✓ | 2,4 s |

**Ergebnis: 7 von 7 Aufträgen identisch zum Soll** · Kosten gesamt ca. 5,8 US-Cent · Ø 3,1 s je Nachricht

Hinweis: Sprachmodelle antworten nicht immer identisch – ein erneuter Lauf kann leicht abweichen.
