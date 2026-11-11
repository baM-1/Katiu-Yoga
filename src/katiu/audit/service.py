"""Escribir y leer el registro de actividad. Sin nada de HTTP."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, col, func, select

from katiu.accounts.models import User
from katiu.audit.models import AuditAction, AuditEvent, AuditTarget
from katiu.classes.models import ClassSession
from katiu.students.models import Student

LABELS: dict[AuditAction, str] = {
    AuditAction.LOGIN: "entró en la app",
    AuditAction.LOGIN_FAILED: "intento de entrada fallido",
    AuditAction.LOGOUT: "salió de la app",
    AuditAction.PASSWORD_CHANGED: "cambió su contraseña",
    AuditAction.STUDENT_CREATED: "creó una ficha",
    AuditAction.STUDENT_UPDATED: "editó una ficha",
    AuditAction.ATTENDANCE_TOGGLED: "marcó asistencia",
    AuditAction.PAYMENT_TOGGLED: "marcó un cobro",
    AuditAction.QUICK_ADD: "añadió alumno a una clase",
    AuditAction.SLOT_ADDED: "añadió un horario",
    AuditAction.SLOT_PAUSED: "pausó un horario",
    AuditAction.EXTRA_CLASS: "creó una clase extra",
    AuditAction.USER_CREATED: "creó un usuario",
    AuditAction.USER_PASSWORD_RESET: "puso contraseña nueva a un usuario",
    AuditAction.USER_ACTIVATED: "activó un usuario",
    AuditAction.USER_DEACTIVATED: "desactivó un usuario",
    AuditAction.EXPORT_DOWNLOADED: "descargó el Excel",
}


def record(
    session: Session,
    user_id: int | None,
    action: AuditAction,
    target_type: AuditTarget | None = None,
    target_id: int | None = None,
    detail: str | None = None,
) -> AuditEvent:
    """Apunta un evento y confirma. Va en su propia transacción: si lo que se audita ya se
    guardó, el registro no puede deshacerlo; y si falla el registro, no rompe la acción."""
    event = AuditEvent(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    session.add(event)
    session.commit()
    return event


@dataclass(frozen=True)
class EventView:
    at: datetime
    who: str
    what: str
    target: str | None
    target_url: str | None
    alert: bool


def _target(
    session: Session, kind: AuditTarget | None, target_id: int | None
) -> tuple[str | None, str | None]:
    if kind is None or target_id is None:
        return None, None
    if kind == AuditTarget.STUDENT:
        student = session.get(Student, target_id)
        name = student.full_name if student else f"alumno #{target_id}"
        return name, f"/alumnos/{target_id}"
    if kind == AuditTarget.CLASS:
        cls = session.get(ClassSession, target_id)
        label = f"clase del {cls.date:%d/%m} {cls.start_time:%H:%M}" if cls else "clase"
        return label, f"/clases/{target_id}"
    if kind == AuditTarget.USER:
        user = session.get(User, target_id)
        return (user.display_name if user else f"usuario #{target_id}"), None
    return f"horario #{target_id}", "/ajustes/horario"


def recent(session: Session, limit: int = 100) -> list[EventView]:
    """Los últimos eventos, ya "traducidos" para mostrarlos."""
    events = session.exec(
        select(AuditEvent)
        .order_by(col(AuditEvent.at).desc(), col(AuditEvent.id).desc())
        .limit(limit)
    ).all()
    names = {u.id: u.display_name for u in session.exec(select(User)).all()}
    out: list[EventView] = []
    for e in events:
        target, url = _target(session, e.target_type, e.target_id)
        what = LABELS[e.action] + (f" ({e.detail})" if e.detail else "")
        out.append(
            EventView(
                at=e.at,
                who=names.get(e.user_id, "Alguien") if e.user_id else "Alguien",
                what=what,
                target=target,
                target_url=url,
                alert=e.action == AuditAction.LOGIN_FAILED,
            )
        )
    return out


def last_logins(session: Session) -> dict[int, datetime]:
    """Última entrada de cada usuario."""
    rows: Sequence[tuple[int | None, datetime]] = session.exec(
        select(AuditEvent.user_id, func.max(AuditEvent.at))
        .where(AuditEvent.action == AuditAction.LOGIN)
        .group_by(col(AuditEvent.user_id))
    ).all()
    return {uid: at for uid, at in rows if uid is not None}


def failed_logins_since(session: Session, since: datetime) -> int:
    return session.exec(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.action == AuditAction.LOGIN_FAILED, col(AuditEvent.at) >= since)
    ).one()
