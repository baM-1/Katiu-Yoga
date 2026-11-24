"""Cambios de horario: cancelar una clase, moverla solo una semana y cambiar una clase fija."""

from datetime import date, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from katiu.attendance import service as attendance
from katiu.audit.models import AuditAction, AuditEvent
from katiu.classes import service
from katiu.classes.models import ClassSession, Plan, ScheduleSlot
from katiu.students.models import Student
from tests.conftest import FRIDAY, csrf_from

MONDAY = FRIDAY - timedelta(days=4)  # lunes 9/11: los viernes 13 y 20 caen en la ventana


@pytest.fixture
def friday_slot(session: Session, group_plan: Plan) -> ScheduleSlot:
    slot = service.add_slot(session, 4, time(9), group_plan.id or 0)
    service.generate_sessions(session, MONDAY)
    return slot


def _fridays(session: Session, slot: ScheduleSlot) -> list[ClassSession]:
    return list(
        session.exec(
            select(ClassSession)
            .where(ClassSession.schedule_slot_id == slot.id)
            .order_by(col(ClassSession.date))
        ).all()
    )


def test_cancelar_no_se_regenera(session: Session, friday_slot: ScheduleSlot) -> None:
    first = _fridays(session, friday_slot)[0]
    service.cancel_class(session, first.id or 0)
    assert service.generate_sessions(session, MONDAY) == 0  # no vuelve a aparecer
    session.refresh(first)
    assert first.cancelled
    todays, _ = service.today_cards(session, first.date)
    assert [c.session.cancelled for c in todays] == [True]
    service.restore_class(session, first.id or 0)
    session.refresh(first)
    assert not first.cancelled


def test_cancelar_con_gente_no_deja(
    session: Session, friday_slot: ScheduleSlot, students: list[Student]
) -> None:
    first = _fridays(session, friday_slot)[0]
    attendance.toggle_attendance(session, first.id or 0, students[0].id or 0)
    with pytest.raises(service.ClassError, match="1 persona marcada"):
        service.cancel_class(session, first.id or 0)


def test_clase_cancelada_no_deja_pasar_lista(
    session: Session, friday_slot: ScheduleSlot, students: list[Student]
) -> None:
    first = _fridays(session, friday_slot)[0]
    service.cancel_class(session, first.id or 0)
    with pytest.raises(attendance.AttendanceError, match="cancelada"):
        attendance.toggle_attendance(session, first.id or 0, students[0].id or 0)


def test_mover_solo_una_semana(session: Session, friday_slot: ScheduleSlot) -> None:
    first = _fridays(session, friday_slot)[0]
    moved = service.move_class(session, first.id or 0, first.date, time(10, 15))
    session.refresh(first)
    assert first.cancelled and not moved.cancelled
    assert (moved.date, moved.start_time, moved.schedule_slot_id) == (
        first.date,
        time(10, 15),
        None,
    )
    assert moved.notes and "Movida" in moved.notes
    assert service.generate_sessions(session, MONDAY) == 0  # el viernes 9:00 no reaparece
    # La semana siguiente sigue a las 9:00.
    assert _fridays(session, friday_slot)[1].start_time == time(9)


def test_mover_a_una_hora_ocupada(
    session: Session, friday_slot: ScheduleSlot, group_plan: Plan
) -> None:
    first = _fridays(session, friday_slot)[0]
    service.create_extra_class(session, first.date, time(18), group_plan.id or 0)
    with pytest.raises(service.ClassError, match="Ya hay una clase"):
        service.move_class(session, first.id or 0, first.date, time(18))


def test_mover_a_un_hueco_del_horario_no_duplica(session: Session, group_plan: Plan) -> None:
    """Si muevo una clase a un día y hora en el que el horario creará clase más adelante,
    no aparecen dos clases a la misma hora."""
    extra = service.create_extra_class(session, MONDAY, time(9), group_plan.id or 0)
    service.move_class(session, extra.id or 0, date(2026, 11, 27), time(9))
    service.add_slot(session, 4, time(9), group_plan.id or 0)
    service.generate_sessions(session, date(2026, 11, 23))
    at_27 = session.exec(
        select(ClassSession).where(
            ClassSession.date == date(2026, 11, 27), col(ClassSession.cancelled).is_(False)
        )
    ).all()
    assert len(at_27) == 1


def test_cambiar_hora_fija(
    session: Session, friday_slot: ScheduleSlot, students: list[Student]
) -> None:
    first, second = _fridays(session, friday_slot)
    attendance.toggle_attendance(session, first.id or 0, students[0].id or 0)
    service.change_slot(session, friday_slot.id or 0, 3, time(18), 75, MONDAY)
    sessions = _fridays(session, friday_slot)
    # La clase con gente se respeta; la vacía se rehace en jueves 18:00.
    assert first in sessions and second not in sessions
    new = [s for s in sessions if s.id != first.id]
    assert {(s.date.weekday(), s.start_time, s.duration_min) for s in new} == {(3, time(18), 75)}


def test_cambiar_hora_choca_con_otra(
    session: Session, friday_slot: ScheduleSlot, group_plan: Plan
) -> None:
    service.add_slot(session, 4, time(10, 15), group_plan.id or 0)
    with pytest.raises(service.ClassError, match="Ya hay una clase"):
        service.change_slot(session, friday_slot.id or 0, 4, time(10, 15), 60, MONDAY)


def test_pantallas(logged: TestClient, session: Session, friday_class: ClassSession) -> None:
    page = logged.get(f"/clases/{friday_class.id}")
    assert "Cancelar o mover esta clase" in page.text
    token = csrf_from(page.text)
    res = logged.post(
        f"/clases/{friday_class.id}/cancelar",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert "Clase cancelada" in logged.get(f"/clases/{friday_class.id}").text
    res = logged.post(
        f"/clases/{friday_class.id}/reactivar", data={"csrf_token": token}, follow_redirects=False
    )
    assert res.status_code == 303
    res = logged.post(
        f"/clases/{friday_class.id}/mover",
        data={"csrf_token": token, "day": "2026-11-14", "start_time": "10:00"},
        follow_redirects=False,
    )
    assert res.status_code == 303
    actions = {e.action for e in session.exec(select(AuditEvent)).all()}
    assert {AuditAction.CLASS_CANCELLED, AuditAction.CLASS_RESTORED, AuditAction.CLASS_MOVED} <= (
        actions
    )


def test_pantalla_cambiar_horario(logged: TestClient, friday_slot: ScheduleSlot) -> None:
    page = logged.get("/ajustes/horario")
    assert "Cambiar día u hora" in page.text
    res = logged.post(
        f"/ajustes/horario/{friday_slot.id}",
        data={
            "csrf_token": csrf_from(page.text),
            "weekday": "3",
            "start_time": "18:00",
            "duration_min": "60",
        },
        follow_redirects=False,
    )
    assert res.status_code == 303
