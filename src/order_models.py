"""Zielformat der KI-Auswertung: So sieht ein aus Freitext „verstandener“ Auftrag aus.

Die KI (bzw. im Demo-Modus eine vorbereitete Antwort) liefert NUR dieses Format.
Artikelnummern, Preise und Prüfungen kommen danach aus normalem Python-Code (order_capture.py).
"""

from dataclasses import asdict, dataclass, field
from datetime import date

from src.master_data import PRODUCTS

# Erlaubte Werte, die die KI verwenden darf
BEVERAGES = sorted({beverage for _, _, beverage, _, _, _ in PRODUCTS})  # z. B. "Helles", "Cola-Mix"
UNITS = ("Kasten", "Fass")


@dataclass
class ExtractedItem:
    """Eine Bestellposition, wie die KI sie verstanden hat – noch ohne Artikelnummer."""
    original_text: str              # Textstelle aus der Nachricht, z. B. "5 Fass Helles"
    quantity: int                   # Menge in Einheiten (Kästen oder Fässer)
    beverage: str | None            # Sorte aus BEVERAGES; None = unklar oder nicht im Sortiment
    unit: str | None                # "Kasten" oder "Fass"; None = nicht angegeben
    size_liters: int | None = None  # Fassgröße (30 oder 50), nur wenn genannt
    note: str | None = None         # Hinweis der KI, z. B. "Sorte nicht eindeutig"


@dataclass
class ExtractedOrder:
    """Ergebnis der KI-Auswertung einer Nachricht."""
    customer_name: str | None             # Kunde laut Absender/Unterschrift
    delivery_date: date | None            # Wunschtermin, von der KI in ein Datum umgerechnet
    delivery_date_text: str | None        # Originalformulierung, z. B. "für Freitag"
    items: list[ExtractedItem] = field(default_factory=list)
    note: str | None = None               # allgemeiner Hinweis, z. B. "Leergut-Abholung gewünscht"

    @classmethod
    def from_dict(cls, data: dict) -> "ExtractedOrder":
        """Baut das Objekt aus JSON-Daten (so antwortet später die KI-API)."""
        raw_date = data.get("delivery_date")
        return cls(
            customer_name=data.get("customer_name"),
            delivery_date=date.fromisoformat(raw_date) if raw_date else None,
            delivery_date_text=data.get("delivery_date_text"),
            items=[ExtractedItem(**item) for item in data.get("items", [])],
            note=data.get("note"),
        )

    def to_dict(self) -> dict:
        """Für die Anzeige als JSON (Datum als Text 'JJJJ-MM-TT')."""
        data = asdict(self)
        data["delivery_date"] = self.delivery_date.isoformat() if self.delivery_date else None
        return data
