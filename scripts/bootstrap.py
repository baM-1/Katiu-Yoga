"""Deja la app lista para Kat: migraciones, tarifas 2026, horario fijo y su usuario.

Uso (una vez, en local o en el servidor):
    uv run python scripts/bootstrap.py --email kat@ejemplo.com --nombre Kat

Es idempotente: si algo ya existe, no lo toca. La contraseña se pide por teclado (nunca en
la línea de comandos, que queda guardada en el historial).
"""

import argparse
import getpass
from datetime import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlmodel import Session, select

from katiu.accounts.repository import UserRepository
from katiu.accounts.service import create_user
from katiu.classes import service as classes
from katiu.classes.models import Plan, ScheduleSlot
from katiu.core import clock
from katiu.core.db import engine
from katiu.importing.service import ImportReport, seed_current_plans

ROOT = Path(__file__).resolve().parent.parent

# Horario fijo de Kat (Lalo, 2026-11-11): viernes 9:00 y 10:15, grupo.
DEFAULT_SLOTS = [(4, time(9, 0)), (4, time(10, 15))]
DEFAULT_PLAN = "Grupal presencial · clase suelta"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--nombre", default="Kat")
    args = parser.parse_args()

    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    with Session(engine) as db:
        seed_current_plans(db, ImportReport())
        db.commit()

        if not db.exec(select(ScheduleSlot)).first():
            plan = db.exec(select(Plan).where(Plan.name == DEFAULT_PLAN)).one()
            for weekday, start in DEFAULT_SLOTS:
                classes.add_slot(db, weekday, start, plan.id or 0)
            print(f"✓ Horario creado: viernes 9:00 y 10:15 ({DEFAULT_PLAN})")
        classes.generate_sessions(db, clock.today())

        if UserRepository(db).by_email(args.email):
            print(f"✓ El usuario {args.email} ya existe")
        else:
            password = getpass.getpass("Contraseña para la app (mín. 8): ")
            create_user(db, args.email, args.nombre, password)
            print(f"✓ Usuario {args.email} creado")


if __name__ == "__main__":
    main()
