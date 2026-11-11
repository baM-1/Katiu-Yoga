"""Asistencias: quién vino a qué clase."""

from enum import StrEnum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class AttendanceStatus(StrEnum):
    ATTENDED = "attended"
    LATE_CANCEL = "late_cancel"  # avisó con < 2 h: no vino, pero se cobra / descuenta del bono


class Attendance(SQLModel, table=True):
    __tablename__ = "attendances"  # pyright: ignore[reportAssignmentType]
    # Un alumno no puede estar dos veces en la misma clase: lo garantiza la BD, no la interfaz.
    __table_args__ = (UniqueConstraint("class_session_id", "student_id"),)

    id: int | None = Field(default=None, primary_key=True)
    class_session_id: int = Field(foreign_key="class_sessions.id", index=True)
    student_id: int = Field(foreign_key="students.id", index=True)
    status: AttendanceStatus = AttendanceStatus.ATTENDED
    price_cents: int = Field(ge=0)  # copiado de la clase
    pack_purchase_id: int | None = Field(default=None, foreign_key="pack_purchases.id")
    notes: str | None = None
    legacy_id: str | None = Field(default=None, index=True, unique=True, max_length=20)
