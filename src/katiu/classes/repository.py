from collections.abc import Sequence
from datetime import date

from sqlmodel import col, select

from katiu.classes.models import ClassSession, Plan, ScheduleSlot
from katiu.core.repository import Repository


class PlanRepository(Repository[Plan]):
    model = Plan

    def active(self) -> Sequence[Plan]:
        return self.session.exec(select(Plan).where(col(Plan.active)).order_by(col(Plan.id))).all()


class ScheduleSlotRepository(Repository[ScheduleSlot]):
    model = ScheduleSlot


class ClassSessionRepository(Repository[ClassSession]):
    model = ClassSession

    def on_date(self, day: date) -> Sequence[ClassSession]:
        stmt = (
            select(ClassSession)
            .where(ClassSession.date == day)
            .order_by(col(ClassSession.start_time))
        )
        return self.session.exec(stmt).all()
