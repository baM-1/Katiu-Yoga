"""Las migraciones crean exactamente el esquema de los modelos (y se pueden deshacer)."""

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlmodel import SQLModel

import katiu.core.all_models  # noqa: F401
from katiu.core.db import make_engine

ROOT = Path(__file__).resolve().parents[2]


def test_upgrade_coincide_con_modelos_y_downgrade(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'm.db'}")
    cfg = Config(str(ROOT / "alembic.ini"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
        assert diff == [], f"Falta una migración: {diff}"
        command.downgrade(cfg, "base")
