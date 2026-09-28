"""Tests für die Stammdaten: Artikel, Preise, Kunden."""

import random

import pytest

from src.master_data import (
    CUSTOMER_GROUPS, DEMO_CUSTOMERS, PRICE_INCREASE_DATE, PRICE_VALID_FROM, PRODUCTS,
    generate_customers, generate_prices,
)


def test_every_product_has_prices_for_all_groups_except_grocery_kegs():
    prices = generate_prices()
    pairs = {(product_id, group) for product_id, group, _, _ in prices}
    for product_id, _, _, _, _, empties_type in PRODUCTS:
        for group in CUSTOMER_GROUPS:
            expected = not (group == "Lebensmittelhandel" and empties_type == "FASS")
            assert ((product_id, group) in pairs) == expected, (product_id, group)


def test_price_increase_is_about_five_percent():
    prices = {(p, g, valid_from): price for p, g, valid_from, price in generate_prices()}
    for (product_id, group, valid_from), old_price in prices.items():
        if valid_from == PRICE_VALID_FROM:
            new_price = prices[(product_id, group, PRICE_INCREASE_DATE)]
            assert new_price / old_price == pytest.approx(1.05, abs=0.01)


def test_customer_counts_per_group():
    customers = generate_customers(random.Random(42))
    counts = {group: sum(1 for c in customers if c[2] == group) for group in CUSTOMER_GROUPS}
    assert counts == {"Gastronomie": 80, "Getränkegroßhandel": 8, "Lebensmittelhandel": 15, "Veranstalter": 12}


def test_customer_ids_and_names_are_unique():
    customers = generate_customers(random.Random(42))
    assert len({c[0] for c in customers}) == len(customers)
    assert len({c[1] for c in customers}) == len(customers)


def test_demo_customers_are_included():
    names = {c[1] for c in generate_customers(random.Random(42))}
    assert {name for name, _, _ in DEMO_CUSTOMERS} <= names


def test_same_seed_gives_same_customers():
    assert generate_customers(random.Random(7)) == generate_customers(random.Random(7))
    assert generate_customers(random.Random(7)) != generate_customers(random.Random(8))
