"""Reglas de cuentas: crear usuario, autenticar, cambiar contraseña. Sin nada de HTTP."""

from sqlmodel import Session

from katiu.accounts.models import User
from katiu.accounts.repository import UserRepository
from katiu.core.security import hash_password, verify_password

MIN_PASSWORD_LENGTH = 8


class AccountError(ValueError):
    pass


def create_user(session: Session, email: str, display_name: str, password: str) -> User:
    repo = UserRepository(session)
    if repo.by_email(email):
        raise AccountError("Ya existe un usuario con ese email.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AccountError(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")
    user = repo.add(
        User(
            email=email.strip().lower(),
            display_name=display_name.strip(),
            password_hash=hash_password(password),
        )
    )
    session.commit()
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    user = UserRepository(session).by_email(email)
    if user is None or not user.active:
        # Verificamos igualmente un hash ficticio: así tardamos lo mismo exista o no el email
        # (no regalamos qué emails están registrados midiendo el tiempo de respuesta).
        verify_password(_DUMMY_HASH, password)
        return None
    return user if verify_password(user.password_hash, password) else None


def change_password(session: Session, user: User, current: str, new: str) -> None:
    if not verify_password(user.password_hash, current):
        raise AccountError("La contraseña actual no es correcta.")
    if len(new) < MIN_PASSWORD_LENGTH:
        raise AccountError(
            f"La nueva contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
        )
    user.password_hash = hash_password(new)
    session.add(user)
    session.commit()


_DUMMY_HASH = hash_password("contraseña-ficticia-para-igualar-tiempos")


def reset_password(session: Session, email: str, new: str) -> User:
    """Restablece la contraseña sin pedir la actual. Solo desde la terminal del servidor
    (scripts/reset_password.py): quien llega ahí ya es administrador."""
    user = UserRepository(session).by_email(email)
    if user is None:
        raise AccountError("No existe un usuario con ese email.")
    if len(new) < MIN_PASSWORD_LENGTH:
        raise AccountError(
            f"La nueva contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
        )
    user.password_hash = hash_password(new)
    session.add(user)
    session.commit()
    return user
