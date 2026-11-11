from datetime import datetime

from sqlmodel import Field, SQLModel

from katiu.core.models import utcnow


class User(SQLModel, table=True):
    __tablename__ = "users"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=254)
    display_name: str = Field(max_length=60)
    password_hash: str
    active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
