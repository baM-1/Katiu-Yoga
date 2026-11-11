from sqlmodel import col, func, select

from katiu.accounts.models import User
from katiu.core.repository import Repository


class UserRepository(Repository[User]):
    model = User

    def by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.strip().lower())
        return self.session.exec(stmt).first()

    def active_admins(self) -> list[User]:
        stmt = select(User).where(col(User.is_admin), col(User.active))
        return list(self.session.exec(stmt).all())

    def ordered(self) -> list[User]:
        stmt = select(User).order_by(col(User.active).desc(), col(User.display_name))
        return list(self.session.exec(stmt).all())
