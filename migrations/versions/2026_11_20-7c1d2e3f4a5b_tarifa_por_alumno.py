"""tarifa por alumno: auditoría de tarifas y alumnos Reggio

Revision ID: 7c1d2e3f4a5b
Revises: 4b0f5b84f080
Create Date: 2026-11-20 13:00:00

Dos cosas:
1. Esquema: nuevas acciones de auditoría (precio puntual, crear/cambiar/archivar tarifa) y el
   objetivo "plan".
2. Datos (decisión de Lalo, 2026-11-20): los alumnos del Grupo Reggio pasan a la tarifa vigente
   "Grupo Reggio · clase suelta" y los que no tienen tarifa, a la normal. Se buscan por su
   código del Excel (legacy_id), no por nombre, porque el nombre se puede editar. Si un alumno o
   la tarifa no existen (BD nueva o de pruebas), se salta sin fallar. Solo cambia la tarifa de
   la ficha: no recalcula clases ni pagos ya guardados.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7c1d2e3f4a5b"
down_revision: Union[str, Sequence[str], None] = "4b0f5b84f080"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_ACTIONS = (
    "LOGIN", "LOGIN_FAILED", "LOGOUT", "PASSWORD_CHANGED", "STUDENT_CREATED", "STUDENT_UPDATED",
    "ATTENDANCE_TOGGLED", "PAYMENT_TOGGLED", "QUICK_ADD", "SLOT_ADDED", "SLOT_PAUSED",
    "EXTRA_CLASS", "USER_CREATED", "USER_PASSWORD_RESET", "USER_ACTIVATED", "USER_DEACTIVATED",
    "EXPORT_DOWNLOADED",
)  # fmt: skip
NEW_ACTIONS = OLD_ACTIONS + ("PRICE_OVERRIDDEN", "PLAN_CREATED", "PLAN_UPDATED", "PLAN_ARCHIVED")
OLD_TARGETS = ("STUDENT", "CLASS", "SLOT", "USER")
NEW_TARGETS = OLD_TARGETS + ("PLAN",)

NORMAL = "Grupal presencial · clase suelta"
REGGIO = "Grupo Reggio · clase suelta"
REGGIO_STUDENTS = (
    "ALU-0001",  # Raquel Cano
    "ALU-0004",  # Matias Lespiau
    "ALU-0005",  # Agostina DAlo
    "ALU-0006",  # Paloma
    "ALU-0007",  # Marta Eric
    "ALU-0008",  # Oscar
    "ALU-0034",  # Marta Clara
)


def _enums(actions: tuple[str, ...], targets: tuple[str, ...]) -> None:
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column("action", type_=sa.Enum(*actions, name="auditaction"))
        batch.alter_column("target_type", type_=sa.Enum(*targets, name="audittarget"))


def _plan_id(conn: sa.Connection, name: str) -> int | None:
    return conn.execute(sa.text("SELECT id FROM plans WHERE name = :n"), {"n": name}).scalar()


def upgrade() -> None:
    _enums(NEW_ACTIONS, NEW_TARGETS)
    conn = op.get_bind()
    reggio = _plan_id(conn, REGGIO)
    if reggio is not None:
        conn.execute(
            sa.text("UPDATE students SET default_plan_id = :p WHERE legacy_id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"p": reggio, "ids": list(REGGIO_STUDENTS)},
        )
    normal = _plan_id(conn, NORMAL)
    if normal is not None:
        conn.execute(
            sa.text("UPDATE students SET default_plan_id = :p WHERE default_plan_id IS NULL"),
            {"p": normal},
        )


def downgrade() -> None:
    # Los datos no se revierten: la tarifa antigua de cada alumno no se guardó y volver a
    # "sin tarifa" sería peor. Solo deshacemos el esquema (borrando antes los eventos nuevos).
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM audit_events WHERE action IN :a OR target_type = 'PLAN'").bindparams(
            sa.bindparam("a", expanding=True)
        ),
        {"a": [a for a in NEW_ACTIONS if a not in OLD_ACTIONS]},
    )
    _enums(OLD_ACTIONS, OLD_TARGETS)
