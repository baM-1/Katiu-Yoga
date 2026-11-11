"""Ajustes: aquí Kat abre nuevos horarios o una clase puntual sin tocar el código."""

from datetime import date, time
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlmodel import col, select

from katiu.accounts.service import AccountError, change_password
from katiu.classes import service as classes
from katiu.classes.models import Plan, PlanKind
from katiu.core import clock
from katiu.core.security import verify_csrf
from katiu.core.templating import templates
from katiu.core.web import CurrentUser, DbSession

router = APIRouter()
write = APIRouter(dependencies=[Depends(verify_csrf)])


def _bookable_plans(db: DbSession) -> list[Plan]:
    """Solo las clases sueltas activas: un horario se define por el tipo de clase, no por bono."""
    return list(
        db.exec(
            select(Plan)
            .where(col(Plan.active), Plan.kind == PlanKind.DROP_IN)
            .order_by(col(Plan.id))
        ).all()
    )


@router.get("/mas", response_class=HTMLResponse)
def more(request: Request, user: CurrentUser) -> Response:
    return templates.TemplateResponse(request, "more.html", {"section": "mas", "user": user})


@router.get("/dinero", response_class=HTMLResponse)
def money(request: Request, user: CurrentUser) -> Response:
    return templates.TemplateResponse(request, "money_soon.html", {"section": "dinero"})


def _schedule_page(
    request: Request,
    db: DbSession,
    *,
    message: str | None = None,
    error: str | None = None,
    status: int = 200,
) -> Response:
    return templates.TemplateResponse(
        request,
        "schedule.html",
        {
            "section": "mas",
            "slots": classes.active_slots(db),
            "plans": _bookable_plans(db),
            "weekdays": classes.WEEKDAYS,
            "today": clock.today(),
            "message": message,
            "error": error,
        },
        status_code=status,
    )


@router.get("/ajustes/horario", response_class=HTMLResponse)
def schedule(request: Request, db: DbSession, user: CurrentUser, ok: str = "") -> Response:
    messages = {
        "franja": "¡Horario guardado! Las clases ya aparecen en Hoy. Om.",
        "pausa": "Horario pausado.",
        "extra": "¡Clase extra creada! Más esterillas, más prana.",
    }
    return _schedule_page(request, db, message=messages.get(ok))


@write.post("/ajustes/horario")
def add_slot(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    weekday: Annotated[int, Form()],
    start_time: Annotated[time, Form()],
    plan_id: Annotated[int, Form()],
    duration_min: Annotated[int, Form()] = 60,
) -> Response:
    try:
        classes.add_slot(db, weekday, start_time, plan_id, duration_min)
    except classes.ClassError as exc:
        return _schedule_page(request, db, error=str(exc), status=422)
    classes.generate_sessions(db, clock.today())
    return RedirectResponse("/ajustes/horario?ok=franja", status_code=303)


@write.post("/ajustes/horario/{slot_id}/pausar")
def pause_slot(request: Request, db: DbSession, user: CurrentUser, slot_id: int) -> Response:
    try:
        classes.deactivate_slot(db, slot_id, clock.today())
    except classes.ClassError as exc:
        return _schedule_page(request, db, error=str(exc), status=404)
    return RedirectResponse("/ajustes/horario?ok=pausa", status_code=303)


@write.post("/ajustes/clase-extra")
def extra_class(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    day: Annotated[date, Form()],
    start_time: Annotated[time, Form()],
    plan_id: Annotated[int, Form()],
    duration_min: Annotated[int, Form()] = 60,
) -> Response:
    try:
        cls = classes.create_extra_class(db, day, start_time, plan_id, duration_min)
    except classes.ClassError as exc:
        return _schedule_page(request, db, error=str(exc), status=422)
    return RedirectResponse(f"/clases/{cls.id}", status_code=303)


@router.get("/ajustes/contrasena", response_class=HTMLResponse)
def password_form(request: Request, user: CurrentUser) -> Response:
    return templates.TemplateResponse(request, "password.html", {"section": "mas"})


@write.post("/ajustes/contrasena", response_class=HTMLResponse)
def password_change(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    current: Annotated[str, Form()],
    new: Annotated[str, Form()],
) -> Response:
    try:
        change_password(db, user, current, new)
    except AccountError as exc:
        return templates.TemplateResponse(
            request, "password.html", {"section": "mas", "error": str(exc)}, status_code=422
        )
    return templates.TemplateResponse(
        request, "password.html", {"section": "mas", "message": "Contraseña cambiada ✓"}
    )
