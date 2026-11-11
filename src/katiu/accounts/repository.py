from sqlmodel import func, select

from katiu.accounts.models import User
from katiu.core.repository import Repository


class UserRepository(Repository[User]):
    model = User

    def by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.strip().lower())
        return self.session.exec(stmt).first()
