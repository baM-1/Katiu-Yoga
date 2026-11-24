"""Reglas de clases: horario recurrente, generación automática de la semana y clases extra.

Kat nunca "crea" las clases normales: salen solas del horario (ScheduleSlot). Solo crea a mano
las extra (un taller, una clase privada puntual).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, time, timedelta

from sqlmodel import Session, col, func, select

from katiu.attendance.models import Attendance
from katiu.classes.models import ClassSession, Plan, ScheduleSlot
from katiu.classes.repository import ClassSessionRepository, PlanRepository, ScheduleSlotRepository

GENERATION_DAYS = 14  # siempre hay dos semanas de clases generadas por delante

WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class ClassError(ValueError):
    pass


@dataclass(frozen=True)
class SessionCard:
    """Lo que necesita una tarjeta de clase en la pantalla Hoy."""

    session: ClassSession
    plan: Plan
    attendees: int


def generate_sessions(session: Session, start: date, days: int = GENERATION_DAYS) -> int:
    """Crea las clases del horario entre `start` y `start + days`. Idempotente: si una franja ya
    tiene su clase ese día, no la duplica. Devuelve cuántas creó."""
    slots = session.exec(select(ScheduleSlot).where(col(ScheduleSlot.active))).all()
    if not slots:
        return 0
    end = start + timedelta(days=days)
    in_range = session.exec(
        select(ClassSession).where(
            col(ClassSession.date) >= start,
            col(ClassSession.date) < end,
        )
    ).all()
    # Una franja con su clase ese día (aunque esté cancelada: cancelar no es "falta crearla")…
    existing = {(s.schedule_slot_id, s.date) for s in in_range if s.schedule_slot_id is not None}
    # …o ya hay otra clase activa a esa misma hora (p. ej. una movida ahí): no se duplica.
    taken = {(s.date, s.start_time) for s in in_range if not s.cancelled}
    plans = {p.id: p for p in session.exec(select(Plan)).all()}
    repo = ClassSessionRepository(session)
    created = 0
    for offset in range(days):
        day = start + timedelta(days=offset)
        for slot in slots:
            if slot.weekday != day.weekday() or (slot.id, day) in existing:
                continue
            if (day, slot.start_time) in taken:
                continue
            plan = plans[slot.plan_id]
            repo.add(
                ClassSession(
                    date=day,
                    start_time=slot.start_time,
                    duration_min=slot.duration_min,
                    plan_id=slot.plan_id,
                    price_cents=plan.price_cents,
                    location=slot.location,
                    schedule_slot_id=slot.id,
                )
            )
            created += 1
    if created:
        session.commit()
    return created


def _cards(session: Session, sessions: Sequence[ClassSession]) -> list[SessionCard]:
    if not sessions:
        return []
    ids = [s.id for s in sessions]
    counts: dict[int, int] = dict(
        session.exec(
            select(col(Attendance.class_session_id), func.count())
            .where(col(Attendance.class_session_id).in_(ids))
            .group_by(col(Attendance.class_session_id))
        ).all()
    )
    plans = {p.id: p for p in session.exec(select(Plan)).all()}
    return [SessionCard(s, plans[s.plan_id], counts.get(s.id or 0, 0)) for s in sessions]


def today_cards(session: Session, today: date) -> tuple[list[SessionCard], list[SessionCard]]:
    """(clases de hoy, próximas clases). Genera antes las que falten."""
    generate_sessions(session, today)
    todays = ClassSessionRepository(session).on_date(today)
    upcoming = session.exec(
        select(ClassSession)
        .where(col(ClassSession.date) > today)
        .order_by(col(ClassSession.date), col(ClassSession.start_time))
        .limit(3)
    ).all()
    return _cards(session, todays), _cards(session, upcoming)


def create_extra_class(
    session: Session, day: date, start: time, plan_id: int, duration_min: int = 60
) -> ClassSession:
    plan = PlanRepository(session).get(plan_id)
    if plan is None:
        raise ClassError("Ese tipo de clase no existe.")
    cls = ClassSessionRepository(session).add(
        ClassSession(
            date=day,
            start_time=start,
            duration_min=duration_min,
            plan_id=plan_id,
            price_cents=plan.price_cents,
            notes="Clase extra",
        )
    )
    session.commit()
    return cls


def add_slot(
    session: Session, weekday: int, start: time, plan_id: int, duration_min: int = 60
) -> ScheduleSlot:
    if not 0 <= weekday <= 6:
        raise ClassError("Día de la semana no válido.")
    if PlanRepository(session).get(plan_id) is None:
        raise ClassError("Ese tipo de clase no existe.")
    clash = session.exec(
        select(ScheduleSlot).where(
            col(ScheduleSlot.active),
            ScheduleSlot.weekday == weekday,
            ScheduleSlot.start_time == start,
        )
    ).first()
    if clash:
        raise ClassError(f"Ya hay una clase los {WEEKDAYS[weekday]} a las {start:%H:%M}.")
    slot = ScheduleSlotRepository(session).add(
        ScheduleSlot(weekday=weekday, start_time=start, plan_id=plan_id, duration_min=duration_min)
    )
    session.commit()
    return slot


def deactivate_slot(session: Session, slot_id: int, today: date) -> None:
    """Pausa una franja y retira sus clases futuras que aún no tengan a nadie apuntado."""
    slot = ScheduleSlotRepository(session).get(slot_id)
    if slot is None:
        raise ClassError("Ese horario no existe.")
    slot.active = False
    session.add(slot)
    future = session.exec(
        select(ClassSession).where(
            ClassSession.schedule_slot_id == slot_id, col(ClassSession.date) >= today
        )
    ).all()
    for cls in future:
        has_people = session.exec(
            select(Attendance.id).where(Attendance.class_session_id == cls.id)
        ).first()
        if not has_people:
            session.delete(cls)
    session.commit()


WEEKDAY_SHORT = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def _get_session(session: Session, class_id: int) -> ClassSession:
    cls = ClassSessionRepository(session).get(class_id)
    if cls is None:
        raise ClassError("Esa clase no existe.")
    return cls


def _attendees(session: Session, class_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(Attendance).where(Attendance.class_session_id == class_id)
    ).one()


def _must_be_empty(session: Session, cls: ClassSession, verb: str) -> None:
    people = _attendees(session, cls.id or 0)
    if people:
        who = "1 persona marcada" if people == 1 else f"{people} personas marcadas"
        raise ClassError(f"Hay {who}. Quítalas de la lista antes de {verb} la clase.")


def cancel_class(session: Session, class_id: int) -> ClassSession:
    """Quita una clase concreta ("este viernes no hay clase"). Se marca, no se borra: si se
    borrara, el horario la volvería a crear. Solo si nadie está marcado (no se pierden cobros)."""
    cls = _get_session(session, class_id)
    if cls.cancelled:
        raise ClassError("Esa clase ya está cancelada.")
    _must_be_empty(session, cls, "cancelar")
    cls.cancelled = True
    session.add(cls)
    session.commit()
    return cls


def restore_class(session: Session, class_id: int) -> ClassSession:
    """Deshace una cancelación."""
    cls = _get_session(session, class_id)
    if not cls.cancelled:
        raise ClassError("Esa clase no está cancelada.")
    clash = session.exec(
        select(ClassSession).where(
            ClassSession.date == cls.date,
            ClassSession.start_time == cls.start_time,
            col(ClassSession.id) != cls.id,
            col(ClassSession.cancelled).is_(False),
        )
    ).first()
    if clash:
        raise ClassError(f"Ya hay otra clase ese día a las {cls.start_time:%H:%M}.")
    cls.cancelled = False
    session.add(cls)
    session.commit()
    return cls


def move_class(session: Session, class_id: int, day: date, start: time) -> ClassSession:
    """Mueve UNA clase (solo esa semana): cancela la original y crea una extra en la nueva fecha
    y hora con el mismo tipo, duración y lugar. Devuelve la nueva."""
    cls = _get_session(session, class_id)
    if cls.cancelled:
        raise ClassError("Esa clase está cancelada. Reactívala antes de moverla.")
    if (day, start) == (cls.date, cls.start_time):
        raise ClassError("Es la misma fecha y hora. Elige otra.")
    _must_be_empty(session, cls, "mover")
    clash = session.exec(
        select(ClassSession).where(
            ClassSession.date == day,
            ClassSession.start_time == start,
            col(ClassSession.cancelled).is_(False),
        )
    ).first()
    if clash:
        raise ClassError(f"Ya hay una clase ese día a las {start:%H:%M}.")
    cls.cancelled = True
    session.add(cls)
    moved = ClassSessionRepository(session).add(
        ClassSession(
            date=day,
            start_time=start,
            duration_min=cls.duration_min,
            plan_id=cls.plan_id,
            price_cents=cls.price_cents,
            location=cls.location,
            notes=f"Movida desde el {WEEKDAY_SHORT[cls.date.weekday()]} "
            f"{cls.date:%d/%m} {cls.start_time:%H:%M}",
        )
    )
    session.commit()
    return moved


def change_slot(
    session: Session,
    slot_id: int,
    weekday: int,
    start: time,
    duration_min: int,
    today: date,
) -> ScheduleSlot:
    """Cambia una clase fija de día u hora para siempre (de aquí en adelante). Las próximas
    clases vacías de esa franja se quitan y se vuelven a crear con el horario nuevo; las que ya
    tienen gente marcada o están canceladas se respetan."""
    slot = ScheduleSlotRepository(session).get(slot_id)
    if slot is None or not slot.active:
        raise ClassError("Ese horario no existe.")
    if not 0 <= weekday <= 6:
        raise ClassError("Día de la semana no válido.")
    if duration_min < 15:
        raise ClassError("La clase tiene que durar al menos 15 minutos.")
    clash = session.exec(
        select(ScheduleSlot).where(
            col(ScheduleSlot.active),
            ScheduleSlot.weekday == weekday,
            ScheduleSlot.start_time == start,
            col(ScheduleSlot.id) != slot_id,
        )
    ).first()
    if clash:
        raise ClassError(f"Ya hay una clase los {WEEKDAYS[weekday]} a las {start:%H:%M}.")
    slot.weekday, slot.start_time, slot.duration_min = weekday, start, duration_min
    session.add(slot)
    future = session.exec(
        select(ClassSession).where(
            ClassSession.schedule_slot_id == slot_id,
            col(ClassSession.date) >= today,
            col(ClassSession.cancelled).is_(False),
        )
    ).all()
    for cls in future:
        if not _attendees(session, cls.id or 0):
            session.delete(cls)
    session.commit()
    generate_sessions(session, today)
    return slot


def active_slots(session: Session) -> list[tuple[ScheduleSlot, Plan]]:
    rows = session.exec(
        select(ScheduleSlot, Plan)
        .join(Plan, col(Plan.id) == ScheduleSlot.plan_id)
        .where(col(ScheduleSlot.active))
        .order_by(col(ScheduleSlot.weekday), col(ScheduleSlot.start_time))
    ).all()
    return [(s, p) for s, p in rows]
