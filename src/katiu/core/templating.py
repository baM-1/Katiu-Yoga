"""Motor de plantillas Jinja2 compartido por todos los módulos.

Cada módulo tiene su carpeta `templates/`; aquí las juntamos todas en un solo cargador para
poder extender `base.html` desde cualquier sitio.
"""

from datetime import date
from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

from katiu.core.config import get_settings
from katiu.core.money import format_eur
from katiu.core.security import csrf_token
from katiu.core.text import initials, whatsapp_url

PKG = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PKG / "templates"
MODULES = ["accounts", "classes", "attendance", "students", "payments", "dashboard", "settings"]

MONTHS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]  # fmt: skip
WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def human_date(d: date, *, weekday: bool = True) -> str:
    """date(2026, 11, 13) → "viernes 13 de noviembre"."""
    text = f"{d.day} de {MONTHS[d.month - 1]}"
    return f"{WEEKDAYS[d.weekday()]} {text}" if weekday else text


def month_year(d: date) -> str:
    """date(2025, 12, 16) → "diciembre 2025"."""
    return f"{MONTHS[d.month - 1]} {d.year}"


templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.loader = ChoiceLoader(
    [FileSystemLoader(TEMPLATES_DIR)]
    + [FileSystemLoader(PKG / m / "templates") for m in MODULES if (PKG / m / "templates").is_dir()]
)
templates.env.globals["eur"] = format_eur
templates.env.globals["human_date"] = human_date
templates.env.globals["month_year"] = month_year
templates.env.globals["is_dev"] = get_settings().is_dev
templates.env.globals["csrf"] = csrf_token
templates.env.globals["initials"] = initials
templates.env.globals["whatsapp_url"] = whatsapp_url
