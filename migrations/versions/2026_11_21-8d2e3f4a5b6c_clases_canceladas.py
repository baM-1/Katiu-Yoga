"""clases canceladas y auditoría de cambios de horario

Revision ID: 8d2e3f4a5b6c
Revises: 7c1d2e3f4a5b
Create Date: 2026-11-21 00:30:00

Una clase cancelada no se borra: se marca (`cancelled`), porque el horario fijo la volvería a
crear sola. Ver ADR-0009.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8d2e3f4a5b6c"
down_revision: Union[str, Sequence[str], None] = "7c1d2e3f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_ACTIONS = (
    "LOGIN", "LOGIN_FAILED", "LOGOUT", "PASSWORD_CHANGED", "STUDENT_CREATED", "STUDENT_UPDATED",
    "ATTENDANCE_TOGGLED", "PAYMENT_TOGGLED", "QUICK_ADD", "SLOT_ADDED", "SLOT_PAUSED",
    "EXTRA_CLASS", "USER_CREATED", "USER_PASSWORD_RESET", "USER_ACTIVATED", "USER_DEACTIVATED",
    "EXPORT_DOWNLOADED", "PRICE_OVERRIDDEN", "PLAN_CREATED", "PLAN_UPDATED", "PLAN_ARCHIVED",
)  # fmt: skip
NEW_ONLY = ("CLASS_CANCELLED", "CLASS_RESTORED", "CLASS_MOVED", "SLOT_CHANGED")


def upgrade() -> None:
    with op.batch_alter_table("class_sessions") as batch:
        batch.add_column(sa.Column("cancelled", sa.Boolean(), server_default="0", nullable=False))
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column("action", type_=sa.Enum(*OLD_ACTIONS, *NEW_ONLY, name="auditaction"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM audit_events WHERE action IN :a").bindparams(
            sa.bindparam("a", expanding=True)
        ),
        {"a": list(NEW_ONLY)},
    )
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column("action", type_=sa.Enum(*OLD_ACTIONS, name="auditaction"))
    with op.batch_alter_table("class_sessions") as batch:
        batch.drop_column("cancelled")
