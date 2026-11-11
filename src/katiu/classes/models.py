"""Planes (tarifas), horario recurrente y sesiones de clase."""

import datetime as dt
from enum import StrEnum

from sqlmodel import Field, SQLModel


class PlanKind(StrEnum):
    DROP_IN = "drop_in"  # clase suelta
    PACK = "pack"  # bono de N clases (4/mes, 8/mes)


class PlanFormat(StrEnum):
    INDIVIDUAL = "individual"
    GROUP = "group"


class Modality(StrEnum):
    IN_PERSON = "in_person"
    ONLINE = "online"


class Plan(SQLModel, table=True):
    """Una línea de la lista de precios: "Individual presencial · 4 clases" = 120 €."""

    __tablename__ = "plans"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=80)
    kind: PlanKind = PlanKind.DROP_IN
    format: PlanFormat = PlanFormat.GROUP
    modality: Modality = Modality.IN_PERSON
    price_cents: int = Field(ge=0)
    classes_included: int | None = Field(default=None, ge=1)  # solo bonos
    validity_days: int | None = Field(default=None, ge=1)  # solo bonos
    active: bool = True
    legacy_id: str | None = Field(default=None, index=True, unique=True, max_length=20)


class ScheduleSlot(SQLModel, table=True):
    """Franja semanal fija ("viernes 9:00, grupo"). Genera las clases de cada semana."""

    __tablename__ = "schedule_slots"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    weekday: int = Field(ge=0, le=6)  # 0 = lunes (como date.weekday())
    start_time: dt.time
    duration_min: int = Field(default=60, ge=1)
    plan_id: int = Field(foreign_key="plans.id")
    location: str | None = Field(default=None, max_length=80)
    active: bool = True


class ClassSession(SQLModel, table=True):
    """Una clase concreta en una fecha."""

    __tablename__ = "class_sessions"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True)
    start_time: dt.time
    duration_min: int = Field(default=60, ge=1)
    plan_id: int = Field(foreign_key="plans.id")
    # Copiado del plan al crearla: cambiar las tarifas no reescribe el pasado.
    price_cents: int = Field(ge=0)
    location: str | None = Field(default=None, max_length=80)
    notes: str | None = None
    schedule_slot_id: int | None = Field(default=None, foreign_key="schedule_slots.id")
    legacy_id: str | None = Field(default=None, index=True, unique=True, max_length=20)
