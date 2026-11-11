"""Dinero: saldos y pagos. El saldo NUNCA se guarda: se calcula a partir de los hechos."""

from datetime import date

from sqlmodel import Session, col, func, select

from katiu.attendance.models import Attendance
from katiu.payments.models import Payment, PaymentMethod
from katiu.payments.repository import PaymentRepository


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
