"""Geführte Tour: in sechs Schritten und 60 Sekunden durch die App – Inhalt ohne Streamlit, testbar.

Jeder Schritt gehört zu einer Seite; die Oberfläche (ui_tour.py) wechselt beim Weiterklicken dorthin.
Die Zahlen kommen aus den Daten und dem Business Case – nichts ist fest eingetippt.
"""

from dataclasses import dataclass

from src.business_case import DEFAULT_CHANNELS
from src.formatting import format_eur, format_number
from src.process import AS_IS, TO_BE, figures

# Seitenschlüssel → so heißen die Seiten in app.py
PAGES = ("home", "order_entry", "process", "business_case", "dashboard")


@dataclass(frozen=True)
class TourStep:
    page: str   # Seitenschlüssel aus PAGES
    title: str
    text: str   # ein bis zwei Sätze


def tour_steps(orders_per_year: int, saved_hours: float, saved_eur: float) -> list[TourStep]:
    """Die sechs Schritte – mit Auftragsmenge, Prozesskennzahlen und Ersparnis aus den Daten."""
    return [
        TourStep("home", "Das Problem der Brauerei",
                 f"Rund {format_number(round(orders_per_year, -2))} Bestellungen "
                 "im Jahr kommen per WhatsApp, Telefon und E-Mail – als Freitext, oft im Dialekt. Heute tippt "
                 "der Innendienst jede davon von Hand ab."),
        TourStep("order_entry", "Live-KI ausprobieren",
                 "Tippen Sie über dem Handy auf den Vorschlag „Dialekt“ und senden Sie ihn im Handy ab: Claude macht "
                 "daraus in Sekunden einen sauberen Auftrag. Auch der Angriffsversuch lohnt einen Klick."),
        TourStep("order_entry", "Prüfung und Mensch",
                 "Daneben (auf dem Handy darunter) prüft normaler Code Kunde, Artikel, Preise und Regeln – die KI "
                 "versteht nur. Gespeichert wird erst, wenn ein Mensch auf „Auftrag bestätigen & speichern“ klickt."),
        TourStep("process", "SAP-Übergabe",
                 f"Oben der Ablauf heute und mit KI: {figures(TO_BE).manual_steps} statt "
                 f"{figures(AS_IS).manual_steps} manuelle Schritte je Auftrag per "
                 f"{' oder '.join(DEFAULT_CHANNELS)}. Darunter sehen Sie Feld für Feld, "
                 "wie der bestätigte Auftrag als Kundenauftrag in SAP S/4HANA ankommt – Preise und Leergut "
                 "ermittelt SAP selbst."),
        TourStep("business_case", "Was es bringt",
                 f"Mit den Auftragsmengen aus den Daten und gemessenen KI-Kosten spart die Brauerei rund "
                 f"{format_number(saved_hours)} Stunden und {format_eur(saved_eur, 0)} im Jahr. Alle Annahmen "
                 "sind vorsichtig gewählt – verschieben Sie die Regler ruhig selbst."),
        TourStep("dashboard", "Überblick und Fazit",
                 "Jeder bestätigte Auftrag erscheint sofort hier in Umsatz und Saison (Leergut wird erst bei der "
                 "Lieferung gebucht). Fazit: Die KI spart Tipparbeit, der Code sichert die Regeln, der Mensch behält "
                 "die Entscheidung."),
    ]
