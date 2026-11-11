"""Pantalla Hoy."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from katiu.classes import service
from katiu.core import clock
from katiu.core.templating import templates
from katiu.core.text import first_name
from katiu.core.web import CurrentUser, DbSession

router = APIRouter()


def _greeting(hour: int) -> str:
    if hour < 13:
        return "Buenos días"
    return "Buenas tardes" if hour < 21 else "Buenas noches"


@router.get("/", response_class=HTMLResponse)
def today(request: Request, db: DbSession, user: CurrentUser) -> Response:
    now = clock.now()
    todays, upcoming = service.today_cards(db, now.date())
    return templates.TemplateResponse(
        request,
        "today.html",
        {
            "section": "hoy",
            "greeting": f"{_greeting(now.hour)}, {first_name(user.display_name)}",
            "today": now.date(),
            "todays": todays,
            "upcoming": upcoming,
        },
    )
