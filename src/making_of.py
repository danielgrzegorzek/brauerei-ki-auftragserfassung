"""Inhalt der Making-of-Seite: warum es das Projekt gibt, wer was gemacht hat, die wichtigsten Entscheidungen.

Nur Daten, kein Streamlit – so ist der Inhalt testbar und die Seite (pages/making_of.py) zeigt nur an.
Die Zeitleiste nennt ausschließlich Entscheidungen, die Daniel selbst getroffen hat.
"""

from dataclasses import dataclass
from datetime import date

AUTHOR = "Daniel Grzegorzek"
PORTFOLIO_URL = "https://danielgrzegorzek.github.io"
GITHUB_URL = "https://github.com/danielgrzegorzek/brauerei-ki-auftragserfassung"
DECISIONS_URL = f"{GITHUB_URL}/blob/main/docs/ENTSCHEIDUNGEN.md"
EVALUATION_URL = f"{GITHUB_URL}/blob/main/docs/EVALUATION.md"

WHY = ("Viele Mittelständler bekommen Bestellungen noch als Freitext – per WhatsApp, E-Mail oder Telefon. "
       "Jemand tippt sie ab, ergänzt, was fehlt, und legt den Auftrag im ERP an. Genau hier treffen drei Themen "
       "aufeinander, die mich interessieren: Prozesse, KI und ERP. Mit diesem Projekt wollte ich zeigen, wie man "
       "sie verbindet – an einem Beispiel, das man in zwei Minuten versteht.")

# Die Brücke: (Titel, ein Satz, Piktogramm aus assets/pict_<name>.svg)
BRIDGE = [
    ("Prozess", "Wo entsteht heute Aufwand – und wie sähe der Ablauf mit KI aus?", "process"),
    ("KI", "Ein Sprachmodell versteht die Nachricht, der Code prüft, ein Mensch bestätigt.", "message"),
    ("ERP", "Der bestätigte Auftrag geht als Kundenauftrag an SAP S/4HANA.", "erp"),
]

ROLE_INTRO = ("Diese App ist mit KI-Unterstützung entstanden – und genau das gehört zum Projekt: "
              "Programmiert hat Claude Code, ein KI-Werkzeug von Anthropic, unter meiner Steuerung.")
MY_PART = [
    "Szenario, Anforderungen und Geschäftsregeln festgelegt – von der Brauerei über den Demo-Modus bis zum "
    "Bestellschluss.",
    "Jede Phase geprüft: im Browser, an den Tests und an Messwerten – und nachbessern lassen, wo etwas nicht stimmte.",
    "Entschieden, was bleibt und was verworfen wird; die Gründe stehen in den Designentscheidungen.",
]
CLAUDE_PART = [
    "Den Code geschrieben – in kleinen Schritten, ein Commit pro Schritt.",
    "Lösungswege vorgeschlagen und technische Details selbst entschieden – offen benannt, damit ich widersprechen "
    "konnte.",
    "Tests geschrieben und Code-Reviews mit Gegenprüfung durchgeführt.",
]


@dataclass(frozen=True)
class Decision:
    phase: str   # „Idee“, „Phase 0“ … – wann die Entscheidung fiel
    title: str
    text: str    # was und warum, ein bis zwei Sätze


