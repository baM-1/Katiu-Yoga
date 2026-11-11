"""Reglas de alumnos: alta, edición, búsqueda y ficha."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, col, select

from katiu.attendance.models import Attendance
from katiu.classes.models import ClassSession, Plan
from katiu.core import clock
from katiu.importing.cleaning import clean_email, clean_name, clean_text, normalize_phone
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


@dataclass(frozen=True)
class StudentChanges:
    """Lo que llega del formulario de edición, ya convertido a tipos de Python."""

    full_name: str
    phone: str | None = None
    email: str | None = None
    birthday: date | None = None
    started_on: date | None = None
    location: str | None = None
    default_plan_id: int | None = None
    health_notes: str | None = None
    notes: str | None = None
    active: bool = True
    whatsapp_consent: bool = False


def update_student(session: Session, student_id: int, changes: StudentChanges) -> Student:
    """Guarda la ficha completa. Valida todo antes de tocar nada: o se guarda entero o nada."""
    student = StudentRepository(session).get(student_id)
    if student is None:
        raise StudentError("Ese alumno no existe.")

    name = clean_name(changes.full_name)
    if not name:
        raise StudentError("Falta el nombre.")
    phone_e164, issue = normalize_phone(changes.phone)
    if issue:
        raise StudentError("Ese teléfono no parece válido. Escríbelo con prefijo, p. ej. +34…")
    email = clean_text(changes.email)
    if email and clean_email(email) is None:
        raise StudentError("Ese email no parece válido.")
    if changes.birthday and changes.birthday > clock.today():
        raise StudentError("El cumpleaños no puede ser en el futuro.")
    if changes.default_plan_id is not None and session.get(Plan, changes.default_plan_id) is None:
        raise StudentError("Esa tarifa no existe.")

    student.full_name = name
    student.phone_e164 = phone_e164
    student.email = clean_email(email) if email else None
    student.birthday = changes.birthday
    student.started_on = changes.started_on
    student.location = clean_text(changes.location)
    student.default_plan_id = changes.default_plan_id
    # Salud y notas: se respetan los saltos de línea; solo se quitan espacios de los bordes.
    student.health_notes = (changes.health_notes or "").strip() or None
    student.notes = (changes.notes or "").strip() or None
    student.active = changes.active
    # El consentimiento guarda CUÁNDO se dio (RGPD). Si se retira, se borra la fecha.
    if changes.whatsapp_consent and not student.whatsapp_consent:
        student.whatsapp_consent_at = clock.now()
    elif not changes.whatsapp_consent:
        student.whatsapp_consent_at = None
    student.whatsapp_consent = changes.whatsapp_consent

    session.add(student)
    session.commit()
    return student


def plan_choices(session: Session, current_id: int | None = None) -> Sequence[Plan]:
    """Tarifas activas para el desplegable (y la actual aunque esté retirada)."""
    stmt = select(Plan).where(col(Plan.active) | (col(Plan.id) == current_id))
    return session.exec(stmt.order_by(col(Plan.name))).all()


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
