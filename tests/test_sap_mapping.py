"""Tests für die Übergabe an SAP S/4HANA: Kundenauftrag im Format der OData-API, Mapping und Vollständigkeit."""

import json
from dataclasses import replace
from datetime import date

import pytest

from src.demo_messages import DEMO_MESSAGES
from src.master_data import CUSTOMER_GROUPS
from src.order_capture import build_draft, load_products, save_order
from src.sap_mapping import (
    DISTRIBUTION_CHANNELS, MAX_CUSTOMER_REFERENCE, OrderForSap, business_partner, customer_reference,
    example_order, field_mapping, http_request, load_order, missing_fields, odata_date, sales_order_payload,
)

TODAY = date(2026, 9, 28)
ORDER = OrderForSap(110067, "K1001", "Gasthof Zur Post", "Gastronomie", "WhatsApp", date(2026, 10, 2),
                    [("HELL-F50", 5), ("WEISS-K20", 10)], 903.0)


def test_payload_has_header_and_items_like_the_sap_api():
    payload = sales_order_payload(ORDER)
    assert payload["SalesOrderType"] == "OR"
    assert (payload["SalesOrganization"], payload["DistributionChannel"], payload["OrganizationDivision"]) == (
        "1010", "10", "00")
    assert payload["SoldToParty"] == "10001001"
    assert payload["PurchaseOrderByCustomer"] == "App-Auftrag 110067 · WhatsApp"
    assert payload["to_Item"] == [
        {"SalesOrderItem": "10", "Material": "HELL-F50", "RequestedQuantity": "5", "RequestedQuantityUnit": "PC"},
        {"SalesOrderItem": "20", "Material": "WEISS-K20", "RequestedQuantity": "10", "RequestedQuantityUnit": "PC"},
    ]


def test_no_prices_and_no_empties_are_sent():
    """SAP ermittelt Preise (Konditionstechnik) und Leergut selbst – wir schicken nur, was bestellt wurde."""
    text = json.dumps(sales_order_payload(ORDER)).casefold()
    assert not any(word in text for word in ("price", "amount", "netvalue", "leergut", "deposit"))


def test_every_customer_group_has_a_distribution_channel():
    assert set(DISTRIBUTION_CHANNELS) == set(CUSTOMER_GROUPS)
    assert len(set(DISTRIBUTION_CHANNELS.values())) == len(CUSTOMER_GROUPS)


def test_business_partner_and_odata_date():
    assert business_partner("K1001") == "10001001"
    assert odata_date(date(1970, 1, 2)) == "/Date(86400000)/"
    assert odata_date(date(2026, 10, 2)) == "/Date(1790899200000)/"


def test_customer_reference_fits_the_sap_field():
    long = replace(ORDER, channel="WhatsApp" * 10)
    assert len(customer_reference(long)) == MAX_CUSTOMER_REFERENCE
    assert customer_reference(replace(ORDER, order_id=None)) == "App-Beispiel · WhatsApp"


def test_complete_order_passes_the_check():
    assert missing_fields(sales_order_payload(ORDER)) == []


@pytest.mark.parametrize("change, expected", [
    ({"delivery_date": None}, "Wunschlieferdatum"),
    ({"lines": []}, "mindestens eine Position"),
    ({"customer_group": "Unbekannt"}, "Vertriebsweg"),
    ({"lines": [("HELL-F50", 0)]}, "Material und Menge in Position 10"),
])
def test_incomplete_orders_are_reported(change, expected):
    assert expected in missing_fields(sales_order_payload(replace(ORDER, **change)))


def test_http_request_shows_method_url_and_body():
    text = http_request(sales_order_payload(ORDER))
    assert text.startswith("POST https://") and "API_SALES_ORDER_SRV/A_SalesOrder" in text
    assert "x-csrf-token" in text and '"SoldToParty": "10001001"' in text


def test_saved_order_is_loaded_for_the_transfer(writable_conn):
    demo = DEMO_MESSAGES[0]
    draft = build_draft(writable_conn, demo.extract(TODAY))
    lines = [(line.product_id, line.quantity) for line in draft.lines]
    order_id = save_order(writable_conn, draft.customer_id, draft.delivery_date, demo.channel, lines, TODAY)
    order = load_order(writable_conn, order_id)
    assert (order.order_id, order.customer_id, order.lines) == (order_id, draft.customer_id, lines)
    assert order.delivery_date == draft.delivery_date and order.net_value > 0
    assert missing_fields(sales_order_payload(order)) == []


def test_example_order_without_saving(conn):
    order = example_order(conn, TODAY)
    assert order.order_id is None and order.customer_name == "Gasthof Zur Post"
    assert missing_fields(sales_order_payload(order)) == []


def test_field_mapping_explains_every_header_field(conn):
    payload = sales_order_payload(ORDER)
    rows = field_mapping(ORDER, payload, {pid: p["name"] for pid, p in load_products(conn).items()})
    mapped = {row["SAP-Feld"] for row in rows}
    assert {key for key in payload if key != "to_Item"} <= mapped
    assert rows[-1]["SAP-Feld"] == "– (nicht übergeben)"   # Preis und Pfand ausdrücklich nicht
