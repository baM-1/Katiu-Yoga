"""Editar la ficha de un alumno: servicio y pantalla."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from katiu.classes.models import Plan
from katiu.students import service
from katiu.students.models import Student


def _changes(**kw: object) -> service.StudentChanges:
    base: dict[str, object] = {"full_name": "Ana Prueba"}
    base.update(kw)
    return service.StudentChanges(**base)  # type: ignore[arg-type]


def test_editar_guarda_todo(session: Session, students: list[Student], group_plan: Plan) -> None:
    ana = students[0]
    service.update_student(
        session,
        ana.id or 0,
        _changes(
            full_name="  Ana   Prueba Nueva ",
            phone="600 111 222",
            email="ANA@Ejemplo.com",
            birthday=date(1990, 5, 1),
            started_on=date(2025, 1, 10),
            location="Valdebebas",
            default_plan_id=group_plan.id,
            health_notes="  Rodilla izquierda\nsin saltos  ",
            notes="",
            active=True,
            whatsapp_consent=True,
        ),
    )
    session.refresh(ana)
    assert ana.full_name == "Ana Prueba Nueva"
    assert ana.phone_e164 == "+34600111222"
    assert ana.email == "ana@ejemplo.com"
    assert ana.health_notes == "Rodilla izquierda\nsin saltos"  # respeta saltos de línea
    assert ana.notes is None
    assert ana.default_plan_id == group_plan.id
    assert ana.whatsapp_consent and ana.whatsapp_consent_at is not None


def test_retirar_consentimiento_borra_fecha(session: Session, students: list[Student]) -> None:
    ana = students[0]
    service.update_student(session, ana.id or 0, _changes(whatsapp_consent=True))
    service.update_student(session, ana.id or 0, _changes(whatsapp_consent=False))
    session.refresh(ana)
    assert not ana.whatsapp_consent and ana.whatsapp_consent_at is None


@pytest.mark.parametrize(
    ("kw", "msg"),
    [
        ({"full_name": "  "}, "nombre"),
        ({"phone": "123"}, "teléfono"),
        ({"email": "no-es-email"}, "email"),
        ({"birthday": date(2999, 1, 1)}, "futuro"),
        ({"default_plan_id": 9999}, "tarifa"),
    ],
)
def test_editar_valida_sin_tocar_nada(
    session: Session, students: list[Student], kw: dict[str, object], msg: str
) -> None:
    ana = students[0]
    with pytest.raises(service.StudentError, match=msg):
        service.update_student(session, ana.id or 0, _changes(**kw))
    session.refresh(ana)
    assert ana.full_name == "Ana Prueba"  # nada a medias


def test_desactivar_lo_saca_de_la_lista(session: Session, students: list[Student]) -> None:
    ana = students[0]
    service.update_student(session, ana.id or 0, _changes(active=False))
    assert ana not in service.search(session)
    assert ana in service.search(session, include_inactive=True)


def test_pantalla_editar(logged: TestClient, students: list[Student]) -> None:
    sid = students[0].id
    page = logged.get(f"/alumnos/{sid}/editar")
    assert page.status_code == 200
    assert 'name="health_notes"' in page.text

    res = logged.post(
        f"/alumnos/{sid}",
        data={"full_name": "Ana Editada", "health_notes": "Embarazo 20 semanas", "active": "1"},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert res.headers["location"] == f"/alumnos/{sid}?guardado=1"
    ficha = logged.get(res.headers["location"]).text
    assert "Ana Editada" in ficha and "Embarazo 20 semanas" in ficha and "Ficha guardada" in ficha


def test_pantalla_editar_error_conserva_lo_escrito(
    logged: TestClient, students: list[Student]
) -> None:
    sid = students[0].id
    res = logged.post(
        f"/alumnos/{sid}",
        data={"full_name": "Ana Editada", "phone": "12", "notes": "lo que escribí"},
    )
    assert res.status_code == 422
    assert "teléfono no parece válido" in res.text
    assert "lo que escribí" in res.text and "Ana Editada" in res.text


def test_editar_sin_csrf_rechazado(client: TestClient, user: None, students: list[Student]) -> None:
    res = client.post(f"/alumnos/{students[0].id}", data={"full_name": "X"})
    assert res.status_code in (401, 403)


def test_editar_alumno_inexistente(logged: TestClient) -> None:
    assert logged.get("/alumnos/9999/editar").status_code == 404
