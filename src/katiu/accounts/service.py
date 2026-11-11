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


def admin_create_user(
    session: Session, email: str, display_name: str, password: str, *, is_admin: bool = False
) -> User:
    """Alta desde el Panel de Admin: valida nombre y email además de la contraseña."""
    clean_email = email.strip().lower()
    if "@" not in clean_email or "." not in clean_email.split("@")[-1]:
        raise AccountError("Ese email no parece válido.")
    if not display_name.strip():
        raise AccountError("Falta el nombre.")
    user = create_user(session, clean_email, display_name, password)
    if is_admin:
        user.is_admin = True
        session.add(user)
        session.commit()
    return user


def set_password(session: Session, user_id: int, new: str) -> User:
    """Un admin pone una contraseña nueva a otro usuario (sin pedir la actual)."""
    user = session.get(User, user_id)
    if user is None:
        raise AccountError("Ese usuario no existe.")
    return reset_password(session, user.email, new)


def set_active(session: Session, actor: User, user_id: int, active: bool) -> User:
    """Activa o desactiva una cuenta. Nadie puede desactivarse a sí mismo ni dejar la app
    sin ningún administrador activo (te quedarías fuera de tu propio panel)."""
    user = session.get(User, user_id)
    if user is None:
        raise AccountError("Ese usuario no existe.")
    if not active:
        if user.id == actor.id:
            raise AccountError("No puedes desactivar tu propia cuenta.")
        if user.is_admin:
            admins = UserRepository(session).active_admins()
            if len([a for a in admins if a.id != user.id]) == 0:
                raise AccountError("Tiene que quedar al menos un administrador activo.")
    user.active = active
    session.add(user)
    session.commit()
    return user


def make_admin(session: Session, email: str) -> User:
    user = UserRepository(session).by_email(email)
    if user is None:
        raise AccountError("No existe un usuario con ese email.")
    user.is_admin = True
    session.add(user)
    session.commit()
    return user


def all_users(session: Session) -> list[User]:
    return UserRepository(session).ordered()
