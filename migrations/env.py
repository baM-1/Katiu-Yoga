"""Entorno de Alembic: conecta las migraciones con nuestros modelos y nuestra configuración."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection
from sqlmodel import SQLModel

import katiu.core.all_models  # noqa: F401  (registra todas las tablas en SQLModel.metadata)
from katiu.core.db import make_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse (útil para revisarlo a mano)."""
    from katiu.core.config import get_settings

    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite no sabe hacer ALTER COLUMN: "batch" recrea la tabla por debajo.
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Los tests pueden pasar una conexión ya abierta (con una BD temporal).
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    with make_engine().connect() as conn:
        _run(conn)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
