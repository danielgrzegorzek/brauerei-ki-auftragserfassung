"""Demo-Modus: Beispielnachrichten mit vorbereiteten KI-Ergebnissen – funktioniert ohne API-Schlüssel.

Jedes vorbereitete Ergebnis hat genau das Format, das später auch die echte KI liefert
(siehe order_models.py). Liefertermine werden relativ zu „heute“ berechnet, damit
„Freitag“ immer der nächste Freitag ist – egal, wann jemand die Demo ausprobiert.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

from src.order_models import ExtractedOrder

MONDAY, TUESDAY, WEDNESDAY, FRIDAY, SATURDAY = 0, 1, 2, 4, 5


def next_weekday(today: date, weekday: int) -> date:
    """Nächster Wochentag NACH heute (0 = Montag … 6 = Sonntag). Freitag → Freitag = in 7 Tagen."""
    return today + timedelta(days=(weekday - today.weekday() - 1) % 7 + 1)


def weekday_next_week(today: date, weekday: int) -> date:
    """Wochentag in der nächsten Kalenderwoche („nächste Woche am Mittwoch“)."""
    next_monday = today + timedelta(days=7 - today.weekday())
    return next_monday + timedelta(days=weekday)


@dataclass
class DemoMessage:
    title: str                          # Kurzbeschreibung für die Auswahl
    channel: str                        # "WhatsApp", "E-Mail" oder "Telefon"
    sender: str                         # Absender, wie er im Kanal erscheint
    text: str                           # die Nachricht im Original
    shows: str                          # was dieses Beispiel demonstriert
    prepared_result: Callable[[date], dict]  # vorbereitete KI-Antwort (JSON-Format), abhängig von „heute“

    def extract(self, today: date) -> ExtractedOrder:
        """Demo-„KI“: liefert das vorbereitete Ergebnis im gleichen Format wie die echte KI."""
        return ExtractedOrder.from_dict(self.prepared_result(today))


def item(original_text, quantity, beverage, unit, size_liters=None, note=None) -> dict:
    """Kurzschreibweise für eine Position im JSON-Format."""
    return {"original_text": original_text, "quantity": quantity, "beverage": beverage,
            "unit": unit, "size_liters": size_liters, "note": note}


DEMO_MESSAGES = [
    DemoMessage(
        title="Stammwirt bestellt per WhatsApp",
        channel="WhatsApp",
        sender="Sepp (Gasthof Zur Post)",
        text="Servus, bräucht für Freitag 5 Fass Helles und 10 Kasten Weißbier. Pfiat di, Sepp",
        shows="Die Fassgröße fehlt – das System ergänzt sie aus der Bestellhistorie des Kunden.",
        prepared_result=lambda today: {
            "customer_name": "Gasthof Zur Post",
            "delivery_date": next_weekday(today, FRIDAY).isoformat(),
            "delivery_date_text": "für Freitag",
            "items": [
                item("5 Fass Helles", 5, "Helles", "Fass", note="Fassgröße nicht angegeben"),
                item("10 Kasten Weißbier", 10, "Weißbier", "Kasten"),
            ],
            "note": None,
        },
    ),
    DemoMessage(
        title="Großhändler bestellt per E-Mail",
        channel="E-Mail",
        sender="einkauf@getraenkehandel-brunner.example",
        text=(
            "Sehr geehrte Damen und Herren,\n\n"
            "hiermit bestellen wir zur Lieferung am kommenden Dienstag:\n\n"
            "- 120 Kästen Helles\n- 80 Kästen Pils\n- 40 Kästen Radler\n- 12 Fässer Weißbier à 50 Liter\n\n"
            "Bitte bestätigen Sie uns den Liefertermin.\n\n"
            "Mit freundlichen Grüßen\nKatharina Seidl\nEinkauf – Getränkehandel Brunner KG"
        ),
        shows="Sauberer Fall: formell und eindeutig – der Mensch muss nur noch bestätigen.",
        prepared_result=lambda today: {
            "customer_name": "Getränkehandel Brunner KG",
            "delivery_date": next_weekday(today, TUESDAY).isoformat(),
            "delivery_date_text": "am kommenden Dienstag",
            "items": [
                item("120 Kästen Helles", 120, "Helles", "Kasten"),
                item("80 Kästen Pils", 80, "Pils", "Kasten"),
                item("40 Kästen Radler", 40, "Radler", "Kasten"),
                item("12 Fässer Weißbier à 50 Liter", 12, "Weißbier", "Fass", 50),
            ],
            "note": "Kunde bittet um Bestätigung des Liefertermins.",
        },
    ),
    DemoMessage(
        title="Biergarten schreibt im Dialekt",
        channel="WhatsApp",
        sender="Vroni Biergarten",
        text=("Griaß di! Mia bräuchadn bis morgn no 3 Fassl Weizn und 2 Helle, jeweils 50er. "
              "Und 5 Kistn Spezi. Merci, Vroni vom Donaublick"),
        shows="Dialekt und Umgangssprache: „Weizn“, „Fassl“, „Kistn“, „Spezi“ und „bis morgn“.",
        prepared_result=lambda today: {
            "customer_name": "Biergarten Donaublick",
            "delivery_date": (today + timedelta(days=1)).isoformat(),
            "delivery_date_text": "bis morgn",
            "items": [
                item("3 Fassl Weizn", 3, "Weißbier", "Fass", 50, note="„Weizn“ = Weißbier, „Fassl“ = Fass"),
                item("2 Helle, jeweils 50er", 2, "Helles", "Fass", 50, note="„50er“ = 50-Liter-Fass"),
                item("5 Kistn Spezi", 5, "Cola-Mix", "Kasten", note="„Spezi“ = Cola-Mix im Sortiment"),
            ],
            "note": None,
        },
    ),
    DemoMessage(
        title="Feuerwehrfest – Telefonnotiz",
        channel="Telefon",
        sender="Telefonnotiz Innendienst – Anruf Hr. Aigner",
        text=("Anruf Hr. Aigner, FF Hengersberg: Herbstfest am Samstag nächste Woche. Brauchen 25 Fass Helles, "
              "10 Fass Weißbier, 15 Kasten alkoholfreies Helles und 10 Kasten Limo gemischt. "
              "Lieferung am Freitag davor. Leergut vom Sommerfest bitte mitnehmen."),
        shows="„Limo gemischt“ ist mehrdeutig – hier entscheidet der Mensch, das System rät nicht.",
        prepared_result=lambda today: {
            "customer_name": "Freiwillige Feuerwehr Hengersberg",
            # Fest: Samstag nächste Woche → Lieferung am Freitag davor (ebenfalls nächste Woche)
            "delivery_date": weekday_next_week(today, FRIDAY).isoformat(),
            "delivery_date_text": "am Freitag vor dem Fest (Samstag nächste Woche)",
            "items": [
                item("25 Fass Helles", 25, "Helles", "Fass", note="Fassgröße nicht angegeben"),
                item("10 Fass Weißbier", 10, "Weißbier", "Fass", note="Fassgröße nicht angegeben"),
                item("15 Kasten alkoholfreies Helles", 15, "Helles Alkoholfrei", "Kasten"),
                item("10 Kasten Limo gemischt", 10, None, "Kasten",
                     note="Sorte unklar: Zitrone, Orange oder Cola-Mix? Ggf. auf mehrere Positionen aufteilen."),
            ],
            "note": "Leergut vom Sommerfest soll bei der Lieferung mitgenommen werden.",
        },
    ),
    DemoMessage(
        title="Supermarkt möchte Fässer",
        channel="E-Mail",
        sender="a.wimmer@frischemarkt-wimmer.example",
        text=("Hallo zusammen,\n\nfür unsere Grillaktion bitte nächste Woche am Mittwoch liefern: "
              "30 Kasten Helles, 20 Kasten Radler und 2 Fass Helles für den Ausschank vorm Markt.\n\n"
              "Danke & Gruß\nAndrea Wimmer"),
        shows="Fässer sind für den Lebensmittelhandel nicht freigegeben – das System blockiert die Position.",
        prepared_result=lambda today: {
            "customer_name": "Frischemarkt Wimmer",
            "delivery_date": weekday_next_week(today, WEDNESDAY).isoformat(),
            "delivery_date_text": "nächste Woche am Mittwoch",
            "items": [
                item("30 Kasten Helles", 30, "Helles", "Kasten"),
                item("20 Kasten Radler", 20, "Radler", "Kasten"),
                item("2 Fass Helles", 2, "Helles", "Fass", note="Fassgröße nicht angegeben"),
            ],
            "note": None,
        },
    ),
    DemoMessage(
        title="Tippfehler bei der Menge",
        channel="WhatsApp",
        sender="Brandl Wirt",
        text="Hallo, bitte bis Mittwoch 50 Fass Weißbier und 6 Kasten Pils. Danke, Brandl",
        shows="Wahrscheinlich 5 statt 50 Fässer – das System vergleicht mit der Historie und warnt.",
        prepared_result=lambda today: {
            "customer_name": "Gasthaus Brandl",
            "delivery_date": next_weekday(today, WEDNESDAY).isoformat(),
            "delivery_date_text": "bis Mittwoch",
            "items": [
                item("50 Fass Weißbier", 50, "Weißbier", "Fass", note="Fassgröße nicht angegeben"),
                item("6 Kasten Pils", 6, "Pils", "Kasten"),
            ],
            "note": None,
        },
    ),
    DemoMessage(
        title="Neukunde mit unbekanntem Artikel",
        channel="E-Mail",
        sender="info@cafe-sonnenschein.example",
        text=("Grüß Gott,\n\nwir eröffnen im Oktober ein kleines Café in Osterhofen und würden gerne "
              "2 Kasten Dunkles und 3 Kasten Zitronenlimo bestellen – Lieferung übermorgen, wenn möglich.\n\n"
              "Viele Grüße\nCafé Sonnenschein"),
        shows="Unbekannter Kunde und ein Artikel, den es nicht gibt – hier darf nichts automatisch gebucht werden.",
        prepared_result=lambda today: {
            "customer_name": "Café Sonnenschein",
            "delivery_date": (today + timedelta(days=2)).isoformat(),
            "delivery_date_text": "übermorgen",
            "items": [
                item("2 Kasten Dunkles", 2, None, "Kasten", note="„Dunkles“ ist nicht im Sortiment der Brauerei."),
                item("3 Kasten Zitronenlimo", 3, "Zitronenlimonade", "Kasten"),
            ],
            "note": "Absender ist vermutlich ein Neukunde.",
        },
    ),
]
