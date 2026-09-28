"""Business Case: Was bringt die KI-gestützte Auftragserfassung im Jahr? – ohne Streamlit, vollständig getestet.

Vorher:  Der Innendienst tippt jede Bestellung von Hand ab.
Nachher: Die KI liest die Nachricht, der Code ordnet zu und prüft, der Mensch prüft nur noch und bestätigt.

Grundsätze:
- Die Auftragsmenge kommt aus den Daten (letzte 12 Monate), nicht aus einer Schätzung.
- Die KI-Kosten je Auftrag sind gemessen (Evaluation, docs/evaluation.json).
- Alles andere sind Annahmen – vorsichtig gewählt, begründet und in der Oberfläche änderbar.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.formatting import format_date, format_eur, format_number

EVALUATION_FILE = Path(__file__).resolve().parent.parent / "docs" / "evaluation.json"
USD_TO_EUR = 1.0              # vorsichtig: 1 US-$ = 1 € – überschätzt die KI-Kosten eher
HOURS_PER_WEEK = 40           # für „entspricht X Arbeitswochen“
DEFAULT_CHANNELS = ("WhatsApp", "E-Mail")   # Telefon zuschaltbar: dort muss weiterhin jemand mitschreiben


@dataclass(frozen=True)
class Assumption:
    """Eine änderbare Annahme – mit vorsichtigem Standardwert und einem Satz Begründung."""
    key: str
    label: str
    default: float
    unit: str
    minimum: float
    maximum: float
    step: float
    reason: str


ASSUMPTIONS = [
    Assumption("minutes_manual", "Minuten je Auftrag – manuell", 6.0, "min", 1.0, 20.0, 0.5,
               "Lesen, Kunde und Artikel suchen, abtippen, Preise prüfen, bestätigen – knapp angesetzt, "
               "in der Praxis sind 5–10 Minuten üblich."),
    Assumption("minutes_ai", "Minuten je Auftrag – mit KI", 2.0, "min", 0.0, 10.0, 0.5,
               "Der Mensch prüft jeden Vorschlag und bestätigt – großzügig angesetzt, ein sauberer Fall "
               "dauert unter einer Minute."),
    Assumption("hourly_rate", "Stundensatz Innendienst", 40.0, "€/h", 20.0, 80.0, 1.0,
               "Vollkosten eines Arbeitsplatzes (Gehalt, Nebenkosten, Arbeitsplatz) je produktiver Stunde – "
               "eher unteres Ende."),
    Assumption("error_rate_manual", "Fehlerquote – manuell", 2.0, "%", 0.0, 10.0, 0.5,
               "Anteil der Aufträge mit Tipp- oder Zuordnungsfehler beim Abtippen – vorsichtig niedrig."),
    Assumption("error_rate_ai", "Fehlerquote – mit KI", 1.0, "%", 0.0, 10.0, 0.5,
               "Nur halbiert, obwohl Prüfung und Bestätigung viele Fehler abfangen – auch der Mensch kann "
               "sich beim Bestätigen irren."),
    Assumption("cost_per_error", "Kosten je Fehler", 50.0, "€", 0.0, 300.0, 5.0,
               "Nachlieferung, Gutschrift und Klärungsaufwand – ohne den Ärger beim Kunden."),
    Assumption("operating_cost", "Betrieb & Wartung pro Jahr", 2000.0, "€", 0.0, 20000.0, 250.0,
               "Hosting, Updates und regelmäßige Kontrolle der KI-Qualität – ohne das einmalige "
               "Einführungsprojekt."),
]
DEFAULTS = {assumption.key: assumption.default for assumption in ASSUMPTIONS}


@dataclass(frozen=True)
class Inputs:
    """Alles, was die Rechnung braucht. Fehlerquoten als Anteil (0,02 = 2 %)."""
    orders_per_year: int
    minutes_manual: float
    minutes_ai: float
    hourly_rate: float
    error_rate_manual: float
    error_rate_ai: float
    cost_per_error: float
    operating_cost: float
    ai_cost_per_order: float   # € je Auftrag – gemessen

    def __post_init__(self):
        if self.orders_per_year < 0:
            raise ValueError("Die Auftragsmenge darf nicht negativ sein.")
        for name in ("minutes_manual", "minutes_ai", "hourly_rate", "cost_per_error", "operating_cost",
                     "ai_cost_per_order"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} darf nicht negativ sein.")
        for name in ("error_rate_manual", "error_rate_ai"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} muss zwischen 0 und 1 liegen.")


@dataclass(frozen=True)
class Scenario:
    """Jahreswerte eines Szenarios (vorher oder nachher)."""
    hours: float          # Arbeitsstunden für die Erfassung
    labor_cost: float
    errors: float         # fehlerhafte Aufträge
    error_cost: float
    ai_cost: float = 0.0  # KI-Aufrufe
    operating_cost: float = 0.0

    @property
    def total(self) -> float:
        return self.labor_cost + self.error_cost + self.ai_cost + self.operating_cost


@dataclass(frozen=True)
class Result:
    before: Scenario
    after: Scenario

    @property
    def saved_hours(self) -> float:
        return self.before.hours - self.after.hours

    @property
    def saved_eur(self) -> float:
        return self.before.total - self.after.total

    @property
    def avoided_errors(self) -> float:
        return self.before.errors - self.after.errors

    @property
    def saved_work_weeks(self) -> float:
        return self.saved_hours / HOURS_PER_WEEK


def calculate(inputs: Inputs) -> Result:
    """Vorher (manuell) und nachher (KI-gestützt) für ein Jahr."""
    orders = inputs.orders_per_year
    hours_before = orders * inputs.minutes_manual / 60
    hours_after = orders * inputs.minutes_ai / 60
    errors_before = orders * inputs.error_rate_manual
    errors_after = orders * inputs.error_rate_ai
    before = Scenario(hours_before, hours_before * inputs.hourly_rate,
                      errors_before, errors_before * inputs.cost_per_error)
    after = Scenario(hours_after, hours_after * inputs.hourly_rate,
                     errors_after, errors_after * inputs.cost_per_error,
                     ai_cost=orders * inputs.ai_cost_per_order, operating_cost=inputs.operating_cost)
    return Result(before, after)


def inputs_from_settings(orders_per_year: int, settings: dict[str, float], ai_cost_per_order: float) -> Inputs:
    """Werte aus der Oberfläche (Fehlerquoten in %) → Inputs."""
    return Inputs(
        orders_per_year=orders_per_year,
        minutes_manual=settings["minutes_manual"],
        minutes_ai=settings["minutes_ai"],
        hourly_rate=settings["hourly_rate"],
        error_rate_manual=settings["error_rate_manual"] / 100,
        error_rate_ai=settings["error_rate_ai"] / 100,
        cost_per_error=settings["cost_per_error"],
        operating_cost=settings["operating_cost"],
        ai_cost_per_order=ai_cost_per_order,
    )


def calculation_steps(inputs: Inputs, result: Result) -> list[str]:
    """Der Rechenweg in Worten – für die aufklappbare Erklärung."""
    b, a, orders = result.before, result.after, inputs.orders_per_year
    n = format_number(orders)
    return [
        f"**Arbeitszeit vorher:** {n} Aufträge × {format_number(inputs.minutes_manual, 1)} min = "
        f"{format_number(b.hours)} h × {format_eur(inputs.hourly_rate, 0)}/h = {format_eur(b.labor_cost, 0)}",
        f"**Arbeitszeit nachher:** {n} Aufträge × {format_number(inputs.minutes_ai, 1)} min = "
        f"{format_number(a.hours)} h × {format_eur(inputs.hourly_rate, 0)}/h = {format_eur(a.labor_cost, 0)}",
        f"**Fehler vorher:** {n} × {format_number(inputs.error_rate_manual * 100, 1)} % = "
        f"{format_number(b.errors)} Fehler × {format_eur(inputs.cost_per_error, 0)} = {format_eur(b.error_cost, 0)}",
        f"**Fehler nachher:** {n} × {format_number(inputs.error_rate_ai * 100, 1)} % = "
        f"{format_number(a.errors)} Fehler × {format_eur(inputs.cost_per_error, 0)} = {format_eur(a.error_cost, 0)}",
        f"**KI-Kosten:** {n} Aufträge × {format_eur(inputs.ai_cost_per_order, 4)} (gemessen) = "
        f"{format_eur(a.ai_cost, 0)}",
        f"**Betrieb & Wartung:** {format_eur(a.operating_cost, 0)} pro Jahr",
        f"**Ersparnis:** {format_eur(b.total, 0)} vorher − {format_eur(a.total, 0)} nachher = "
        f"**{format_eur(result.saved_eur, 0)} pro Jahr**",
    ]


# ---------- Daten: Auftragsmenge aus der Datenbank, KI-Kosten aus der Evaluation ----------

LAST_12_MONTHS = """
    source = 'Historie'
    AND order_date > date((SELECT MAX(order_date) FROM orders WHERE source = 'Historie'), '-12 months')
