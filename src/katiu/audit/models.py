"""Registro de actividad (auditoría).

Tabla de solo añadir: nunca se edita ni se borra una fila. Guarda QUÉ pasó y sobre QUÉ (tipo e
id), nunca el contenido: ni nombres, ni teléfonos, ni datos de salud. Si alguien necesita ver
de quién se trata, la pantalla une el id con la ficha en el momento de mostrarla.
"""

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from katiu.core.models import utcnow


class AuditAction(StrEnum):
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGED = "password_changed"
    STUDENT_CREATED = "student_created"
    STUDENT_UPDATED = "student_updated"
    ATTENDANCE_TOGGLED = "attendance_toggled"
    PAYMENT_TOGGLED = "payment_toggled"
    QUICK_ADD = "quick_add"
    SLOT_ADDED = "slot_added"
    SLOT_PAUSED = "slot_paused"
    EXTRA_CLASS = "extra_class"
    USER_CREATED = "user_created"
    USER_PASSWORD_RESET = "user_password_reset"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    EXPORT_DOWNLOADED = "export_downloaded"


class AuditTarget(StrEnum):
    STUDENT = "student"
    CLASS = "class"
    SLOT = "slot"
    USER = "user"


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_events"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    at: datetime = Field(default_factory=utcnow, index=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    action: AuditAction
    target_type: AuditTarget | None = None
    target_id: int | None = None
    # Detalle corto y NO personal ("sí"/"no", "con salud"…). Nunca texto libre del usuario.
    detail: str | None = Field(default=None, max_length=80)
