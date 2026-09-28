"""Übergabe eines bestätigten Auftrags an SAP S/4HANA – als Kundenauftrag über die Standard-API.

Ziel ist die OData-Schnittstelle API_SALES_ORDER_SRV (Entität A_SalesOrder mit den Positionen to_Item).
Kopf und Positionen gehen in einem einzigen Aufruf an SAP („Deep Insert“). Die App sendet nichts –
sie zeigt, wie der Aufruf aussähe (Simulation, kein SAP-System angebunden).

Grundsatz wie bei der KI: Wir übergeben, was der Kunde bestellt hat und ein Mensch bestätigt hat.
- Preise schicken wir NICHT mit – SAP ermittelt sie selbst (Konditionstechnik).
- Leergut schicken wir NICHT mit – Getränke-Branchenlösungen erzeugen die Leergutpositionen über
  Leergutstücklisten selbst.
Organisationsdaten (Verkaufsorganisation, Sparte) und Nummern sind Beispielwerte eines fiktiven Systems.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone

from src.demo_messages import DEMO_MESSAGES
from src.order_capture import build_draft, load_customers

SERVICE_URL = "https://<s4hana-host>/sap/opu/odata/sap/API_SALES_ORDER_SRV/A_SalesOrder"
SALES_ORDER_TYPE = "OR"       # Terminauftrag – intern „TA“, in der (englischen) API-Sicht „OR“
SALES_ORGANIZATION = "1010"   # Verkaufsorganisation „Bräu am Stein Inland“ (Beispielwert)
DIVISION = "00"               # Sparte: spartenübergreifend (Getränke)
QUANTITY_UNIT = "PC"          # Stück (intern „ST“) – jeder Artikel ist ein ganzes Gebinde: 1 Kasten, 1 Fass
BUSINESS_PARTNER_OFFSET = 10_000_000  # K1001 → Geschäftspartner 10001001 (Schlüsselmapping, Beispielregel)
# Vertriebsweg je Kundengruppe – über ihn steuert SAP u. a. Preise und Zuständigkeiten
DISTRIBUTION_CHANNELS = {
    "Gastronomie": "10",
    "Getränkegroßhandel": "20",
    "Lebensmittelhandel": "30",
    "Veranstalter": "40",
}
MAX_CUSTOMER_REFERENCE = 35   # Länge des SAP-Felds „Bestellnummer des Kunden“


@dataclass(frozen=True)
class OrderForSap:
    """Ein vom Menschen bestätigter Auftrag – alles, was die Übergabe braucht."""
    order_id: int | None          # None = Beispiel, nicht gespeichert
    customer_id: str
    customer_name: str
    customer_group: str
    channel: str
    delivery_date: date | None
    lines: list[tuple[str, int]]  # [(Artikelnummer, Menge), …]
    net_value: float = 0.0        # nur zur Info – SAP rechnet selbst


def business_partner(customer_id: str) -> str:
    """Kundennummer der App → SAP-Geschäftspartnernummer (in echt aus einer Zuordnungstabelle)."""
    return str(BUSINESS_PARTNER_OFFSET + int(customer_id.removeprefix("K")))


def odata_date(day: date) -> str:
    """Datum im JSON-Format von OData V2: Millisekunden seit 1970 (UTC), z. B. '/Date(1790899200000)/'."""
    midnight = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return f"/Date({int(midnight.timestamp() * 1000)})/"


def customer_reference(order: OrderForSap) -> str:
    """„Bestellnummer des Kunden“: woher der Auftrag kommt – damit er in SAP wiederzufinden ist."""
    origin = f"App-Auftrag {order.order_id}" if order.order_id else "App-Beispiel"
    return f"{origin} · {order.channel}"[:MAX_CUSTOMER_REFERENCE]


def sales_order_payload(order: OrderForSap) -> dict:
    """Kundenauftrag im Format von API_SALES_ORDER_SRV (Deep Insert: Kopf und Positionen zusammen)."""
    return {
        "SalesOrderType": SALES_ORDER_TYPE,
        "SalesOrganization": SALES_ORGANIZATION,
        "DistributionChannel": DISTRIBUTION_CHANNELS.get(order.customer_group, ""),
        "OrganizationDivision": DIVISION,
        "SoldToParty": business_partner(order.customer_id),
        "PurchaseOrderByCustomer": customer_reference(order),
        "RequestedDeliveryDate": odata_date(order.delivery_date) if order.delivery_date else None,
        "to_Item": [
            {
                "SalesOrderItem": str(position * 10),  # Positionsnummern in 10er-Schritten wie in SAP
                "Material": product_id,
                "RequestedQuantity": str(quantity),    # OData V2: Mengen als Text
                "RequestedQuantityUnit": QUANTITY_UNIT,
            }
            for position, (product_id, quantity) in enumerate(order.lines, start=1)
        ],
    }


def missing_fields(payload: dict) -> list[str]:
    """Vollständigkeitsprüfung vor der Übergabe (angelehnt an SAPs Unvollständigkeitsprotokoll)."""
    required = {
        "SalesOrderType": "Verkaufsbelegart",
        "SalesOrganization": "Verkaufsorganisation",
        "DistributionChannel": "Vertriebsweg",
        "OrganizationDivision": "Sparte",
        "SoldToParty": "Auftraggeber",
        "RequestedDeliveryDate": "Wunschlieferdatum",
    }
    missing = [label for field, label in required.items() if not payload.get(field)]
    if not payload.get("to_Item"):
        missing.append("mindestens eine Position")
    for item in payload.get("to_Item", []):
        if not item.get("Material") or int(item.get("RequestedQuantity") or 0) <= 0:
            missing.append(f"Material und Menge in Position {item.get('SalesOrderItem')}")
    return missing


def http_request(payload: dict) -> str:
    """Der Aufruf, wie er an SAP ginge – als lesbarer Text (Methode, Adresse, Kopfzeilen, Inhalt)."""
    return (
        f"POST {SERVICE_URL}\n"
        "Content-Type: application/json\n"
        "Accept: application/json\n"
        "x-csrf-token: <Token aus einem vorherigen GET mit „x-csrf-token: Fetch“>\n"
        "Authorization: <technischer Benutzer aus dem Kommunikationsszenario>\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


# ---------- Aufträge laden ----------

def load_order(conn: sqlite3.Connection, order_id: int) -> OrderForSap:
    """Einen in der App erfassten (vom Menschen bestätigten) Auftrag aus der Datenbank laden."""
    customer_id, channel, delivery = conn.execute(
        "SELECT customer_id, channel, delivery_date FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    rows = conn.execute("SELECT product_id, quantity, quantity * unit_price_eur FROM order_items "
                        "WHERE order_id = ? ORDER BY item_no", (order_id,)).fetchall()
    customer = load_customers(conn)[customer_id]
    return OrderForSap(order_id, customer_id, customer["name"], customer["group"], channel,
                       date.fromisoformat(delivery), [(pid, qty) for pid, qty, _ in rows],
                       sum(value for _, _, value in rows))


def example_order(conn: sqlite3.Connection, today: date) -> OrderForSap:
    """Beispiel, falls noch nichts gespeichert wurde: die Stammwirt-Nachricht nach Abgleich (nicht gespeichert)."""
    demo = DEMO_MESSAGES[0]
    draft = build_draft(conn, demo.extract(today))
    customer = load_customers(conn)[draft.customer_id]
    return OrderForSap(None, draft.customer_id, customer["name"], customer["group"], demo.channel,
                       draft.delivery_date, [(line.product_id, line.quantity) for line in draft.lines])


def field_mapping(order: OrderForSap, payload: dict, product_names: dict[str, str]) -> list[dict]:
    """Feld-Mapping als Tabelle: App-Feld → SAP-Feld, mit Wert und Erklärung."""
    first = payload["to_Item"][0] if payload["to_Item"] else {}
    first_line = order.lines[0] if order.lines else (None, 0)
    delivery = order.delivery_date.strftime("%d.%m.%Y") if order.delivery_date else "–"
    return [
        {"App": "– (fest)", "SAP-Feld": "SalesOrderType", "SAP-Begriff": "Verkaufsbelegart",
         "Wert": payload["SalesOrderType"], "Erklärung": "Terminauftrag (intern „TA“)"},
        {"App": "– (fest)", "SAP-Feld": "SalesOrganization", "SAP-Begriff": "Verkaufsorganisation",
         "Wert": payload["SalesOrganization"], "Erklärung": "Wer verkauft – Bräu am Stein Inland"},
        {"App": f"Kundengruppe: {order.customer_group}", "SAP-Feld": "DistributionChannel",
         "SAP-Begriff": "Vertriebsweg", "Wert": payload["DistributionChannel"],
         "Erklärung": "Weg zum Kunden, abgeleitet aus der Kundengruppe"},
        {"App": "– (fest)", "SAP-Feld": "OrganizationDivision", "SAP-Begriff": "Sparte",
         "Wert": payload["OrganizationDivision"], "Erklärung": "Produktbereich (spartenübergreifend)"},
        {"App": f"Kunde: {order.customer_id} ({order.customer_name})", "SAP-Feld": "SoldToParty",
         "SAP-Begriff": "Auftraggeber (Geschäftspartner)", "Wert": payload["SoldToParty"],
         "Erklärung": "Schlüsselmapping Kundennummer → Geschäftspartner; Warenempfänger ermittelt SAP"},
        {"App": f"Kanal: {order.channel}", "SAP-Feld": "PurchaseOrderByCustomer",
         "SAP-Begriff": "Bestellnummer des Kunden", "Wert": payload["PurchaseOrderByCustomer"],
         "Erklärung": "Bezug zur App – so bleibt der Auftrag nachvollziehbar"},
        {"App": f"Liefertermin: {delivery}", "SAP-Feld": "RequestedDeliveryDate",
         "SAP-Begriff": "Wunschlieferdatum", "Wert": payload["RequestedDeliveryDate"] or "–",
         "Erklärung": "OData-V2-Datumsformat (Millisekunden seit 1970)"},
        {"App": f"Artikel: {product_names.get(first_line[0], first_line[0])}", "SAP-Feld": "to_Item/Material",
         "SAP-Begriff": "Materialnummer", "Wert": first.get("Material", "–"),
         "Erklärung": "Artikelnummer der App = Materialnummer"},
        {"App": f"Menge: {first_line[1]}", "SAP-Feld": "to_Item/RequestedQuantity + Unit",
         "SAP-Begriff": "Auftragsmenge + Mengeneinheit",
         "Wert": f"{first.get('RequestedQuantity', '–')} {first.get('RequestedQuantityUnit', '')}".strip(),
         "Erklärung": "1 Stück = 1 Gebinde (Kasten bzw. Fass)"},
        {"App": "Preis, Pfand", "SAP-Feld": "– (nicht übergeben)", "SAP-Begriff": "Preisfindung, Leergut",
         "Wert": "–", "Erklärung": "Ermittelt SAP selbst (Konditionstechnik, Leergutstückliste)"},
    ]
