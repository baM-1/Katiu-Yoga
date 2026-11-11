"""Datos FICTICIOS para probar la app y hacer capturas sin tocar datos reales (RGPD).

Uso:
    KATIU_DATABASE_URL=sqlite:///data/demo.db uv run python scripts/seed_demo.py
    KATIU_DATABASE_URL=sqlite:///data/demo.db uv run fastapi dev
    → entra con demo@katiu.local / demo-olas
"""

import random
from datetime import time, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlmodel import Session, select

from katiu.accounts.repository import UserRepository
from katiu.accounts.service import create_user
from katiu.attendance.service import toggle_attendance, toggle_paid
from katiu.classes import service as classes
from katiu.classes.models import ClassSession, Plan, ScheduleSlot
from katiu.core import clock
from katiu.core.db import engine
from katiu.importing.service import ImportReport, seed_current_plans
from katiu.students.models import Student
from katiu.students.repository import StudentRepository

ROOT = Path(__file__).resolve().parent.parent
NAMES = [
    "Lucía Marín", "Paula Ortega", "Marta Rivas", "Inés Calvo", "Sara Duarte", "Elena Prado",
    "Nora Vidal", "Clara Soler", "Irene Lago", "Julia Mena", "Alba Ruiz", "Carmen Peña",
]  # fmt: skip


def main() -> None:
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    rnd = random.Random(7)
    today = clock.today()
    with Session(engine) as db:
        seed_current_plans(db, ImportReport())
        db.commit()
        if not UserRepository(db).by_email("demo@katiu.local"):
            create_user(db, "demo@katiu.local", "Kat", "demo-olas")
        group = db.exec(select(Plan).where(Plan.name == "Grupal presencial · clase suelta")).one()
        if not db.exec(select(ScheduleSlot)).first():
            for start in (time(9, 0), time(10, 15)):
                classes.add_slot(
                    db, today.weekday(), start, group.id or 0
                )  # "hoy" siempre hay clase
        if not db.exec(select(Student)).first():
            for i, name in enumerate(NAMES):
                StudentRepository(db).add(
                    Student(
                        full_name=name,
                        phone_e164=f"+34600{100000 + i * 1111}",
                        started_on=today - timedelta(days=30 * (i + 1)),
                        default_plan_id=group.id,
                        health_notes="Lesión ficticia de hombro" if i == 2 else None,
                    )
                )
            db.commit()
            # 6 semanas de historia para que existan "habituales"
            classes.generate_sessions(db, today - timedelta(days=42), days=42)
            students = list(db.exec(select(Student)).all())
            past = db.exec(select(ClassSession).where(ClassSession.date < today)).all()
            for cls in past:
                regulars = students[:6] if cls.start_time == time(9, 0) else students[5:10]
                for s in regulars:
                    if rnd.random() < 0.8:
                        toggle_attendance(db, cls.id or 0, s.id or 0)
                        if rnd.random() < 0.85:
                            toggle_paid(db, cls.id or 0, s.id or 0, cls.date)
        classes.generate_sessions(db, today)
    print("✓ Demo lista: demo@katiu.local / demo-olas")


if __name__ == "__main__":
    main()
