"""Conexión a la base de datos.

- `engine`: el "grifo" hacia SQLite (o PostgreSQL mañana, solo cambiando la URL).
- `get_session`: dependencia de FastAPI que abre una sesión por petición y la cierra al acabar.
"""

from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, event
from sqlmodel import Session, create_engine

from katiu.core.config import get_settings


def make_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    url = url or get_settings().database_url
    is_sqlite = url.startswith("sqlite")
    engine = create_engine(
        url,
        echo=echo,
        # SQLite por defecto prohíbe usar una conexión desde otro hilo; FastAPI usa varios.
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )
    if is_sqlite:
        event.listen(engine, "connect", _sqlite_pragmas)
    return engine


def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
    """WAL: lectores y escritor no se bloquean. foreign_keys: SQLite no las aplica si no se pide."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


engine = make_engine()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
