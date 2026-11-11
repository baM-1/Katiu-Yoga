"""Fixtures compartidas por todos los tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import katiu.core.all_models  # noqa: F401  (registra las tablas)
from katiu.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Un cliente HTTP contra una app recién creada (sin servidor real)."""
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def session() -> Iterator[Session]:
    """BD SQLite en memoria, nueva para cada test: aislada y rapidísima."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
