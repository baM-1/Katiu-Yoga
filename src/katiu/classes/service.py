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
    existing = {
        (s.schedule_slot_id, s.date)
        for s in session.exec(
            select(ClassSession).where(
                col(ClassSession.schedule_slot_id).is_not(None),
                col(ClassSession.date) >= start,
                col(ClassSession.date) < end,
            )
        ).all()
    }
    plans = {p.id: p for p in session.exec(select(Plan)).all()}
    repo = ClassSessionRepository(session)
    created = 0
    for offset in range(days):
        day = start + timedelta(days=offset)
        for slot in slots:
            if slot.weekday != day.weekday() or (slot.id, day) in existing:
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


def active_slots(session: Session) -> list[tuple[ScheduleSlot, Plan]]:
    rows = session.exec(
        select(ScheduleSlot, Plan)
        .join(Plan, col(Plan.id) == ScheduleSlot.plan_id)
        .where(col(ScheduleSlot.active))
        .order_by(col(ScheduleSlot.weekday), col(ScheduleSlot.start_time))
    ).all()
    return [(s, p) for s, p in rows]
