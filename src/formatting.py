"""Deutsche Zahlen- und Datumsformate: Tausenderpunkt, Dezimalkomma, Euro, TT.MM.JJJJ."""

from datetime import date


def format_date(day: date) -> str:
    """date(2026, 9, 28) → '28.09.2026'."""
    return day.strftime("%d.%m.%Y")


def format_number(value: float, decimals: int = 0) -> str:
    """1234567.891 → '1.234.567,89' (bei decimals=2)."""
    english = f"{value:,.{decimals}f}"  # '1,234,567.89'
    # Komma und Punkt tauschen – über ein Platzhalterzeichen, damit nichts doppelt ersetzt wird
    return english.replace(",", "#").replace(".", ",").replace("#", ".")


def format_eur(value: float, decimals: int = 2) -> str:
    """Exakter Eurobetrag: 1234.5 → '1.234,50 €'."""
    return f"{format_number(value, decimals)} €"


def format_eur_compact(value: float) -> str:
    """Kurzer Eurobetrag für Kennzahlen: 7960000 → '7,96 Mio. €', 812300 → '812,3 Tsd. €'."""
    if abs(value) >= 1_000_000:
        return f"{format_number(value / 1_000_000, 2)} Mio. €"
    if abs(value) >= 10_000:
        return f"{format_number(value / 1_000, 1)} Tsd. €"
    return format_eur(value, 0)


def format_change(current: float, previous: float) -> str | None:
    """Veränderung in Prozent mit Vorzeichen: '+6,2 %'. None, wenn es keinen Vergleichswert gibt.

    Bewusst das normale Minus '-': st.metric färbt eine Veränderung nur dann rot,
    wenn der Text mit '-' beginnt.
    """
    if not previous:
        return None
    change = (current / previous - 1) * 100
    return f"{'+' if change >= 0 else '-'}{format_number(abs(change), 1)} %"
