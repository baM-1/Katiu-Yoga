from collections.abc import Sequence

from sqlmodel import col, select

from katiu.core.repository import Repository
from katiu.students.models import Student


class StudentRepository(Repository[Student]):
    model = Student

    def active(self) -> Sequence[Student]:
        stmt = select(Student).where(col(Student.active)).order_by(col(Student.full_name))
        return self.session.exec(stmt).all()
