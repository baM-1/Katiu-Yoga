from datetime import time, timedelta

from sqlmodel import Session, select

from katiu.attendance import service
from katiu.classes.models import ClassSession, Plan
from katiu.classes.service import create_extra_class
from katiu.payments.models import Payment
from katiu.payments.service import balance_cents
from katiu.students.models import Student
from tests.conftest import FRIDAY


def test_marcar_y_desmarcar(
    session: Session, friday_class: ClassSession, students: list[Student]
) -> None:
    cid, sid = friday_class.id or 0, students[0].id or 0
    assert service.toggle_attendance(session, cid, sid) is True
    assert service.totals(session, cid).people == 1
    assert service.toggle_attendance(session, cid, sid) is False
    assert service.totals(session, cid).people == 0


def test_cobrar_y_totales(
    session: Session, friday_class: ClassSession, students: list[Student]
) -> None:
    cid = friday_class.id or 0
    for s in students[:3]:
        service.toggle_attendance(session, cid, s.id or 0)
    service.toggle_paid(session, cid, students[0].id or 0, FRIDAY)
    t = service.totals(session, cid)
    assert (t.people, t.collected_cents, t.pending_cents) == (3, 3000, 6000)
    assert balance_cents(session, students[0].id or 0) == 0
    assert balance_cents(session, students[1].id or 0) == 3000


def test_pagar_sin_marcar_marca_tambien(
    session: Session, friday_class: ClassSession, students: list[Student]
) -> None:
    cid, sid = friday_class.id or 0, students[0].id or 0
    assert service.toggle_paid(session, cid, sid, FRIDAY) is True
    item = service.roster_item(session, cid, sid)
    assert item.attended and item.paid


def test_desmarcar_borra_el_pago(
    session: Session, friday_class: ClassSession, students: list[Student]
) -> None:
    cid, sid = friday_class.id or 0, students[0].id or 0
    service.toggle_paid(session, cid, sid, FRIDAY)
    service.toggle_attendance(session, cid, sid)
    assert session.exec(select(Payment)).all() == []
    assert balance_cents(session, sid) == 0


def test_habituales_primero(session: Session, group_plan: Plan, students: list[Student]) -> None:
    # Dani viene los dos viernes anteriores a las 9:00 → habitual; Ana vino a otra hora.
    for weeks in (1, 2):
        past = create_extra_class(
            session, FRIDAY - timedelta(weeks=weeks), time(9, 0), group_plan.id or 0
        )
        service.toggle_attendance(session, past.id or 0, students[3].id or 0)
        other = create_extra_class(
            session, FRIDAY - timedelta(weeks=weeks), time(18, 0), group_plan.id or 0
        )
        service.toggle_attendance(session, other.id or 0, students[0].id or 0)
    today = create_extra_class(session, FRIDAY, time(9, 0), group_plan.id or 0)
    items = service.roster(session, today.id or 0)
    assert items[0].student.full_name == "Dani Demo"
    assert items[0].is_regular
    assert not next(i for i in items if i.student.full_name == "Ana Prueba").is_regular


def test_inactivos_no_salen_salvo_si_ya_estan_marcados(
    session: Session, friday_class: ClassSession, students: list[Student]
) -> None:
    cid = friday_class.id or 0
    service.toggle_attendance(session, cid, students[0].id or 0)
    students[0].active = False
    students[1].active = False
    session.add_all(students[:2])
    session.commit()
    names = {i.student.full_name for i in service.roster(session, cid)}
    assert "Ana Prueba" in names and "Bea Ficticia" not in names


def test_alta_rapida(session: Session, friday_class: ClassSession) -> None:
    student = service.quick_add(session, friday_class.id or 0, "  Nueva  Alumna ", "600 111 222")
    assert student.full_name == "Nueva Alumna"
    assert student.phone_e164 == "+34600111222"
    assert student.default_plan_id == friday_class.plan_id
    assert service.totals(session, friday_class.id or 0).people == 1
