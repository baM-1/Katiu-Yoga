"""Importa todos los modelos para que `SQLModel.metadata` los conozca.

Alembic y los tests importan este módulo: si un modelo no aparece aquí, no existe para ellos.
"""

from katiu.accounts.models import User
from katiu.attendance.models import Attendance
from katiu.classes.models import ClassSession, Plan, ScheduleSlot
from katiu.payments.models import PackPurchase, Payment
from katiu.reminders.models import ReminderLog
from katiu.students.models import Student

__all__ = [
    "Attendance",
    "ClassSession",
    "PackPurchase",
    "Payment",
    "Plan",
    "ReminderLog",
    "ScheduleSlot",
    "Student",
    "User",
]