"""


def orders_last_12_months(conn: sqlite3.Connection) -> dict[str, int]:
    """Aufträge der letzten 12 Monate je Kanal – gerechnet ab dem letzten Auftrag der Historie."""
    rows = conn.execute(f"SELECT channel, COUNT(*) FROM orders WHERE {LAST_12_MONTHS} GROUP BY channel")
    return dict(rows.fetchall())


def period_last_12_months(conn: sqlite3.Connection) -> tuple[date, date]:
    first, last = conn.execute(
        f"SELECT MIN(order_date), MAX(order_date) FROM orders WHERE {LAST_12_MONTHS}").fetchone()
    return date.fromisoformat(first), date.fromisoformat(last)


def orders_by_month(conn: sqlite3.Connection, channels: tuple[str, ...]) -> list[tuple[str, int]]:
    """Aufträge je Monat (JJJJ-MM) der letzten 12 Monate für die gewählten Kanäle – für die Hochsaison."""
    marks = ", ".join("?" for _ in channels)
    rows = conn.execute(f"""
        SELECT substr(order_date, 1, 7) AS month, COUNT(*) FROM orders
        WHERE {LAST_12_MONTHS} AND channel IN ({marks})
        GROUP BY month ORDER BY month
    """, channels)
    return rows.fetchall()


@dataclass(frozen=True)
class MeasuredAiCost:
    """KI-Kosten je Auftrag aus dem letzten Evaluationslauf eines Modells."""
    usd_per_order: float
    model_name: str
    measured_on: date
    hits: int
    total: int

    @property
    def eur_per_order(self) -> float:
        return self.usd_per_order * USD_TO_EUR

    @property
    def source_text(self) -> str:
        return (f"gemessen am {format_date(self.measured_on)} mit {self.model_name} "
                f"({self.hits} von {self.total} Aufträgen richtig)")


def measured_ai_cost(model: str, path: Path = EVALUATION_FILE) -> MeasuredAiCost | None:
    """Letzter Evaluationslauf des Modells – None, wenn es (noch) keine Messung gibt."""
    if not path.exists():
        return None
    runs = [run for run in json.loads(path.read_text(encoding="utf-8")) if run["model"] == model]
    if not runs:
        return None
    run = runs[-1]
    return MeasuredAiCost(run["cost_per_message_usd"], run["model_name"], date.fromisoformat(run["date"]),
                          run["hits"], run["total"])


def busiest_and_quietest(monthly: list[tuple[str, int]]) -> tuple[tuple[str, int], tuple[str, int]]:
    """Stärkster und ruhigster Monat: ((JJJJ-MM, Aufträge), (JJJJ-MM, Aufträge))."""
    return max(monthly, key=lambda row: row[1]), min(monthly, key=lambda row: row[1])
