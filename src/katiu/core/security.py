"""Seguridad: contraseñas (argon2), CSRF, límite de intentos de login y cabeceras HTTP.

Todo en un sitio y sin dependencias mágicas, para poder leerlo de arriba abajo.
"""

import secrets
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, Request
from starlette.responses import Response

# ---------- Contraseñas ----------
# argon2id: el algoritmo recomendado hoy (OWASP). Lento a propósito para frenar la fuerza bruta.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


# ---------- CSRF ----------
# Un token aleatorio vive en la sesión (cookie firmada) y cada POST debe devolverlo, en la
# cabecera X-CSRF-Token (HTMX lo añade solo) o en el campo oculto `csrf_token` de un formulario.
# Una web maliciosa puede hacer que el navegador envíe la cookie, pero no puede leer el token.
CSRF_SESSION_KEY = "csrf"
CSRF_HEADER = "X-CSRF-Token"
CSRF_FIELD = "csrf_token"


def csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


async def verify_csrf(request: Request) -> None:
    """Dependencia de FastAPI: se añade a los routers que aceptan POST."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    expected = request.session.get(CSRF_SESSION_KEY)
    sent = request.headers.get(CSRF_HEADER)
    if sent is None:
        form = await request.form()
        value = form.get(CSRF_FIELD)
        sent = value if isinstance(value, str) else None
    if not expected or not sent or not secrets.compare_digest(expected, sent):
        raise HTTPException(status_code=403, detail="Formulario caducado. Recarga la página.")


# ---------- Límite de intentos de login ----------
class LoginRateLimiter:
    """Ventana deslizante en memoria: N fallos por IP en M minutos. Suficiente para un solo
    proceso; con varios servidores se movería a la BD o a Redis."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._failures: defaultdict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._failures[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def is_blocked(self, key: str) -> bool:
        return len(self._prune(key, time.monotonic())) >= self.max_attempts

    def register_failure(self, key: str) -> None:
        self._prune(key, time.monotonic()).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


# ---------- Cabeceras de seguridad ----------
def security_headers_middleware(
    *, hsts: bool
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    csp = "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' https://fonts.googleapis.com",
            "font-src https://fonts.gstatic.com",
            "img-src 'self' data:",
            "connect-src 'self'",
            "manifest-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
    )

    async def middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if hsts:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response

    return middleware
