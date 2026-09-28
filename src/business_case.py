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
FALLBACK_AI_COST = 0.01       # nur falls es keine Messung gibt: 1 Cent je Auftrag (vorsichtig)
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
    Assumption("minutes_ai_phone", "Minuten je Telefonauftrag – mit KI", 4.0, "min", 0.0, 20.0, 0.5,
               "Beim Anruf schreibt weiterhin jemand mit – nur Suchen und Abtippen entfallen, deshalb spart "
               "die KI hier nur die Hälfte."),
    Assumption("hourly_rate", "Stundensatz Innendienst", 40.0, "€/h", 20.0, 80.0, 1.0,
               "Vollkosten eines Arbeitsplatzes (Gehalt, Nebenkosten, Arbeitsplatz) je produktiver Stunde – "
               "eher unteres Ende."),
    Assumption("error_rate_manual", "Fehlerquote – manuell", 2.0, "%", 0.0, 10.0, 0.5,
               "Anteil der Aufträge mit Tipp- oder Zuordnungsfehler beim Abtippen – vorsichtig niedrig."),
    Assumption("error_rate_ai", "Fehlerquote – mit KI", 1.0, "%", 0.0, 10.0, 0.5,
               "Nur halbiert, obwohl Prüfung und Bestätigung viele Fehler abfangen – auch der Mensch kann "
               "sich beim Bestätigen irren. Für Telefonaufträge rechnen wir vorsichtig ohne Verbesserung."),
    Assumption("cost_per_error", "Kosten je Fehler", 50.0, "€", 0.0, 300.0, 5.0,
               "Nachlieferung, Gutschrift und Klärungsaufwand – ohne den Ärger beim Kunden."),
    Assumption("operating_cost", "Betrieb & Wartung pro Jahr", 2000.0, "€", 0.0, 20000.0, 250.0,
               "Hosting, Updates und regelmäßige Kontrolle der KI-Qualität – ohne das einmalige "
               "Einführungsprojekt."),
]
DEFAULTS = {assumption.key: assumption.default for assumption in ASSUMPTIONS}


@dataclass(frozen=True)
class Inputs:
    """Alles, was die Rechnung braucht. Fehlerquoten als Anteil (0,02 = 2 %).
    orders_per_year = Aufträge per WhatsApp/E-Mail; phone_orders_per_year = Telefonaufträge (0 = nicht gezählt)."""
    orders_per_year: int
    minutes_manual: float
    minutes_ai: float
    hourly_rate: float
    error_rate_manual: float
    error_rate_ai: float
    cost_per_error: float
    operating_cost: float
    ai_cost_per_order: float   # € je Auftrag – gemessen
    phone_orders_per_year: int = 0
    minutes_ai_phone: float = 4.0

    def __post_init__(self):
        if self.orders_per_year < 0 or self.phone_orders_per_year < 0:
            raise ValueError("Die Auftragsmenge darf nicht negativ sein.")
        for name in ("minutes_manual", "minutes_ai", "minutes_ai_phone", "hourly_rate", "cost_per_error",
                     "operating_cost", "ai_cost_per_order"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} darf nicht negativ sein.")
        for name in ("error_rate_manual", "error_rate_ai"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} muss zwischen 0 und 1 liegen.")

    @property
    def all_orders(self) -> int:
        return self.orders_per_year + self.phone_orders_per_year


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
    def saved_labor_cost(self) -> float:
        return self.before.labor_cost - self.after.labor_cost

    @property
    def saved_error_cost(self) -> float:
        return self.before.error_cost - self.after.error_cost

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
    """Vorher (manuell) und nachher (KI-gestützt) für ein Jahr.
    Telefonaufträge vorsichtig: eigene (höhere) Minuten mit KI und keine geringere Fehlerquote."""
    text, phone = inputs.orders_per_year, inputs.phone_orders_per_year
    hours_before = (text + phone) * inputs.minutes_manual / 60
    hours_after = (text * inputs.minutes_ai + phone * inputs.minutes_ai_phone) / 60
    errors_before = (text + phone) * inputs.error_rate_manual
    errors_after = text * inputs.error_rate_ai + phone * inputs.error_rate_manual
    before = Scenario(hours_before, hours_before * inputs.hourly_rate,
                      errors_before, errors_before * inputs.cost_per_error)
    after = Scenario(hours_after, hours_after * inputs.hourly_rate,
                     errors_after, errors_after * inputs.cost_per_error,
                     ai_cost=(text + phone) * inputs.ai_cost_per_order, operating_cost=inputs.operating_cost)
    return Result(before, after)


