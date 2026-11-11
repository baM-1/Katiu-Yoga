"""Alumnos."""

from datetime import date, datetime

from sqlmodel import Field, SQLModel


class Student(SQLModel, table=True):
    __tablename__ = "students"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    full_name: str = Field(index=True, max_length=120)
    phone_e164: str | None = Field(default=None, max_length=20)  # +34XXXXXXXXX
    email: str | None = Field(default=None, max_length=254)
    birthday: date | None = None
    started_on: date | None = None  # fecha de inicio con Katiu Yoga = "aniversario" (D2)
    default_plan_id: int | None = Field(default=None, foreign_key="plans.id")
    location: str | None = Field(default=None, max_length=80)
    health_notes: str | None = None  # DATO SENSIBLE (RGPD): solo en la ficha, nunca en listados
    notes: str | None = None
    active: bool = True
    whatsapp_consent: bool = False
    whatsapp_consent_at: datetime | None = None
    legacy_id: str | None = Field(default=None, index=True, unique=True, max_length=20)
