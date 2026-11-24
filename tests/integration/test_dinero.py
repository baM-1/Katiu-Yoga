"""Dinero: quién debe sale de las asistencias sin pagar, y se puede cobrar desde ahí."""

from datetime import date, time

from fastapi.testclient import TestClient
from sqlmodel import Session

from katiu.attendance import service as attendance
from katiu.classes import service as classes
from katiu.classes.models import ClassSession, Plan
from katiu.payments import service as money
from katiu.payments.models import PaymentMethod
from katiu.payments.service import balance_cents
from katiu.students.models import Student

TODAY = date(2026, 11, 24)


def test_sin_deudas_nadie_sale(session: Session, students: list[Student]) -> None:
    assert money.money_overview(session).debtors == []


def test_quien_vino_y_no_pago_sale_en_dinero(
    session: Session, friday_class: ClassSession, students: list[Student], group_plan: Plan
) -> None:
    ana, bea, carla, _ = students
    later = classes.create_extra_class(session, date(2026, 11, 20), time(9, 0), group_plan.id or 0)
    for cls in (friday_class, later):
        attendance.toggle_attendance(session, cls.id or 0, ana.id or 0)
    attendance.toggle_attendance(session, friday_class.id or 0, bea.id or 0)
    attendance.toggle_paid(session, friday_class.id or 0, bea.id or 0, TODAY)  # Bea pagó
    attendance.toggle_attendance(session, friday_class.id or 0, carla.id or 0)
    carla.active = False  # aunque ya no venga, si debe, Kat lo tiene que ver
    session.add(carla)
    session.commit()

    o = money.money_overview(session)
    assert [d.student.full_name for d in o.debtors] == ["Ana Prueba", "Carla Inventada"]
    ana_debt = o.debtors[0]
    assert ana_debt.balance_cents == 6000 == balance_cents(session, ana.id or 0)
    assert len(ana_debt.unpaid) == 2 and ana_debt.since == friday_class.date
    assert o.total_cents == 9000 and o.unpaid_count == 3


def test_cobrar_una_y_todo(
    session: Session, friday_class: ClassSession, students: list[Student], group_plan: Plan
) -> None:
    ana = students[0]
    later = classes.create_extra_class(session, date(2026, 11, 20), time(9, 0), group_plan.id or 0)
    for cls in (friday_class, later):
        attendance.toggle_attendance(session, cls.id or 0, ana.id or 0)
    first = money.money_overview(session).debtors[0].unpaid[0].attendance

    money.collect_attendance(session, first.id or 0, TODAY, PaymentMethod.CASH)
    assert balance_cents(session, ana.id or 0) == 3000
    try:
        money.collect_attendance(session, first.id or 0, TODAY, PaymentMethod.CASH)
        raise AssertionError("no debe cobrar dos veces")
    except money.PaymentError:
        pass

    assert money.collect_all(session, ana.id or 0, TODAY, PaymentMethod.CASH) == 1
    assert balance_cents(session, ana.id or 0) == 0
    assert money.money_overview(session).debtors == []


def test_pantalla_dinero(
    logged: TestClient, session: Session, friday_class: ClassSession, students: list[Student]
) -> None:
    empty = logged.get("/dinero")
    assert empty.status_code == 200 and "Nadie te debe nada" in empty.text

    ana = students[0]
    ana.phone_e164 = "+34600111222"
    session.add(ana)
    session.commit()
    logged.post(f"/clases/{friday_class.id}/alumnos/{ana.id}/asistencia")

    page = logged.get("/dinero")
    assert "Ana Prueba" in page.text and "Te deben" in page.text and "30 €" in page.text
    assert "wa.me/34600111222?text=" in page.text

    res = logged.post(f"/dinero/alumnos/{ana.id}/cobrar-todo", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "/dinero?ok=todo"
    assert "Nadie te debe nada" in logged.get("/dinero?ok=todo").text
