"""Dinero: saldos y pagos. El saldo NUNCA se guarda: se calcula a partir de los hechos."""

from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, col, func, select

from katiu.attendance.models import Attendance
from katiu.classes.models import ClassSession
from katiu.payments.models import Payment, PaymentMethod
from katiu.payments.repository import PaymentRepository
from katiu.students.models import Student


def balance_cents(session: Session, student_id: int) -> int:
    """Lo que debe (positivo) o tiene a favor (negativo): Σ clases - Σ pagos."""
    owed = session.exec(
        select(func.coalesce(func.sum(Attendance.price_cents), 0)).where(
            Attendance.student_id == student_id, col(Attendance.pack_purchase_id).is_(None)
        )
    ).one()
    paid = session.exec(
        select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
            Payment.student_id == student_id, col(Payment.pack_purchase_id).is_(None)
        )
    ).one()
    return int(owed) - int(paid)


def pay_attendance(
    session: Session, attendance: Attendance, paid_on: date, method: PaymentMethod
) -> Payment:
    if attendance.id is None:
        raise ValueError("La asistencia no está guardada")
    payment = PaymentRepository(session).add(
        Payment(
            student_id=attendance.student_id,
            paid_on=paid_on,
            amount_cents=attendance.price_cents,
            method=method,
            concept="Clase",
            attendance_id=attendance.id,
        )
    )
    session.commit()
    return payment


def payment_for_attendance(session: Session, attendance_id: int) -> Payment | None:
    return session.exec(select(Payment).where(Payment.attendance_id == attendance_id)).first()


# --- Pantalla "Dinero": quién debe -------------------------------------------------------


@dataclass(frozen=True)
class UnpaidClass:
    """Una clase a la que vino y que aún no ha pagado."""

    session: ClassSession
    attendance: Attendance


@dataclass(frozen=True)
class Debtor:
    student: Student
    balance_cents: int  # el mismo número que "Debe X €" en su ficha
    unpaid: list[UnpaidClass]  # de la más antigua a la más reciente

    @property
    def since(self) -> date | None:
        return self.unpaid[0].session.date if self.unpaid else None


@dataclass(frozen=True)
class MoneyOverview:
    debtors: list[Debtor]

    @property
    def total_cents(self) -> int:
        return sum(d.balance_cents for d in self.debtors)

    @property
    def unpaid_count(self) -> int:
        return sum(len(d.unpaid) for d in self.debtors)


def _unpaid_classes(session: Session, student_id: int | None = None) -> list[UnpaidClass]:
    """Asistencias sin pago y fuera de bono (un bono ya se pagó al comprarlo)."""
    stmt = (
        select(ClassSession, Attendance)
        .join(Attendance, col(Attendance.class_session_id) == ClassSession.id)
        .outerjoin(Payment, col(Payment.attendance_id) == Attendance.id)
        .where(
            col(Payment.id).is_(None),
            col(Attendance.pack_purchase_id).is_(None),
            Attendance.price_cents > 0,
        )
        .order_by(col(ClassSession.date), col(ClassSession.start_time))
    )
    if student_id is not None:
        stmt = stmt.where(Attendance.student_id == student_id)
    return [UnpaidClass(s, a) for s, a in session.exec(stmt).all()]


def money_overview(session: Session) -> MoneyOverview:
    """Todos los que deben algo, de quien más debe a quien menos.

    El importe sale de `balance_cents` (el de la ficha), así las dos pantallas nunca discrepan.
    No filtra por "activo": si alguien dejó de venir y debe, Kat tiene que verlo igual.
    """
    by_student: dict[int, list[UnpaidClass]] = {}
    for row in _unpaid_classes(session):
        by_student.setdefault(row.attendance.student_id, []).append(row)
    debtors: list[Debtor] = []
    for student_id, unpaid in by_student.items():
        owed = balance_cents(session, student_id)
        student = session.get(Student, student_id)
        if owed > 0 and student is not None:
            debtors.append(Debtor(student, owed, unpaid))
    debtors.sort(key=lambda d: (-d.balance_cents, d.student.full_name.casefold()))
    return MoneyOverview(debtors)


class PaymentError(ValueError):
    pass


def collect_attendance(
    session: Session, attendance_id: int, paid_on: date, method: PaymentMethod
) -> Attendance:
    """Cobra una clase pendiente desde la pantalla Dinero. Si ya estaba pagada, no duplica."""
    attendance = session.get(Attendance, attendance_id)
    if attendance is None:
        raise PaymentError("Esa clase ya no está en la lista.")
    if attendance.pack_purchase_id is not None or payment_for_attendance(session, attendance_id):
        raise PaymentError("Esa clase ya estaba pagada.")
    pay_attendance(session, attendance, paid_on=paid_on, method=method)
    return attendance


def collect_all(session: Session, student_id: int, paid_on: date, method: PaymentMethod) -> int:
    """Cobra todas sus clases pendientes de una vez. Devuelve cuántas cobró."""
    unpaid = _unpaid_classes(session, student_id)
    for row in unpaid:
        pay_attendance(session, row.attendance, paid_on=paid_on, method=method)
    return len(unpaid)
