from datetime import date, time, timedelta

import pytest
from sqlmodel import Session, select

from katiu.attendance.service import toggle_attendance
from katiu.classes import service
from katiu.classes.models import ClassSession, Plan
from katiu.students.models import Student
from tests.conftest import FRIDAY

MONDAY = FRIDAY - timedelta(days=4)


def _friday_slots(session: Session, plan: Plan) -> None:
    service.add_slot(session, 4, time(9, 0), plan.id or 0)
    service.add_slot(session, 4, time(10, 15), plan.id or 0)


def test_genera_las_clases_de_la_semana(session: Session, group_plan: Plan) -> None:
    _friday_slots(session, group_plan)
    created = service.generate_sessions(session, MONDAY, days=14)
    assert created == 4  # 2 viernes x 2 franjas
    sessions = session.exec(select(ClassSession)).all()
    assert {s.date for s in sessions} == {FRIDAY, FRIDAY + timedelta(days=7)}
    assert {s.start_time for s in sessions} == {time(9, 0), time(10, 15)}
    assert all(s.price_cents == group_plan.price_cents for s in sessions)


def test_generar_es_idempotente(session: Session, group_plan: Plan) -> None:
    _friday_slots(session, group_plan)
    service.generate_sessions(session, MONDAY)
    assert service.generate_sessions(session, MONDAY) == 0


def test_no_permite_dos_franjas_iguales(session: Session, group_plan: Plan) -> None:
    service.add_slot(session, 4, time(9, 0), group_plan.id or 0)
    with pytest.raises(service.ClassError, match="Ya hay una clase"):
        service.add_slot(session, 4, time(9, 0), group_plan.id or 0)


def test_hoy_y_proximas(session: Session, group_plan: Plan) -> None:
    _friday_slots(session, group_plan)
    todays, upcoming = service.today_cards(session, FRIDAY)
    assert [c.session.start_time for c in todays] == [time(9, 0), time(10, 15)]
    assert upcoming and upcoming[0].session.date == FRIDAY + timedelta(days=7)
    todays_monday, upcoming_monday = service.today_cards(session, MONDAY)
    assert todays_monday == []
    assert upcoming_monday[0].session.date == FRIDAY


def test_pausar_franja_borra_solo_clases_futuras_vacias(
    session: Session, group_plan: Plan, students: list[Student]
) -> None:
    _friday_slots(session, group_plan)
    service.generate_sessions(session, MONDAY)
    nine = session.exec(select(ClassSession).where(ClassSession.start_time == time(9, 0))).all()
    with_people = nine[0]
    toggle_attendance(session, with_people.id or 0, students[0].id or 0)
    service.deactivate_slot(session, with_people.schedule_slot_id or 0, MONDAY)
    left = session.exec(select(ClassSession).where(ClassSession.start_time == time(9, 0))).all()
    assert [c.id for c in left] == [with_people.id]  # la que tiene gente se queda
    assert service.generate_sessions(session, MONDAY) == 0  # y no se regeneran


def test_clase_extra(session: Session, group_plan: Plan) -> None:
    cls = service.create_extra_class(session, date(2026, 12, 1), time(18, 0), group_plan.id or 0)
    assert cls.schedule_slot_id is None
    assert cls.price_cents == 3000
