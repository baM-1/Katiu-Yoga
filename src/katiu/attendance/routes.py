"""Pasar lista: la pantalla más importante de la app."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from katiu.attendance import service
from katiu.classes.models import ClassSession, Plan
from katiu.core import clock
from katiu.core.security import verify_csrf
from katiu.core.templating import templates
from katiu.core.web import CurrentUser, DbSession
from katiu.students.service import StudentError

router = APIRouter(prefix="/clases")
write = APIRouter(prefix="/clases", dependencies=[Depends(verify_csrf)])


def _class_or_404(db: DbSession, class_id: int) -> tuple[ClassSession, Plan]:
    cls = db.get(ClassSession, class_id)
    if cls is None:
        raise HTTPException(404, "Esa clase no existe.")
    plan = db.get(Plan, cls.plan_id)
    assert plan is not None
    return cls, plan


@router.get("/{class_id}", response_class=HTMLResponse)
def roll_call(request: Request, db: DbSession, user: CurrentUser, class_id: int) -> Response:
    cls, plan = _class_or_404(db, class_id)
    items = service.roster(db, class_id)
    regulars = [i for i in items if i.is_regular or i.attended]
    others = [i for i in items if not (i.is_regular or i.attended)]
    return templates.TemplateResponse(
        request,
        "roll_call.html",
        {
            "section": "hoy",
            "cls": cls,
            "plan": plan,
            "regulars": regulars,
            "others": others,
            "totals": service.totals(db, class_id),
        },
    )


def _item_response(request: Request, db: DbSession, class_id: int, student_id: int) -> Response:
    """Devuelve la tarjeta actualizada + la barra de totales (fuera de banda, hx-swap-oob)."""
    return templates.TemplateResponse(
        request,
        "_roster_update.html",
        {
            "cls_id": class_id,
            "item": service.roster_item(db, class_id, student_id),
            "totals": service.totals(db, class_id),
        },
    )


@write.post("/{class_id}/alumnos/{student_id}/asistencia", response_class=HTMLResponse)
def toggle_attendance(
    request: Request, db: DbSession, user: CurrentUser, class_id: int, student_id: int
) -> Response:
    _class_or_404(db, class_id)
    try:
        service.toggle_attendance(db, class_id, student_id)
    except service.AttendanceError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _item_response(request, db, class_id, student_id)


@write.post("/{class_id}/alumnos/{student_id}/pago", response_class=HTMLResponse)
def toggle_paid(
    request: Request, db: DbSession, user: CurrentUser, class_id: int, student_id: int
) -> Response:
    _class_or_404(db, class_id)
    try:
        service.toggle_paid(db, class_id, student_id, clock.today())
    except service.AttendanceError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _item_response(request, db, class_id, student_id)


@write.post("/{class_id}/alumnos", response_class=HTMLResponse)
def quick_add(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    class_id: int,
    full_name: Annotated[str, Form()],
    phone: Annotated[str, Form()] = "",
) -> Response:
    _class_or_404(db, class_id)
    try:
        student = service.quick_add(db, class_id, full_name, phone or None)
    except StudentError as exc:
        return templates.TemplateResponse(
            request,
            "_form_error.html",
            {"error": str(exc)},
            status_code=422,
            headers={"HX-Retarget": "#quick-add-error", "HX-Reswap": "innerHTML"},
        )
    response = _item_response(request, db, class_id, student.id or 0)
    response.headers["HX-Retarget"] = "#roster-attended"
    response.headers["HX-Reswap"] = "afterbegin"
    return response
