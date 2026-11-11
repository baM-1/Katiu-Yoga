"""Fixtures compartidas por todos los tests."""

import re
from collections.abc import Iterator
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import katiu.core.all_models  # noqa: F401  (registra las tablas)
from katiu.accounts.routes import limiter
from katiu.accounts.service import create_user
from katiu.classes import service as classes
from katiu.classes.models import ClassSession, Plan
from katiu.core.db import get_session
from katiu.importing.service import ImportReport, seed_current_plans
from katiu.main import create_app
from katiu.students.models import Student

PASSWORD = "olas-de-prueba"
FRIDAY = date(2026, 11, 13)


@pytest.fixture
def engine() -> Engine:
    """BD SQLite en memoria, nueva para cada test: aislada y rapidísima."""
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    """Cliente HTTP contra una app nueva que usa la BD en memoria del test."""
    app = create_app()

    def _session() -> Iterator[Session]:
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    limiter._failures.clear()  # pyright: ignore[reportPrivateUsage]
    with TestClient(app) as c:
        yield c


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html) or re.search(
        r'"X-CSRF-Token": "([^"]+)"', html
    )
    assert match, "la página no tiene token CSRF"
    return match.group(1)


@pytest.fixture
def user(session: Session) -> None:
    create_user(session, "kat@ejemplo.com", "Kat", PASSWORD)


@pytest.fixture
def logged(client: TestClient, user: None) -> TestClient:
    """Cliente con la sesión iniciada. Lleva la cabecera CSRF como haría HTMX."""
    token = csrf_from(client.get("/entrar").text)
    res = client.post(
        "/entrar",
        data={"email": "kat@ejemplo.com", "password": PASSWORD, "csrf_token": token},
        follow_redirects=False,
    )
    assert res.status_code == 303
    client.headers["X-CSRF-Token"] = csrf_from(client.get("/mas").text)
    return client


@pytest.fixture
def plans(session: Session) -> dict[str, Plan]:
    seed_current_plans(session, ImportReport())
    session.commit()
    return {p.name: p for p in session.exec(select(Plan)).all()}


@pytest.fixture
def group_plan(plans: dict[str, Plan]) -> Plan:
    return plans["Grupal presencial · clase suelta"]


@pytest.fixture
def friday_class(session: Session, group_plan: Plan) -> ClassSession:
    return classes.create_extra_class(session, FRIDAY, time(9, 0), group_plan.id or 0)


@pytest.fixture
def students(session: Session) -> list[Student]:
    names = ["Ana Prueba", "Bea Ficticia", "Carla Inventada", "Dani Demo"]
    out = [Student(full_name=n) for n in names]
    session.add_all(out)
    session.commit()
    return out
