"""Auswertungen für das Dashboard: SQL-Abfragen, die pandas-Tabellen (DataFrames) liefern.

Hier stehen bewusst keine Streamlit-Befehle – so lässt sich alles ohne Oberfläche testen.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.master_data import ORDER_CHANNELS


@dataclass(frozen=True)
class Filters:
    """Auswahl im Dashboard. frozen = unveränderlich → kann als Cache-Schlüssel dienen."""
    start: date
    end: date
    customer_groups: tuple[str, ...]


# Alle Auswertungen gehen von den Auftragspositionen aus und holen Kopf, Kunde und Artikel dazu
BASE_FROM = """
    FROM order_items i
    JOIN orders o    ON o.order_id = i.order_id
    JOIN customers c ON c.customer_id = o.customer_id
    JOIN products p  ON p.product_id = i.product_id
"""
REVENUE = "i.quantity * i.unit_price_eur"
HECTOLITERS = "i.quantity * p.volume_liters / 100.0"


def where_clause(filters: Filters) -> tuple[str, list]:
    """Baut die WHERE-Bedingung mit ?-Platzhaltern – die Werte werden nie in den SQL-Text geklebt."""
    placeholders = ", ".join("?" for _ in filters.customer_groups)
    sql = f"WHERE o.order_date BETWEEN ? AND ? AND c.customer_group IN ({placeholders})"
    params = [filters.start.isoformat(), filters.end.isoformat(), *filters.customer_groups]
    return sql, params


def query(conn: sqlite3.Connection, sql: str, params: list | tuple = ()) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn, params=params)


def shift_year(day: date, years: int) -> date:
    """Verschiebt ein Datum um ganze Jahre (29. Februar → 28. Februar)."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def previous_year(filters: Filters) -> Filters:
    """Gleicher Zeitraum ein Jahr früher – für den Vorjahresvergleich."""
    return Filters(shift_year(filters.start, -1), shift_year(filters.end, -1), filters.customer_groups)


def data_period(conn: sqlite3.Connection) -> tuple[date, date]:
    """Erstes und letztes Bestelldatum in der Datenbank."""
    first, last = conn.execute("SELECT MIN(order_date), MAX(order_date) FROM orders").fetchone()
    return date.fromisoformat(first), date.fromisoformat(last)


def kpis(conn: sqlite3.Connection, filters: Filters) -> dict[str, float]:
    """Kennzahlen: Umsatz, Anzahl Aufträge, Absatz in Hektolitern, durchschnittlicher Auftragswert."""
    where, params = where_clause(filters)
    revenue, orders, hectoliters = conn.execute(f"""
        SELECT COALESCE(SUM({REVENUE}), 0), COUNT(DISTINCT o.order_id), COALESCE(SUM({HECTOLITERS}), 0)
        {BASE_FROM} {where}
    """, params).fetchone()
    return {
        "revenue": revenue,
        "orders": orders,
        "hectoliters": hectoliters,
        "avg_order_value": revenue / orders if orders else 0.0,
    }


def open_deposit(conn: sqlite3.Connection, as_of: date, customer_groups: tuple[str, ...]) -> float:
    """Offenes Pfand in € zum Stichtag: Summe aller Leergut-Bewegungen bis dahin × Pfand."""
    placeholders = ", ".join("?" for _ in customer_groups)
    return conn.execute(f"""
        SELECT COALESCE(SUM(m.quantity * e.deposit_eur), 0)
        FROM empties_movements m
        JOIN empties_types e ON e.empties_type_id = m.empties_type_id
        JOIN customers c     ON c.customer_id = m.customer_id
        WHERE m.movement_date <= ? AND c.customer_group IN ({placeholders})
    """, [as_of.isoformat(), *customer_groups]).fetchone()[0]


def revenue_by_month(conn: sqlite3.Connection, filters: Filters) -> pd.DataFrame:
    """Kennzahlen je Monat. Spalten: month (Datum des Monatsersten), revenue, hectoliters, orders."""
    where, params = where_clause(filters)
    df = query(conn, f"""
        SELECT substr(o.order_date, 1, 7) AS month, SUM({REVENUE}) AS revenue,
               SUM({HECTOLITERS}) AS hectoliters, COUNT(DISTINCT o.order_id) AS orders
        {BASE_FROM} {where}
        GROUP BY month ORDER BY month
    """, params)
    df["month"] = pd.to_datetime(df["month"] + "-01")
    # Monate ohne Aufträge fehlen im SQL-Ergebnis → mit 0 auffüllen, sonst „verschwinden“ sie im Diagramm
    all_months = pd.date_range(filters.start.replace(day=1), filters.end, freq="MS", name="month")
    return df.set_index("month").reindex(all_months, fill_value=0).reset_index()


def open_deposit_by_month(conn: sqlite3.Connection, filters: Filters) -> pd.DataFrame:
    """Offenes Pfand jeweils am Monatsende im Zeitraum. Spalten: month, deposit_eur.

    Der Saldo braucht ALLE Bewegungen seit Beginn, nicht nur die im Zeitraum:
    erst Veränderung je Monat, dann laufende Summe (cumsum), dann auf den Zeitraum kürzen.
    """
    placeholders = ", ".join("?" for _ in filters.customer_groups)
    df = query(conn, f"""
        SELECT substr(m.movement_date, 1, 7) AS month, SUM(m.quantity * e.deposit_eur) AS change_eur
        FROM empties_movements m
        JOIN empties_types e ON e.empties_type_id = m.empties_type_id
        JOIN customers c     ON c.customer_id = m.customer_id
        WHERE m.movement_date <= ? AND c.customer_group IN ({placeholders})
        GROUP BY month ORDER BY month
    """, [filters.end.isoformat(), *filters.customer_groups])
    df["deposit_eur"] = df["change_eur"].cumsum()
    df = df[df["month"] >= filters.start.isoformat()[:7]]
    return df[["month", "deposit_eur"]].reset_index(drop=True)


