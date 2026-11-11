"""Reglas de alumnos: alta, búsqueda y ficha."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlmodel import Session, col, select

from katiu.attendance.models import Attendance
from katiu.classes.models import ClassSession, Plan
from katiu.core import clock
from katiu.importing.cleaning import clean_name, normalize_phone
from katiu.payments.service import balance_cents
from katiu.students.models import Student
from katiu.students.repository import StudentRepository


class StudentError(ValueError):
    pass


@dataclass(frozen=True)
class HistoryRow:
    session: ClassSession
    attendance: Attendance


@dataclass(frozen=True)
class StudentProfile:
    student: Student
    plan: Plan | None
    history: list[HistoryRow]
    balance_cents: int


def create_student(
    session: Session,
    full_name: str,
    phone: str | None = None,
    *,
    default_plan_id: int | None = None,
) -> Student:
    name = clean_name(full_name)
    if not name:
        raise StudentError("Falta el nombre.")
    phone_e164, issue = normalize_phone(phone)
    if issue:
        raise StudentError("Ese teléfono no parece válido. Escríbelo con prefijo, p. ej. +34…")
    student = StudentRepository(session).add(
        Student(
            full_name=name,
            phone_e164=phone_e164,
            default_plan_id=default_plan_id,
            started_on=clock.today(),
            active=True,
        )
    )
    session.commit()
    return student


def search(
    session: Session, query: str = "", *, include_inactive: bool = False
) -> Sequence[Student]:
    stmt = select(Student)
    if not include_inactive:
        stmt = stmt.where(col(Student.active))
    q = (query or "").strip()
    if q:
        stmt = stmt.where(col(Student.full_name).icontains(q))
    return session.exec(stmt.order_by(col(Student.full_name))).all()


def profile(session: Session, student_id: int, history_limit: int = 20) -> StudentProfile:
    student = StudentRepository(session).get(student_id)
    if student is None:
        raise StudentError("Ese alumno no existe.")
    plan = session.get(Plan, student.default_plan_id) if student.default_plan_id else None
    rows = session.exec(
        select(ClassSession, Attendance)
        .join(Attendance, col(Attendance.class_session_id) == ClassSession.id)
        .where(Attendance.student_id == student_id)
        .order_by(col(ClassSession.date).desc(), col(ClassSession.start_time).desc())
        .limit(history_limit)
    ).all()
    return StudentProfile(
        student=student,
        plan=plan,
        history=[HistoryRow(s, a) for s, a in rows],
        balance_cents=balance_cents(session, student_id),
    )
