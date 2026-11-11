"""Tarifas vigentes (lista de precios 2026 de Katiu Yoga, Valdebebas).

Es la "semilla" del catálogo: se carga una vez y después Kat las cambia desde Ajustes (Fase 2).
"""

from dataclasses import dataclass

from katiu.classes.models import Modality, PlanFormat, PlanKind

PACK_VALIDITY_DAYS = 60  # "Cada paquete tiene una vigencia de 60 días naturales desde el pago"
LATE_CANCEL_HOURS = 2  # "Cancelaciones con al menos 2 horas de antelación"


@dataclass(frozen=True)
class PlanSeed:
    name: str
    format: PlanFormat
    modality: Modality
    kind: PlanKind
    price_cents: int
    classes_included: int | None = None


def _family(
    label: str, fmt: PlanFormat, modality: Modality, single: int, four: int, eight: int
) -> list[PlanSeed]:
    return [
        PlanSeed(f"{label} · clase suelta", fmt, modality, PlanKind.DROP_IN, single),
        PlanSeed(f"{label} · 4 clases", fmt, modality, PlanKind.PACK, four, 4),
        PlanSeed(f"{label} · 8 clases", fmt, modality, PlanKind.PACK, eight, 8),
    ]


TARIFAS_2026: list[PlanSeed] = [
    *_family(
        "Individual presencial", PlanFormat.INDIVIDUAL, Modality.IN_PERSON, 3500, 12000, 21600
    ),
    *_family("Individual online", PlanFormat.INDIVIDUAL, Modality.ONLINE, 2000, 7200, 14400),
    *_family("Grupal presencial", PlanFormat.GROUP, Modality.IN_PERSON, 3000, 10800, 20000),
]
