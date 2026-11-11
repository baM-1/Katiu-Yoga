"""Fixtures compartidas por todos los tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from katiu.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Un cliente HTTP contra una app recién creada (sin servidor real)."""
    with TestClient(create_app()) as c:
        yield c
