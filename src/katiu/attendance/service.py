"""Pasar lista. Las tres operaciones que importan: marcar, cobrar y (con cuidado) deshacer."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from sqlmodel import Session, col, select

from katiu.attendance.models import Attendance, AttendanceStatus
from katiu.attendance.repository import AttendanceRepository
from katiu.classes.models import ClassSession
from katiu.payments.models import Payment, PaymentMethod
from katiu.payments.service import pay_attendance
from katiu.students.models import Student
from katiu.students.service import create_student

REGULARS_LOOKBACK_DAYS = 120


class AttendanceError(ValueError):
    pass


@dataclass(frozen=True)
class RosterItem:
    student: Student
    attendance: Attendance | None
    payment: Payment | None
    visits_in_slot: int  # cuántas veces vino a esta misma franja (día + hora) últimamente

    @property
    def attended(self) -> bool:
        return self.attendance is not None

    @property
    def paid(self) -> bool:
        return self.payment is not None

    @property
    def is_regular(self) -> bool:
        return self.visits_in_slot >= 2


@dataclass(frozen=True)
class Totals:
    people: int
    collected_cents: int
    pending_cents: int


def _get_class(session: Session, class_session_id: int) -> ClassSession:
    cls = session.get(ClassSession, class_session_id)
    if cls is None:
        raise AttendanceError("Esa clase no existe.")
    return cls


def _visits_in_slot(session: Session, cls: ClassSession) -> Counter[int]:
    """Habituales: quién viene a ESTA franja (mismo día de la semana y misma hora)."""
    since = cls.date - timedelta(days=REGULARS_LOOKBACK_DAYS)
    rows = session.exec(
        select(col(Attendance.student_id), col(ClassSession.date))
        .join(ClassSession, col(ClassSession.id) == Attendance.class_session_id)
        .where(
            ClassSession.start_time == cls.start_time,
            col(ClassSession.date) >= since,
            col(ClassSession.date) < cls.date,
        )
    ).all()
    return Counter(sid for sid, day in rows if day.weekday() == cls.date.weekday())


def roster(session: Session, class_session_id: int) -> list[RosterItem]:
    """Alumnos para pasar lista: primero los habituales de la franja, luego el resto (A→Z).
    Incluye a cualquiera ya marcado aunque esté inactivo."""
    cls = _get_class(session, class_session_id)
    attendances = {a.student_id: a for a in AttendanceRepository(session).for_session(cls.id or 0)}
    payments = {
        p.attendance_id: p
        for p in session.exec(
            select(Payment).where(
                col(Payment.attendance_id).in_([a.id for a in attendances.values()])
            )
        ).all()
    }
    visits = _visits_in_slot(session, cls)
    students = session.exec(
        select(Student).where(col(Student.active) | col(Student.id).in_(list(attendances)))
    ).all()
    items = [
        RosterItem(
            student=s,
            attendance=(att := attendances.get(s.id or 0)),
            payment=payments.get(att.id) if att else None,
            visits_in_slot=visits[s.id or 0],
        )
        for s in students
    ]
    items.sort(key=lambda i: (-i.visits_in_slot, i.student.full_name.casefold()))
    return items


def roster_item(session: Session, class_session_id: int, student_id: int) -> RosterItem:
    for item in roster(session, class_session_id):
        if item.student.id == student_id:
            return item
    raise AttendanceError("Ese alumno no está en la lista.")


def toggle_attendance(session: Session, class_session_id: int, student_id: int) -> bool:
    """Marca o desmarca. Desmarcar borra también su pago de esa clase (la interfaz pide
    confirmación antes si estaba pagada). Devuelve True si queda marcado."""
    cls = _get_class(session, class_session_id)
    if session.get(Student, student_id) is None:
        raise AttendanceError("Ese alumno no existe.")
    existing = session.exec(
        select(Attendance).where(
            Attendance.class_session_id == class_session_id, Attendance.student_id == student_id
        )
    ).first()
    if existing:
        for payment in session.exec(
            select(Payment).where(Payment.attendance_id == existing.id)
        ).all():
            session.delete(payment)
        session.delete(existing)
        session.commit()
        return False
    AttendanceRepository(session).add(
        Attendance(
            class_session_id=class_session_id,
            student_id=student_id,
            status=AttendanceStatus.ATTENDED,
            price_cents=cls.price_cents,
        )
    )
    session.commit()
    return True


def toggle_paid(
    session: Session,
    class_session_id: int,
    student_id: int,
    today: date,
    method: PaymentMethod = PaymentMethod.CASH,
) -> bool:
    """Marca o desmarca "pagado". Si no estaba marcado como asistente, lo marca también:
    pagar implica que vino. Devuelve True si queda pagado."""
    att = session.exec(
        select(Attendance).where(
            Attendance.class_session_id == class_session_id, Attendance.student_id == student_id
        )
    ).first()
    if att is None:
        toggle_attendance(session, class_session_id, student_id)
        return toggle_paid(session, class_session_id, student_id, today, method)
    payment = session.exec(select(Payment).where(Payment.attendance_id == att.id)).first()
    if payment:
        session.delete(payment)
        session.commit()
        return False
    pay_attendance(session, att, paid_on=today, method=method)
    return True


def totals(session: Session, class_session_id: int) -> Totals:
    atts = AttendanceRepository(session).for_session(class_session_id)
    paid_ids = {
        p.attendance_id
        for p in session.exec(
            select(Payment).where(col(Payment.attendance_id).in_([a.id for a in atts]))
        ).all()
    }
    collected = sum(a.price_cents for a in atts if a.id in paid_ids)
    pending = sum(a.price_cents for a in atts if a.id not in paid_ids)
    return Totals(people=len(atts), collected_cents=collected, pending_cents=pending)


def quick_add(
    session: Session, class_session_id: int, full_name: str, phone: str | None
) -> Student:
    """Alta rápida desde la lista: crea al alumno con el plan de la clase y lo marca."""
    cls = _get_class(session, class_session_id)
    student = create_student(session, full_name, phone, default_plan_id=cls.plan_id)
    toggle_attendance(session, class_session_id, student.id or 0)
    return student
