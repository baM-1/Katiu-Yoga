from decimal import Decimal

import pytest

from katiu.core.money import format_eur, to_cents


@pytest.mark.parametrize(
    ("value", "cents"),
    [
        (21, 2100),
        (21.0, 2100),  # el Excel mezcla int y float
        (21.1, 2110),  # sin el truco de Decimal(str()) saldría 2109
        ("21,50", 2150),
        ("1.234,56 €", 123456),
        (Decimal("0.005"), 1),  # redondeo comercial (half up)
        (0, 0),
    ],
)
def test_to_cents(value: int | float | str | Decimal, cents: int) -> None:
    assert to_cents(value) == cents


def test_to_cents_rechaza_basura() -> None:
    with pytest.raises(ValueError):
        to_cents("veintiuno")
    with pytest.raises(TypeError):
        to_cents(True)


@pytest.mark.parametrize(
    ("cents", "text"),
    [(2100, "21,00 €"), (123456, "1.234,56 €"), (-550, "-5,50 €"), (5, "0,05 €")],
)
def test_format_eur(cents: int, text: str) -> None:
    assert format_eur(cents) == text


def test_format_eur_sin_decimales_si_son_cero() -> None:
    assert format_eur(3500, decimals=False) == "35 €"
    assert format_eur(3550, decimals=False) == "35,50 €"