def inputs_from_settings(orders_per_year: int, settings: dict[str, float], ai_cost_per_order: float,
                         phone_orders_per_year: int = 0) -> Inputs:
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
        phone_orders_per_year=phone_orders_per_year,
        minutes_ai_phone=settings["minutes_ai_phone"],
    )


def default_result(conn: sqlite3.Connection, model: str) -> tuple[Inputs, Result]:
    """Ergebnis mit den vorsichtigen Standardannahmen (WhatsApp + E-Mail) – für Startseite und Tour,
    damit überall dieselben Zahlen stehen wie auf der Business-Case-Seite."""
    per_channel = orders_last_12_months(conn)
    measured = measured_ai_cost(model)
    ai_cost = measured.eur_per_order if measured else FALLBACK_AI_COST
    inputs = inputs_from_settings(sum(per_channel.get(c, 0) for c in DEFAULT_CHANNELS), DEFAULTS, ai_cost)
    return inputs, calculate(inputs)


def exact(value: float) -> str:
    """Zwischenwert ohne Rundungsfehler im Rechenweg: 325.8 → '325,8', 65.16 → '65,16', 60.0 → '60'."""
    return format_number(value, 2).rstrip("0").rstrip(",")


def calculation_steps(inputs: Inputs, result: Result, ai_cost_measured: bool = True) -> list[str]:
    """Der Rechenweg in Worten – mit genauen Zwischenwerten, damit jede Zeile nachrechenbar aufgeht."""
    b, a = result.before, result.after
    text, phone, rate = inputs.orders_per_year, inputs.phone_orders_per_year, format_eur(inputs.hourly_rate, 0)
    all_orders = format_number(inputs.all_orders)
    minutes_after = f"{format_number(text)} × {exact(inputs.minutes_ai)} min"
    errors_after = f"{format_number(text)} × {exact(inputs.error_rate_ai * 100)} %"
    if phone:  # Telefonaufträge mit eigenen Werten
        minutes_after += f" + {format_number(phone)} Telefon × {exact(inputs.minutes_ai_phone)} min"
        errors_after += f" + {format_number(phone)} Telefon × {exact(inputs.error_rate_manual * 100)} %"
    source = "gemessen" if ai_cost_measured else "angenommen – keine Messung vorhanden"
    return [
        f"**Arbeitszeit vorher:** {all_orders} Aufträge × {exact(inputs.minutes_manual)} min = "
        f"{exact(b.hours)} h × {rate}/h = {format_eur(b.labor_cost, 0)}",
        f"**Arbeitszeit nachher:** {minutes_after} = {exact(a.hours)} h × {rate}/h = {format_eur(a.labor_cost, 0)}",
        f"**Fehler vorher:** {all_orders} × {exact(inputs.error_rate_manual * 100)} % = {exact(b.errors)} Fehler "
        f"× {format_eur(inputs.cost_per_error, 0)} = {format_eur(b.error_cost, 0)}",
        f"**Fehler nachher:** {errors_after} = {exact(a.errors)} Fehler × {format_eur(inputs.cost_per_error, 0)} "
        f"= {format_eur(a.error_cost, 0)}",
        f"**Vermiedene Fehler:** {exact(b.errors)} − {exact(a.errors)} = {exact(result.avoided_errors)}",
        f"**KI-Kosten:** {all_orders} Aufträge × {format_eur(inputs.ai_cost_per_order, 4)} ({source}) = "
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
    """Letzter gültiger Evaluationslauf des Modells – None, wenn es (noch) keine Messung gibt.
    Läufe ohne Kosten (z. B. alle Aufrufe gescheitert) zählen nicht als Messung."""
    if not path.exists():
        return None
    runs = [run for run in json.loads(path.read_text(encoding="utf-8"))
            if run["model"] == model and run["cost_per_message_usd"] > 0]
    if not runs:
        return None
    run = runs[-1]
    return MeasuredAiCost(run["cost_per_message_usd"], run["model_name"], date.fromisoformat(run["date"]),
                          run["hits"], run["total"])


def busiest_and_quietest(monthly: list[tuple[str, int]]) -> tuple[tuple[str, int], tuple[str, int]]:
    """Stärkster und ruhigster Monat: ((JJJJ-MM, Aufträge), (JJJJ-MM, Aufträge))."""
    return max(monthly, key=lambda row: row[1]), min(monthly, key=lambda row: row[1])
