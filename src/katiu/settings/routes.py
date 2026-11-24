"""Ajustes: aquí Kat abre nuevos horarios o una clase puntual sin tocar el código."""

from datetime import date, time
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlmodel import col, select

from katiu.accounts.service import AccountError, change_password
from katiu.audit import service as audit
from katiu.audit.models import AuditAction, AuditTarget
from katiu.classes import service as classes
from katiu.classes import tariffs
from katiu.classes.models import Modality, Plan, PlanFormat, PlanKind
from katiu.core import clock
from katiu.core.money import format_eur
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
        slot = classes.add_slot(db, weekday, start_time, plan_id, duration_min)
    except classes.ClassError as exc:
        return _schedule_page(request, db, error=str(exc), status=422)
    audit.record(db, user.id, AuditAction.SLOT_ADDED, AuditTarget.SLOT, slot.id)
    classes.generate_sessions(db, clock.today())
    return RedirectResponse("/ajustes/horario?ok=franja", status_code=303)


@write.post("/ajustes/horario/{slot_id}/pausar")
def pause_slot(request: Request, db: DbSession, user: CurrentUser, slot_id: int) -> Response:
    try:
        classes.deactivate_slot(db, slot_id, clock.today())
    except classes.ClassError as exc:
        return _schedule_page(request, db, error=str(exc), status=404)
    audit.record(db, user.id, AuditAction.SLOT_PAUSED, AuditTarget.SLOT, slot_id)
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
    audit.record(db, user.id, AuditAction.EXTRA_CLASS, AuditTarget.CLASS, cls.id)
    return RedirectResponse(f"/clases/{cls.id}", status_code=303)


def _tariffs_page(
    request: Request,
    db: DbSession,
    *,
    message: str | None = None,
    error: str | None = None,
    form: dict[str, str] | None = None,
    open_id: int | None = None,
    status: int = 200,
) -> Response:
    return templates.TemplateResponse(
        request,
        "tariffs.html",
        {
            "section": "mas",
            "rows": tariffs.tariff_list(db),
            "message": message,
            "error": error,
            "form": form,
            "open_id": open_id,
        },
        status_code=status,
    )


@router.get("/ajustes/tarifas", response_class=HTMLResponse)
def tariff_list(request: Request, db: DbSession, user: CurrentUser, ok: str = "") -> Response:
    messages = {
        "nueva": "¡Tarifa creada! Ya la puedes asignar en la ficha de cada alumno.",
        "guardada": "Tarifa guardada. El precio nuevo vale para lo que marques desde ahora.",
        "archivada": "Tarifa archivada. Namasté y hasta luego.",
    }
    return _tariffs_page(request, db, message=messages.get(ok))


@write.post("/ajustes/tarifas", response_class=HTMLResponse)
def tariff_create(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    name: Annotated[str, Form()],
    price: Annotated[str, Form()],
    format: Annotated[PlanFormat, Form()] = PlanFormat.GROUP,
    modality: Annotated[Modality, Form()] = Modality.IN_PERSON,
) -> Response:
    try:
        plan = tariffs.create_tariff(db, name, price, format, modality)
    except tariffs.TariffError as exc:
        form = {"name": name, "price": price, "format": format, "modality": modality}
        return _tariffs_page(request, db, error=str(exc), form=form, status=422)
    detail = format_eur(plan.price_cents, decimals=False)
    audit.record(db, user.id, AuditAction.PLAN_CREATED, AuditTarget.PLAN, plan.id, detail)
    return RedirectResponse("/ajustes/tarifas?ok=nueva", status_code=303)


@write.post("/ajustes/tarifas/{plan_id}", response_class=HTMLResponse)
def tariff_update(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    plan_id: int,
    name: Annotated[str, Form()],
    price: Annotated[str, Form()],
) -> Response:
    try:
        plan, before = tariffs.update_tariff(db, plan_id, name, price)
    except tariffs.TariffError as exc:
        db.rollback()
        return _tariffs_page(request, db, error=str(exc), open_id=plan_id, status=422)
    after = plan.price_cents
    detail = f"{format_eur(before, decimals=False)} → {format_eur(after, decimals=False)}"
    audit.record(db, user.id, AuditAction.PLAN_UPDATED, AuditTarget.PLAN, plan_id, detail)
    return RedirectResponse("/ajustes/tarifas?ok=guardada", status_code=303)


@write.post("/ajustes/tarifas/{plan_id}/archivar", response_class=HTMLResponse)
def tariff_archive(request: Request, db: DbSession, user: CurrentUser, plan_id: int) -> Response:
    try:
        tariffs.archive_tariff(db, plan_id)
    except tariffs.TariffError as exc:
        return _tariffs_page(request, db, error=str(exc), status=422)
    audit.record(db, user.id, AuditAction.PLAN_ARCHIVED, AuditTarget.PLAN, plan_id)
    return RedirectResponse("/ajustes/tarifas?ok=archivada", status_code=303)


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
    audit.record(db, user.id, AuditAction.PASSWORD_CHANGED, AuditTarget.USER, user.id)
    return templates.TemplateResponse(
        request, "password.html", {"section": "mas", "message": "Contraseña cambiada ✓"}
    )
