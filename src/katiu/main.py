"""Punto de entrada: crea la app, monta los estáticos y registra los routers de cada módulo."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from katiu.core.config import get_settings
from katiu.core.templating import templates

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    """Fábrica de la app. Tenerla en una función permite crear apps aisladas en los tests."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        # La documentación OpenAPI solo se expone en desarrollo.
        docs_url="/docs" if settings.is_dev else None,
        redoc_url=None,
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "home.html", {"greeting": "Hola Kat 🌊"})

    @app.get("/salud", include_in_schema=False)
    def health() -> dict[str, str]:
        """Endpoint de vida para el hosting y el CI."""
        return {"estado": "ok"}

    return app


app = create_app()
