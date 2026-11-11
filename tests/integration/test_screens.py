"""Las pantallas responden y los flujos HTMX devuelven lo que la interfaz espera."""

from datetime import time

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from katiu.classes.models import ClassSession, Plan
from katiu.students.models import Student


def test_hoy_muestra_horario_vacio(logged: TestClient) -> None:
    res = logged.get("/")
    assert res.status_code == 200
    assert "Configurar horario" in res.text


def test_pasar_lista_con_htmx(
    logged: TestClient, friday_class: ClassSession, students: list[Student]
) -> None:
    page = logged.get(f"/clases/{friday_class.id}")
    assert page.status_code == 200
    assert "Ana Prueba" in page.text
    assert (
        "ALU-" not in page.text and f"/alumnos/{students[0].id}/" in page.text
    )  # sin IDs visibles

    res = logged.post(f"/clases/{friday_class.id}/alumnos/{students[0].id}/asistencia")
    assert res.status_code == 200
    assert "is-on" in res.text
    assert 'hx-swap-oob="true"' in res.text and "1 persona" in res.text

    res = logged.post(f"/clases/{friday_class.id}/alumnos/{students[0].id}/pago")
    assert "is-paid" in res.text and "Cobrado <b>30 €</b>" in res.text


def test_alta_rapida_por_http(logged: TestClient, friday_class: ClassSession) -> None:
    res = logged.post(f"/clases/{friday_class.id}/alumnos", data={"full_name": "Eva Nueva"})
    assert res.status_code == 200
    assert res.headers["HX-Reswap"] == "afterbegin"
    assert "Eva Nueva" in res.text


def test_alta_rapida_telefono_malo(logged: TestClient, friday_class: ClassSession) -> None:
    res = logged.post(
        f"/clases/{friday_class.id}/alumnos", data={"full_name": "Eva", "phone": "12"}
    )
    assert res.status_code == 422
    assert res.headers["HX-Retarget"] == "#quick-add-error"


def test_alumnos_buscar_y_ficha(logged: TestClient, students: list[Student]) -> None:
    page = logged.get("/alumnos")
    assert all(s.full_name in page.text for s in students)
    partial = logged.get("/alumnos?q=bea", headers={"HX-Request": "true"})
    assert "Bea Ficticia" in partial.text and "Ana Prueba" not in partial.text
    assert "<html" not in partial.text
    ficha = logged.get(f"/alumnos/{students[0].id}")
    assert ficha.status_code == 200 and "Al día" in ficha.text
    assert logged.get("/alumnos/9999").status_code == 404


def test_crear_alumno(logged: TestClient, session: Session) -> None:
    res = logged.post("/alumnos", data={"full_name": "Flor Nueva"}, follow_redirects=False)
    assert res.status_code == 303
    assert session.exec(select(Student).where(Student.full_name == "Flor Nueva")).one()


def test_ajustes_horario(logged: TestClient, session: Session, group_plan: Plan) -> None:
    res = logged.post(
        "/ajustes/horario",
        data={"weekday": "4", "start_time": "10:15", "plan_id": str(group_plan.id)},
        follow_redirects=False,
    )
    assert res.status_code == 303
    page = logged.get("/ajustes/horario?ok=franja")
    assert "Viernes · 10:15" in page.text
    assert session.exec(select(ClassSession).where(ClassSession.start_time == time(10, 15))).first()


def test_clase_extra_lleva_a_pasar_lista(logged: TestClient, group_plan: Plan) -> None:
    res = logged.post(
        "/ajustes/clase-extra",
        data={"day": "2026-12-01", "start_time": "18:00", "plan_id": str(group_plan.id)},
        follow_redirects=False,
    )
    assert res.status_code == 303 and res.headers["location"].startswith("/clases/")


def test_cambiar_contrasena(logged: TestClient) -> None:
    bad = logged.post("/ajustes/contrasena", data={"current": "mala", "new": "nueva-larga"})
    assert bad.status_code == 422
    ok = logged.post(
        "/ajustes/contrasena", data={"current": "olas-de-prueba", "new": "nueva-larga"}
    )
    assert "Contraseña cambiada" in ok.text


def test_paginas_secundarias(logged: TestClient) -> None:
    for url in ("/mas", "/dinero", "/_estilo"):
        assert logged.get(url).status_code == 200
