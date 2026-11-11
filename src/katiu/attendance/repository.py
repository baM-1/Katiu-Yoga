from collections.abc import Sequence

from sqlmodel import select

from katiu.attendance.models import Attendance
from katiu.core.repository import Repository


class AttendanceRepository(Repository[Attendance]):
    model = Attendance

    def for_session(self, class_session_id: int) -> Sequence[Attendance]:
        stmt = select(Attendance).where(Attendance.class_session_id == class_session_id)
        return self.session.exec(stmt).all()

    def for_student(self, student_id: int) -> Sequence[Attendance]:
        stmt = select(Attendance).where(Attendance.student_id == student_id)
        return self.session.exec(stmt).all()
