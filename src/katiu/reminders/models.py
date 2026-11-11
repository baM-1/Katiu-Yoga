"""Registro de recordatorios enviados (para no enviar dos veces el mismo)."""

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from katiu.core.models import utcnow


class ReminderKind(StrEnum):
    BIRTHDAY = "birthday"
    ANNIVERSARY = "anniversary"
    PAYMENT_DUE = "payment_due"


class ReminderChannel(StrEnum):
    WHATSAPP_LINK = "whatsapp_link"
    WHATSAPP_API = "whatsapp_api"
    EMAIL = "email"


class ReminderLog(SQLModel, table=True):
    __tablename__ = "reminder_logs"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id", index=True)
    kind: ReminderKind
    channel: ReminderChannel
    sent_at: datetime = Field(default_factory=utcnow)
    message: str