DECISIONS = [
    Decision("Idee", "Brauerei statt Beachvolleyball",
             "Mein erstes Szenario war ein Ausstatter für Beachvolleyball. Das Geschäftsmodell war mir nicht "
             "realistisch genug – eine Brauerei mit Wirten, Händlern, Volksfesten und Leergut hat echte Prozessprobleme."),
    Decision("Phase 0", "Demo-Modus als Pflicht",
             "Recruiter sollen die App ohne Anmeldung, ohne API-Schlüssel und ohne Kosten ausprobieren können. "
             "Die Live-KI ist ein Zusatz, keine Voraussetzung."),
    Decision("Phase 0", "Die KI schlägt vor, ein Mensch bestätigt",
             "Human-in-the-Loop von Anfang an: Kein Auftrag wird gespeichert, ohne dass ein Mensch ihn geprüft hat."),
    Decision("Phase 0", "KI-Anbieter austauschbar",
             "Claude als Modell, aber hinter einer schmalen Schnittstelle – ein Wechsel des Anbieters bleibt möglich, "
             "ohne die App umzubauen."),
    Decision("Phase 0", "Entscheidungen offen dokumentieren",
             "Jede Designentscheidung steht mit Begründung und verworfener Alternative im Repository – nachprüfbar "
             "statt behauptet."),
    Decision("Phase 4", "Früh veröffentlichen statt am Ende",
             "Sobald Dashboard und Demo-Modus liefen, ging die App online. Alles Weitere kam als Update – mit einem "
             "Blick auf die Live-App nach jedem Push."),
    Decision("Phase 5b", "Modellvergleich verlangt",
             "Ich wollte das Modell nicht einfach übernehmen: Das kleinste Claude-Modell lief gegen dieselbe "
             "Evaluation, die Regel stand vorher fest – Wechsel nur bei 7 von 7 in zwei Läufen. Haiku kam auf "
             "6 von 7, also blieb Sonnet 5."),
    Decision("Phase 5b", "Bestellungen im WhatsApp-Stil",
             "Die Auftragserfassung zeigt ein Handy mit Chat – so kommen Bestellungen heute wirklich an. Wer die App "
             "öffnet, versteht das Problem in Sekunden."),
    Decision("Phase 5b", "Rückfragen per Knopf, Zusage erst nach Prüfung",
             "Fragt die Brauerei nach, antwortet der Kunde per Knopf. Die verbindliche Bestätigung kommt erst, wenn "
             "ein Mensch den Auftrag gespeichert hat."),
    Decision("Phase 5b", "Angriffe sichtbar machen",
             "Ein Beispiel versucht, die KI mit „Ignoriere alle Regeln …“ umzusteuern. Die App zeigt offen, warum "
             "das nicht durchkommt."),
    Decision("Phase 5b", "Business Case mit Daten statt Schätzung",
             "Auftragszahlen aus der Datenbank, KI-Kosten gemessen, alle Annahmen vorsichtig und als Regler "
             "änderbar. Anrufe nur zuschaltbar, weil dort weiterhin jemand mitschreibt."),
    Decision("Phase 6", "Übergabe an SAP S/4HANA",
             "Ein Auftrag ist erst fertig, wenn er im ERP steht. Die Prozessseite zeigt Ist und Soll und den "
             "Kundenauftrag für die Standard-Schnittstelle – als Simulation, klar gekennzeichnet."),
    Decision("Feinschliff", "Bestellschluss 14 Uhr",
             "Eine Regel aus dem Alltag: Wer nach 14 Uhr für morgen bestellt, bekommt einen Hinweis zur "
             "Tourenplanung, und der Chat bietet erst spätere Liefertage an."),
]


@dataclass(frozen=True)
class EvaluationStep:
    run: str      # „Lauf 1“
    hits: int     # richtig erkannte Beispiele
    total: int
    found: str    # was die Messung gezeigt hat
    fix: str      # was daraufhin geändert wurde


EVALUATION_STEPS = [
    EvaluationStep("Lauf 1", 4, 7,
                   "Kundennamen wie „FF Hengersberg“ fand der Abgleich nicht – die KI hatte richtig gelesen.",
                   "Kundenabgleich über Namensbestandteile, mit Warnung statt stiller Zuordnung."),
    EvaluationStep("Lauf 2–3", 6, 7,
                   "Beim Feuerwehrfest war der Liefertermin falsch berechnet („Samstag in zwei Wochen“).",
                   "Kalender der nächsten 14 Tage im Prompt – Fakten vorgeben statt rechnen lassen."),
    EvaluationStep("Lauf 4–5", 7, 7,
                   "Alle sieben Beispiele richtig – mit Dialekt, Tippfehlern und mehrdeutigen Angaben.",
                   "Danach der Modellvergleich: Haiku 4.5 kam auf 6 von 7, Sonnet 5 blieb im Einsatz."),
]
EVALUATION_LESSON = ("Die meisten Fehler lagen nicht im Sprachverständnis der KI, sondern im Zusammenspiel mit "
                     "meinem Code. Ohne Messung hätte ich an der falschen Stelle gesucht.")

# Was ich gelernt habe: (Überschrift, ein bis zwei Sätze)
LEARNINGS = [
    ("Messen statt glauben",
     "Erst die Evaluation hat gezeigt, wo es hakt – und dass es meist nicht an der KI lag, sondern am Code drumherum."),
    ("Regeln gehören in Code",
     "Die KI versteht die Nachricht, der Code entscheidet. So sind Preise, Freigaben und Prüfungen nachvollziehbar "
     "und testbar."),
    ("Mit KI entwickeln heißt führen und prüfen",
     "Klare Anforderungen, kleine Schritte und eine Abnahme nach jeder Phase. „Lokal grün“ heißt nicht "
     "„online grün“ – deshalb prüfe ich nach jedem Push die Live-App."),
    ("Ehrlich rechnen",
     "Vorsichtige Annahmen und offen benannte Grenzen machen Zahlen glaubwürdiger als große Versprechen."),
]

# Kennzahlen mit Stand-Datum: Die Cloud kennt weder die Git-Historie noch einen Testlauf
FIGURES_AS_OF = date(2026, 9, 29)
TESTS = 249
COMMITS = 76
PHASES_DONE = "0–6"   # siehe Phasenplan in CLAUDE.md; offen: Regel-Parser, Demo-Video


def count_decisions(markdown: str) -> int:
    """Zeilen der Entscheidungstabellen in docs/ENTSCHEIDUNGEN.md – ohne Kopf- und Trennzeilen."""
    return sum(1 for line in markdown.splitlines()
               if line.startswith("| ") and not line.startswith("| Entscheidung |"))
