"""Repositorio base: la ÚNICA capa que habla con la base de datos.

Patrón Repository: los services piden "dame el alumno X" o "guarda esta asistencia" sin saber
si detrás hay SQLite, PostgreSQL o una lista en memoria. Así la lógica se prueba fácil y el
almacenamiento se puede cambiar sin tocar las reglas de negocio.
"""

from collections.abc import Sequence
from typing import Any, ClassVar

from sqlmodel import Session, SQLModel, col, select


class Repository[ModelT: SQLModel]:
    model: ClassVar[type[Any]]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, id_: int) -> ModelT | None:
        return self.session.get(self.model, id_)

    def get_by_legacy_id(self, legacy_id: str) -> ModelT | None:
        stmt = select(self.model).where(col(self.model.legacy_id) == legacy_id)
        return self.session.exec(stmt).first()

    def list(self) -> Sequence[ModelT]:
        return self.session.exec(select(self.model)).all()

    def add(self, obj: ModelT) -> ModelT:
        """Añade y hace flush (obtiene el id) sin confirmar: el commit lo decide quien orquesta."""
        self.session.add(obj)
        self.session.flush()
        return obj
