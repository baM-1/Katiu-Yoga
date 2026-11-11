"""Pagos y bonos. El saldo NO se guarda: se calcula (ver payments/service.py, Fase 3)."""

from datetime import date
from enum import StrEnum

from sqlmodel import Field, SQLModel


class PaymentMethod(StrEnum):
    CASH = "cash"
    BIZUM = "bizum"
    TRANSFER = "transfer"
    OTHER = "other"


class PackPurchase(SQLModel, table=True):
    """Compra de un bono (4 u 8 clases, 60 días de vigencia)."""

    __tablename__ = "pack_purchases"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id", index=True)
    plan_id: int = Field(foreign_key="plans.id")
    purchased_on: date
    classes_total: int = Field(ge=1)
    price_cents: int = Field(ge=0)
    expires_on: date


class Payment(SQLModel, table=True):
    __tablename__ = "payments"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id", index=True)
    paid_on: date
    amount_cents: int = Field(gt=0)
    method: PaymentMethod = PaymentMethod.CASH
    concept: str | None = Field(default=None, max_length=200)
    attendance_id: int | None = Field(default=None, foreign_key="attendances.id")
    pack_purchase_id: int | None = Field(default=None, foreign_key="pack_purchases.id")
    legacy_id: str | None = Field(default=None, index=True, unique=True, max_length=20)
