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
    text: str   # genau ein Satz


def tour_steps(orders_per_year: int, saved_hours: float, saved_eur: float) -> list[TourStep]:
    """Die sechs Schritte – mit Auftragsmenge, Prozesskennzahlen und Ersparnis aus den Daten."""
    return [
        TourStep("home", "Das Problem der Brauerei",
                 f"Rund {format_number(round(orders_per_year, -2))} Bestellungen im Jahr kommen als Freitext per "
                 "WhatsApp, Telefon und E-Mail – heute tippt der Innendienst jede davon von Hand ab."),
        TourStep("order_entry", "Live-KI ausprobieren",
                 "Tippen Sie auf „Dialekt“ und senden Sie die Nachricht im Handy ab – Claude macht daraus in Sekunden "
                 "einen Auftragsvorschlag."),
        TourStep("order_entry", "Prüfung und Mensch",
                 "Normaler Code prüft Kunde, Artikel, Preise und Regeln – gespeichert wird erst, wenn ein Mensch auf "
                 "„Auftrag bestätigen & speichern“ klickt."),
        TourStep("process", "SAP-Übergabe",
                 f"Mit KI {figures(TO_BE).manual_steps} statt {figures(AS_IS).manual_steps} manuelle Schritte je "
                 f"Auftrag per {' oder '.join(DEFAULT_CHANNELS)} – darunter der Kundenauftrag für SAP S/4HANA, "
                 "den Sie mit „Übergabe simulieren“ testweise übergeben."),
        TourStep("business_case", "Was es bringt",
                 f"Mit den Auftragsmengen aus den (simulierten) Daten und gemessenen KI-Kosten spart die Brauerei rund "
                 f"{format_number(saved_hours)} Stunden und {format_eur(saved_eur, 0)} im Jahr – eigene Annahmen "
                 "stellen Sie unter „Annahmen anpassen“ ein."),
        TourStep("dashboard", "Überblick und Fazit",
                 "Jeder bestätigte Auftrag erscheint sofort hier – die KI versteht, der Code entscheidet, der Mensch "
                 "bestätigt."),
    ]
