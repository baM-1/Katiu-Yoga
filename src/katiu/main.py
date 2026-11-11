"""Punto de entrada: crea la app, monta middlewares, estáticos y los routers de cada módulo."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from katiu.accounts.routes import router as accounts_router
from katiu.admin.routes import router as admin_router
from katiu.admin.routes import write as admin_write
from katiu.attendance.routes import router as attendance_router
from katiu.attendance.routes import write as attendance_write
from katiu.classes.routes import router as classes_router
from katiu.core.config import get_settings
from katiu.core.security import security_headers_middleware
from katiu.core.templating import templates
from katiu.core.web import LoginRequiredError, is_htmx
from katiu.settings.routes import router as settings_router
from katiu.settings.routes import write as settings_write
from katiu.students.routes import router as students_router
from katiu.students.routes import write as students_write

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    """Fábrica de la app. Tenerla en una función permite crear apps aisladas en los tests."""
    settings = get_settings()
    if settings.is_prod and settings.secret_key.startswith("dev-"):
        raise RuntimeError("Falta KATIU_SECRET_KEY en producción.")

    app = FastAPI(
        title=settings.app_name,
        docs_url="/docs" if settings.is_dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.is_dev else None,
    )

    # Middlewares (el último añadido es el primero en ejecutarse).
    app.middleware("http")(security_headers_middleware(hsts=settings.is_prod))
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="katiu_sesion",
        max_age=settings.session_days * 24 * 3600,
        same_site="lax",
        https_only=settings.is_prod,  # cookie "Secure" en producción (HTTPS)
    )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    for router in (
        accounts_router,
        classes_router,
        attendance_router,
        attendance_write,
        students_router,
        students_write,
        settings_router,
        settings_write,
        admin_router,
        admin_write,
    ):
        app.include_router(router)

    @app.exception_handler(LoginRequiredError)
    async def _login_required(request: Request, _exc: LoginRequiredError) -> Response:
        if is_htmx(
            request
        ):  # HTMX no sigue redirecciones de página: se lo decimos con una cabecera
            return Response(status_code=401, headers={"HX-Redirect": "/entrar"})
        return RedirectResponse("/entrar", status_code=303)

    @app.get("/salud", include_in_schema=False)
    def health() -> dict[str, str]:
        """Endpoint de vida para el hosting y el CI."""
        return {"estado": "ok"}

    # PWA: el manifest y el service worker se sirven desde la raíz para controlar toda la app.
    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json"
        )

    @app.get("/sw.js", include_in_schema=False)
    def service_worker() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "sw.js",
            media_type="text/javascript",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/_estilo", response_class=HTMLResponse, include_in_schema=False)
    def style_guide(request: Request) -> Response:
        """Catálogo de componentes. Solo en desarrollo."""
        if not settings.is_dev:
            raise HTTPException(404)
        return templates.TemplateResponse(request, "style_guide.html", {"section": "mas"})

    return app


app = create_app()
