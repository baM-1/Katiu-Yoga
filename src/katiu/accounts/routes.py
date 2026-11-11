"""Entrar y salir."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from katiu.accounts.service import authenticate
from katiu.core.config import get_settings
from katiu.core.security import LoginRateLimiter, verify_csrf
from katiu.core.templating import templates
from katiu.core.web import SESSION_USER_KEY, DbSession

router = APIRouter()

_settings = get_settings()
limiter = LoginRateLimiter(_settings.login_max_attempts, _settings.login_window_minutes * 60)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "desconocido"


@router.get("/entrar", response_class=HTMLResponse)
def login_form(request: Request) -> Response:
    if request.session.get(SESSION_USER_KEY):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/entrar", dependencies=[Depends(verify_csrf)], response_class=HTMLResponse)
def login(
    request: Request,
    db: DbSession,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> Response:
    key = _client_key(request)
    if limiter.is_blocked(key):
        error = "Demasiados intentos. Espera unos minutos y vuelve a probar."
        return templates.TemplateResponse(
            request, "login.html", {"error": error, "email": email}, status_code=429
        )
    user = authenticate(db, email, password)
    if user is None:
        limiter.register_failure(key)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Email o contraseña incorrectos.", "email": email},
            status_code=401,
        )
    limiter.reset(key)
    # Sesión nueva al entrar (evita "session fixation"): conservamos solo el token CSRF nuevo.
    request.session.clear()
    request.session[SESSION_USER_KEY] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/salir", dependencies=[Depends(verify_csrf)])
def logout(request: Request) -> Response:
    request.session.clear()
    return RedirectResponse("/entrar", status_code=303)
