"""Dinero en céntimos enteros.

Regla de oro: el dinero NUNCA se guarda como float. `0.1 + 0.2 != 0.3` en coma flotante,
y en una contabilidad ese céntimo perdido acaba apareciendo. Guardamos `int` (céntimos) y solo
formateamos a euros al mostrarlo.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

Cents = int

MAX_CLASS_PRICE_CENTS: Cents = 99_900  # 999 €: más en una sola clase es casi seguro un error


def to_cents(value: int | float | str | Decimal) -> Cents:
    """Convierte euros (21, 21.0, "21,50", Decimal("21.5")) a céntimos (2100, 2150).

    Pasamos por `Decimal(str(x))` para que 21.1 (float) no se convierta en 2109.99999...
    """
    if isinstance(value, bool):
        raise TypeError("Un booleano no es un importe")
    text = str(value).strip().replace("€", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")  # formato español: 1.234,56
    try:
        euros = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Importe no válido: {value!r}") from exc
    return int((euros * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_eur(cents: Cents, *, decimals: bool = True) -> str:
    """2100 → "21,00 €" · 123456 → "1.234,56 €" · con decimals=False: "21 €"."""
    sign = "-" if cents < 0 else ""
    euros, cent = divmod(abs(cents), 100)
    whole = f"{euros:,}".replace(",", ".")
    if decimals or cent:
        return f"{sign}{whole},{cent:02d} €"
    return f"{sign}{whole} €"


def format_amount_input(cents: Cents) -> str:
    """Para rellenar un campo de importe: 2100 → "21" · 2150 → "21,50" (sin € ni miles)."""
    euros, cent = divmod(cents, 100)
    return f"{euros},{cent:02d}" if cent else str(euros)
