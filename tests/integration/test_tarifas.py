"""Tarifa por alumno: la etiqueta de precio va con la persona, no con la esterilla."""

from datetime import date, time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, select

from katiu.attendance import service
from katiu.audit.models import AuditAction, AuditEvent
from katiu.classes import tariffs
from katiu.classes.catalog import NORMAL_GROUP_PLAN, REGGIO_GROUP_PLAN
from katiu.classes.models import ClassSession, Modality, Plan, PlanFormat, PlanKind
from katiu.classes.service import create_extra_class
from katiu.core.db import make_engine
from katiu.students.models import Student
from katiu.students.service import create_student
from tests.conftest import FRIDAY, csrf_from

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def reggio(plans: dict[str, Plan]) -> Plan:
    return plans[REGGIO_GROUP_PLAN]


def _price(session: Session, cls: ClassSession, student: Student) -> int:
    service.toggle_attendance(session, cls.id or 0, student.id or 0)
    item = service.roster_item(session, cls.id or 0, student.id or 0)
    assert item.attendance is not None
    return item.attendance.price_cents


# --- Regla pura -------------------------------------------------------------------------------


def _plan(kind: PlanKind, fmt: PlanFormat, price: int) -> Plan:
    return Plan(name="x", kind=kind, format=fmt, price_cents=price)


@pytest.mark.parametrize(
    ("student_plan", "expected"),
    [
        (None, 3000),  # sin tarifa: precio de la clase
        (_plan(PlanKind.DROP_IN, PlanFormat.GROUP, 2100), 2100),  # Reggio
        (_plan(PlanKind.PACK, PlanFormat.GROUP, 10800), 3000),  # bono: no es precio por clase
        (_plan(PlanKind.DROP_IN, PlanFormat.INDIVIDUAL, 3500), 3000),  # individual en grupo
    ],
)
def test_price_for(student_plan: Plan | None, expected: int) -> None:
    group = _plan(PlanKind.DROP_IN, PlanFormat.GROUP, 3000)
    cls = ClassSession(date=FRIDAY, start_time=time(9), plan_id=1, price_cents=3000)
    assert service.price_for(student_plan, cls, group) == expected


def test_clase_individual_ignora_tarifa_de_grupo() -> None:
    individual = _plan(PlanKind.DROP_IN, PlanFormat.INDIVIDUAL, 3500)
    cls = ClassSession(date=FRIDAY, start_time=time(9), plan_id=1, price_cents=3500)
    reggio = _plan(PlanKind.DROP_IN, PlanFormat.GROUP, 2100)
    assert service.price_for(reggio, cls, individual) == 3500


# --- Pasar lista ------------------------------------------------------------------------------


def test_reggio_y_normal_en_la_misma_clase(
    session: Session, friday_class: ClassSession, students: list[Student], reggio: Plan
) -> None:
    paloma, ana = students[0], students[1]
    paloma.default_plan_id = reggio.id
    session.add(paloma)
    session.commit()
    assert _price(session, friday_class, paloma) == 2100
    assert _price(session, friday_class, ana) == 3000
    t = service.totals(session, friday_class.id or 0)
    assert (t.people, t.pending_cents) == (2, 5100)
    assert service.roster_item(session, friday_class.id or 0, paloma.id or 0).tariff_label == (
        "Grupo Reggio"
    )
    assert service.roster_item(session, friday_class.id or 0, ana.id or 0).tariff_label is None


def test_cambiar_tarifa_solo_hacia_adelante(
    session: Session,
    friday_class: ClassSession,
    students: list[Student],
    reggio: Plan,
    group_plan: Plan,
) -> None:
    paloma = students[0]
    paloma.default_plan_id = reggio.id
    session.add(paloma)
    session.commit()
    assert _price(session, friday_class, paloma) == 2100
    # Kat sube Reggio a 22 €: lo ya marcado sigue a 21 €.
    tariffs.update_tariff(session, reggio.id or 0, reggio.name, "22")
    item = service.roster_item(session, friday_class.id or 0, paloma.id or 0)
    assert item.attendance is not None and item.attendance.price_cents == 2100
    # La siguiente clase ya se marca a 22 €.
    next_week = create_extra_class(session, date(2026, 11, 20), time(9), group_plan.id or 0)
    assert _price(session, next_week, paloma) == 2200


def test_descuento_puntual(
    session: Session, friday_class: ClassSession, students: list[Student]
) -> None:
    cid, sid = friday_class.id or 0, students[0].id or 0
    service.toggle_attendance(session, cid, sid)
    assert service.override_price(session, cid, sid, "15") == (3000, 1500)
    assert service.totals(session, cid).pending_cents == 1500
    with pytest.raises(service.AttendanceError, match="entre 0 y 999"):
        service.override_price(session, cid, sid, "1000")
    with pytest.raises(service.AttendanceError, match="no se entiende"):
        service.override_price(session, cid, sid, "quince")
    service.toggle_paid(session, cid, sid, FRIDAY)
    with pytest.raises(service.AttendanceError, match="Deshaz el pago"):
        service.override_price(session, cid, sid, "10")


def test_descuento_sin_marcar(
    session: Session, friday_class: ClassSession, students: list[Student]
) -> None:
    with pytest.raises(service.AttendanceError, match="Marca primero"):
        service.override_price(session, friday_class.id or 0, students[0].id or 0, "10")


