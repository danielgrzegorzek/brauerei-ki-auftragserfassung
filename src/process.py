"""Ist- und Soll-Prozess der Auftragserfassung – als Daten, ohne Streamlit, testbar.

Die Minuten des Innendiensts passen zu den Annahmen des Business Case (6 min heute, 2 min mit KI) –
ein Test stellt sicher, dass beide Seiten dieselbe Geschichte erzählen.
"""

from dataclasses import dataclass

LANES = ("Kunde", "Innendienst", "KI & Prüfung", "SAP S/4HANA")  # „Schwimmbahnen“: wer macht was
MANUAL, AUTOMATIC, CUSTOMER = "manuell", "automatisch", "Kunde"


@dataclass(frozen=True)
class ProcessStep:
    lane: str                   # aus LANES
    title: str
    kind: str                   # MANUAL, AUTOMATIC oder CUSTOMER
    minutes: float = 0.0        # Arbeitszeit des Innendiensts
    note: str = ""              # Schwachstelle (Ist) bzw. Verbesserung (Soll)
    media_break: bool = False   # Medienbruch: Information wird von einem System ins andere übertragen


AS_IS = [
    ProcessStep("Kunde", "Bestellung per WhatsApp, E-Mail oder Anruf", CUSTOMER,
                note="Freitext ohne festes Format, oft im Dialekt"),
    ProcessStep("Innendienst", "Nachricht lesen und verstehen", MANUAL, 0.5,
                note="Unklare Angaben, z. B. fehlende Fassgröße"),
    ProcessStep("Innendienst", "Kunde und Artikel in SAP suchen", MANUAL, 1.5,
                note="Wechsel zwischen Handy, Postfach und SAP", media_break=True),
    ProcessStep("Innendienst", "Kundenauftrag in SAP abtippen (VA01)", MANUAL, 2.0,
                note="Tippfehler und Zahlendreher", media_break=True),
    ProcessStep("Innendienst", "Freigaben, Mengen und Leergut prüfen", MANUAL, 1.0,
                note="Regeln stehen im Kopf einzelner Mitarbeiter"),
    ProcessStep("Innendienst", "Bei Unklarheit zurückrufen", MANUAL, 0.5,
                note="Telefon-Ping-Pong, Wartezeit für den Kunden"),
    ProcessStep("Innendienst", "Auftrag bestätigen", MANUAL, 0.5,
                note="Rückmeldung oft erst Stunden später"),
]

TO_BE = [
    ProcessStep("Kunde", "Bestellung per WhatsApp, E-Mail oder Anruf", CUSTOMER,
                note="Für den Kunden ändert sich nichts – kein neues Portal"),
    ProcessStep("KI & Prüfung", "KI übersetzt die Nachricht in ein festes Format", AUTOMATIC,
                note="In Sekunden, auch Dialekt"),
    ProcessStep("KI & Prüfung", "Code ordnet Kunde und Artikel zu und prüft die Regeln", AUTOMATIC,
                note="Freigaben, Mengen, Termin – nachvollziehbar und getestet"),
    ProcessStep("KI & Prüfung", "Eingangsbestätigung oder Rückfrage mit Knöpfen", AUTOMATIC,
                note="Antwort an den Kunden in Sekunden"),
    ProcessStep("Innendienst", "Vorschlag prüfen und bestätigen", MANUAL, 2.0,
                note="Der Mensch entscheidet (Human-in-the-Loop)"),
    ProcessStep("SAP S/4HANA", "Kundenauftrag per Standard-API anlegen", AUTOMATIC,
                note="Kein Abtippen; Preise und Leergut ermittelt SAP selbst"),
    ProcessStep("SAP S/4HANA", "Verbindliche Auftragsbestätigung an den Kunden", AUTOMATIC,
                note="Erst nach der Freigabe durch den Menschen"),
]


@dataclass(frozen=True)
class ProcessFigures:
    manual_steps: int
    minutes: float
    media_breaks: int


def figures(steps: list[ProcessStep]) -> ProcessFigures:
    """Kennzahlen eines Prozesses: manuelle Schritte, Arbeitszeit, Medienbrüche."""
    return ProcessFigures(sum(step.kind == MANUAL for step in steps),
                          sum(step.minutes for step in steps),
                          sum(step.media_break for step in steps))
