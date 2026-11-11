"""Piezas HTTP compartidas por todos los routers: usuario actual y respuestas HTMX."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from katiu.accounts.models import User
from katiu.core.db import get_session

SESSION_USER_KEY = "uid"

DbSession = Annotated[Session, Depends(get_session)]


class LoginRequiredError(Exception):
    """Se lanza cuando no hay sesión; main.py la convierte en redirección a /entrar."""


def current_user(request: Request, db: DbSession) -> User:
    uid = request.session.get(SESSION_USER_KEY)
    user = db.get(User, uid) if isinstance(uid, int) else None
    if user is None or not user.active:
        raise LoginRequiredError
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def admin_user(user: CurrentUser) -> User:
    """Solo administradores. A los demás les respondemos 404 (ni siquiera saben que existe)."""
    if not user.is_admin:
        raise HTTPException(404)
    return user


AdminUser = Annotated[User, Depends(admin_user)]