def test_alumno_nuevo_es_normal(session: Session, plans: dict[str, Plan]) -> None:
    s = create_student(session, "Nueva Alumna")
    assert s.default_plan_id == plans[NORMAL_GROUP_PLAN].id


# --- Tarifas ----------------------------------------------------------------------------------


def test_crear_editar_archivar(session: Session, plans: dict[str, Plan]) -> None:
    amigas = tariffs.create_tariff(session, "  Grupo   Amigas ", "25")
    assert (amigas.name, amigas.price_cents, amigas.kind) == ("Grupo Amigas", 2500, "drop_in")
    assert amigas in tariffs.group_choices(session)
    with pytest.raises(tariffs.TariffError, match="Ya hay"):
        tariffs.create_tariff(session, "grupo amigas", "20")
    with pytest.raises(tariffs.TariffError, match="nombre"):
        tariffs.create_tariff(session, " ", "20")
    plan, before = tariffs.update_tariff(session, amigas.id or 0, "Grupo Amigas", "24,50")
    assert (before, plan.price_cents) == (2500, 2450)
    tariffs.archive_tariff(session, amigas.id or 0)
    assert amigas not in tariffs.group_choices(session)


def test_no_archiva_si_hay_alumnos_o_es_la_normal(
    session: Session, students: list[Student], reggio: Plan, plans: dict[str, Plan]
) -> None:
    students[0].default_plan_id = reggio.id
    session.add(students[0])
    session.commit()
    with pytest.raises(tariffs.TariffError, match="1 alumno"):
        tariffs.archive_tariff(session, reggio.id or 0)
    normal = plans[NORMAL_GROUP_PLAN]
    with pytest.raises(tariffs.TariffError, match="normal"):
        tariffs.archive_tariff(session, normal.id or 0)
    with pytest.raises(tariffs.TariffError, match="renombrar"):
        tariffs.update_tariff(session, normal.id or 0, "Normal", "30")


def test_pantalla_tarifas(logged: TestClient, session: Session, plans: dict[str, Plan]) -> None:
    page = logged.get("/ajustes/tarifas")
    assert page.status_code == 200 and "Grupo Reggio" in page.text
    token = csrf_from(page.text)
    res = logged.post(
        "/ajustes/tarifas",
        data={"name": "Grupo Amigas", "price": "25", "format": "group", "modality": "in_person"},
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )
    assert res.status_code == 303
    amigas = session.exec(select(Plan).where(Plan.name == "Grupo Amigas")).one()
    assert (amigas.price_cents, amigas.modality) == (2500, Modality.IN_PERSON)
    bad = logged.post(
        f"/ajustes/tarifas/{amigas.id}",
        data={"name": "Grupo Amigas", "price": "mucho"},
        headers={"X-CSRF-Token": token},
    )
    assert bad.status_code == 422 and "no se entiende" in bad.text
    actions = {e.action for e in session.exec(select(AuditEvent)).all()}
    assert AuditAction.PLAN_CREATED in actions


def test_pantalla_tarifas_pide_csrf(logged: TestClient, plans: dict[str, Plan]) -> None:
    res = logged.post(
        "/ajustes/tarifas",
        data={"name": "X", "price": "1"},
        headers={"X-CSRF-Token": "falso"},
    )
    assert res.status_code == 403


def test_pantalla_precio_puntual(
    logged: TestClient, session: Session, friday_class: ClassSession, students: list[Student]
) -> None:
    cid, sid = friday_class.id, students[0].id
    logged.post(f"/clases/{cid}/alumnos/{sid}/asistencia")
    page = logged.get(f"/clases/{cid}")
    assert "cambiar precio" in page.text
    res = logged.post(f"/clases/{cid}/alumnos/{sid}/precio", data={"amount": "18,50"})
    assert res.status_code == 200 and "18,50 €" in res.text
    bad = logged.post(f"/clases/{cid}/alumnos/{sid}/precio", data={"amount": "-3"})
    assert bad.status_code == 422 and "entre 0 y 999" in bad.text


# --- Migración de datos -----------------------------------------------------------------------


def test_migracion_pasa_reggio_y_normal(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'm.db'}")
    cfg = Config(str(ROOT / "alembic.ini"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "4b0f5b84f080")
        for i, name in enumerate([NORMAL_GROUP_PLAN, REGGIO_GROUP_PLAN, "Grupo Reggio"], 1):
            conn.execute(
                text(
                    "INSERT INTO plans (id, name, kind, format, modality, price_cents, active) "
                    "VALUES (:i, :n, 'DROP_IN', 'GROUP', 'IN_PERSON', 3000, 1)"
                ),
                {"i": i, "n": name},
            )
        rows = [("ALU-0006", 3), ("ALU-0034", 3), ("ALU-0009", None), ("ALU-0033", 3)]
        for legacy, plan in rows:
            conn.execute(
                text(
                    "INSERT INTO students (full_name, legacy_id, default_plan_id, active, "
                    "whatsapp_consent) VALUES ('x', :l, :p, 1, 0)"
                ),
                {"l": legacy, "p": plan},
            )
        command.upgrade(cfg, "head")
        got = dict(conn.execute(text("SELECT legacy_id, default_plan_id FROM students")).all())
    assert got == {"ALU-0006": 2, "ALU-0034": 2, "ALU-0009": 1, "ALU-0033": 3}