def revenue_by_customer_group(conn: sqlite3.Connection, filters: Filters) -> pd.DataFrame:
    where, params = where_clause(filters)
    return query(conn, f"""
        SELECT c.customer_group, SUM({REVENUE}) AS revenue, COUNT(DISTINCT o.order_id) AS orders
        {BASE_FROM} {where}
        GROUP BY c.customer_group ORDER BY revenue DESC
    """, params)


def revenue_by_product(conn: sqlite3.Connection, filters: Filters) -> pd.DataFrame:
    where, params = where_clause(filters)
    return query(conn, f"""
        SELECT p.name AS product, p.product_group, SUM(i.quantity) AS quantity,
               SUM({HECTOLITERS}) AS hectoliters, SUM({REVENUE}) AS revenue
        {BASE_FROM} {where}
        GROUP BY p.product_id ORDER BY revenue DESC
    """, params)


def top_customers(conn: sqlite3.Connection, filters: Filters, limit: int = 10) -> pd.DataFrame:
    where, params = where_clause(filters)
    return query(conn, f"""
        SELECT c.name AS customer, c.customer_group, c.city,
               SUM({REVENUE}) AS revenue, COUNT(DISTINCT o.order_id) AS orders
        {BASE_FROM} {where}
        GROUP BY c.customer_id ORDER BY revenue DESC LIMIT ?
    """, [*params, limit])


def seasonality_index(conn: sqlite3.Connection, filters: Filters) -> pd.DataFrame:
    """Saisonindex je Warengruppe und Kalendermonat (100 = Durchschnittsmonat der Warengruppe).

    Rückgabe: Tabelle mit Warengruppen als Zeilen und Monaten 1–12 als Spalten.
    Liegen mehrere Jahre im Zeitraum, wird je Kalendermonat der Durchschnitt über die Jahre genommen.
    """
    where, params = where_clause(filters)
    df = query(conn, f"""
        SELECT p.product_group, substr(o.order_date, 1, 4) AS year,
               CAST(substr(o.order_date, 6, 2) AS INTEGER) AS month, SUM({HECTOLITERS}) AS hectoliters
        {BASE_FROM} {where}
        GROUP BY p.product_group, year, month
    """, params)
    if df.empty:
        return pd.DataFrame()
    per_month = df.groupby(["product_group", "month"])["hectoliters"].mean().unstack("month")
    return per_month.div(per_month.mean(axis=1), axis=0) * 100


def channel_share_by_quarter(conn: sqlite3.Connection, filters: Filters) -> pd.DataFrame:
    """Anteil der Bestellkanäle je Quartal. Spalten: quarter ('Q1 2025'), channel, orders, share (0–1).

    Alle Quartale des Zeitraums sind enthalten; ohne Aufträge ist der Anteil leer (NaN) → Lücke im Diagramm.
    """
    where, params = where_clause(filters)
    df = query(conn, f"""
        SELECT substr(o.order_date, 1, 4) AS year,
               (CAST(substr(o.order_date, 6, 2) AS INTEGER) + 2) / 3 AS q,
               o.channel, COUNT(DISTINCT o.order_id) AS orders
        {BASE_FROM} {where}
        GROUP BY year, q, o.channel
    """, params)
    df["period"] = [pd.Period(f"{year}Q{q}", freq="Q") for year, q in zip(df["year"], df["q"])]
    # Tabelle Quartal × Kanal, fehlende Quartale und Kanäle mit 0 Aufträgen ergänzen
    counts = (df.pivot_table(index="period", columns="channel", values="orders", aggfunc="sum")
                .reindex(index=pd.period_range(filters.start, filters.end, freq="Q"), columns=ORDER_CHANNELS)
                .fillna(0))
    shares = counts.div(counts.sum(axis=1), axis=0)  # 0 / 0 → NaN (Quartal ohne Aufträge)
    result = pd.DataFrame({
        "quarter": [f"Q{p.quarter} {p.year}" for p in counts.index for _ in ORDER_CHANNELS],
        "channel": list(ORDER_CHANNELS) * len(counts),
        "orders": counts.to_numpy().ravel().astype(int),
        "share": shares.to_numpy().ravel(),
    })
    return result


def open_empties_by_customer(conn: sqlite3.Connection, as_of: date, customer_groups: tuple[str, ...]) -> pd.DataFrame:
    """Offenes Leergut je Kunde zum Stichtag, nur Kunden mit offenem Pfand, absteigend nach Pfand."""
    placeholders = ", ".join("?" for _ in customer_groups)
    return query(conn, f"""
        SELECT c.name AS customer, c.customer_group, c.city,
               SUM(CASE WHEN m.empties_type_id = 'KASTEN' THEN m.quantity ELSE 0 END) AS crates,
               SUM(CASE WHEN m.empties_type_id = 'FASS' THEN m.quantity ELSE 0 END) AS kegs,
               SUM(m.quantity * e.deposit_eur) AS deposit_eur
        FROM empties_movements m
        JOIN empties_types e ON e.empties_type_id = m.empties_type_id
        JOIN customers c     ON c.customer_id = m.customer_id
        WHERE m.movement_date <= ? AND c.customer_group IN ({placeholders})
        GROUP BY c.customer_id
        HAVING deposit_eur > 0
        ORDER BY deposit_eur DESC
    """, [as_of.isoformat(), *customer_groups])
