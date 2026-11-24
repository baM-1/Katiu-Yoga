"""Pasar lista: la pantalla más importante de la app."""

from datetime import date, time
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from katiu.attendance import service
from katiu.audit import service as audit
from katiu.audit.models import AuditAction, AuditTarget
from katiu.classes import service as classes
from katiu.classes.models import ClassSession, Plan
from katiu.core import clock
from katiu.core.money import format_eur
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
    return _roll_call_page(request, db, class_id)


def _roll_call_page(
    request: Request, db: DbSession, class_id: int, *, error: str | None = None
) -> Response:
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
            "error": error,
        },
        status_code=422 if error else 200,
    )


def _when(cls: ClassSession) -> str:
    return f"{cls.date:%d/%m} {cls.start_time:%H:%M}"


def _item_response(
    request: Request,
    db: DbSession,
    class_id: int,
    student_id: int,
    *,
    price_error: str | None = None,
) -> Response:
    """Devuelve la tarjeta actualizada + la barra de totales (fuera de banda, hx-swap-oob)."""
    return templates.TemplateResponse(
        request,
        "_roster_update.html",
        {
            "cls_id": class_id,
            "item": service.roster_item(db, class_id, student_id),
            "totals": service.totals(db, class_id),
            "price_error": price_error,
        },
        status_code=422 if price_error else 200,
    )


@write.post("/{class_id}/alumnos/{student_id}/asistencia", response_class=HTMLResponse)
def toggle_attendance(
    request: Request, db: DbSession, user: CurrentUser, class_id: int, student_id: int
) -> Response:
    cls, _ = _class_or_404(db, class_id)
    try:
        came = service.toggle_attendance(db, class_id, student_id)
    except service.AttendanceError as exc:
        raise HTTPException(404, str(exc)) from exc
    detail = f"{_when(cls)} · {'vino' if came else 'quitado'}"
    audit.record(
        db, user.id, AuditAction.ATTENDANCE_TOGGLED, AuditTarget.STUDENT, student_id, detail
    )
    return _item_response(request, db, class_id, student_id)


@write.post("/{class_id}/alumnos/{student_id}/pago", response_class=HTMLResponse)
def toggle_paid(
    request: Request, db: DbSession, user: CurrentUser, class_id: int, student_id: int
) -> Response:
    cls, _ = _class_or_404(db, class_id)
    try:
        paid = service.toggle_paid(db, class_id, student_id, clock.today())
    except service.AttendanceError as exc:
        raise HTTPException(404, str(exc)) from exc
    detail = f"{_when(cls)} · {'pagado' if paid else 'deshecho'}"
    audit.record(db, user.id, AuditAction.PAYMENT_TOGGLED, AuditTarget.STUDENT, student_id, detail)
    return _item_response(request, db, class_id, student_id)


@write.post("/{class_id}/cancelar", response_class=HTMLResponse)
def cancel_class(request: Request, db: DbSession, user: CurrentUser, class_id: int) -> Response:
    cls, _ = _class_or_404(db, class_id)
    try:
        classes.cancel_class(db, class_id)
    except classes.ClassError as exc:
        return _roll_call_page(request, db, class_id, error=str(exc))
    audit.record(db, user.id, AuditAction.CLASS_CANCELLED, AuditTarget.CLASS, class_id, _when(cls))
    return RedirectResponse(f"/clases/{class_id}", status_code=303)


@write.post("/{class_id}/reactivar", response_class=HTMLResponse)
def restore_class(request: Request, db: DbSession, user: CurrentUser, class_id: int) -> Response:
    cls, _ = _class_or_404(db, class_id)
    try:
        classes.restore_class(db, class_id)
    except classes.ClassError as exc:
        return _roll_call_page(request, db, class_id, error=str(exc))
    audit.record(db, user.id, AuditAction.CLASS_RESTORED, AuditTarget.CLASS, class_id, _when(cls))
    return RedirectResponse(f"/clases/{class_id}", status_code=303)


@write.post("/{class_id}/mover", response_class=HTMLResponse)
def move_class(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    class_id: int,
    day: Annotated[date, Form()],
    start_time: Annotated[time, Form()],
) -> Response:
    cls, _ = _class_or_404(db, class_id)
    before = _when(cls)
    try:
        moved = classes.move_class(db, class_id, day, start_time)
    except classes.ClassError as exc:
        return _roll_call_page(request, db, class_id, error=str(exc))
    detail = f"{before} → {_when(moved)}"
    audit.record(db, user.id, AuditAction.CLASS_MOVED, AuditTarget.CLASS, moved.id, detail)
    return RedirectResponse(f"/clases/{moved.id}", status_code=303)


@write.post("/{class_id}/alumnos/{student_id}/precio", response_class=HTMLResponse)
def override_price(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    class_id: int,
    student_id: int,
    amount: Annotated[str, Form()],
) -> Response:
    """Excepción puntual: otro precio para esta asistencia (descuento, invitación…)."""
    cls, _ = _class_or_404(db, class_id)
    try:
        before, after = service.override_price(db, class_id, student_id, amount)
    except service.AttendanceError as exc:
        try:
            return _item_response(request, db, class_id, student_id, price_error=str(exc))
        except service.AttendanceError as missing:
            raise HTTPException(404, str(missing)) from missing
    change = f"{format_eur(before, decimals=False)} → {format_eur(after, decimals=False)}"
    detail = f"{_when(cls)} · {change}"
    audit.record(db, user.id, AuditAction.PRICE_OVERRIDDEN, AuditTarget.STUDENT, student_id, detail)
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
    cls, _ = _class_or_404(db, class_id)
    try:
        student = service.quick_add(db, class_id, full_name, phone or None)
    except (StudentError, service.AttendanceError) as exc:
        return templates.TemplateResponse(
            request,
            "_form_error.html",
            {"error": str(exc)},
            status_code=422,
            headers={"HX-Retarget": "#quick-add-error", "HX-Reswap": "innerHTML"},
        )
    audit.record(db, user.id, AuditAction.QUICK_ADD, AuditTarget.STUDENT, student.id, _when(cls))
    response = _item_response(request, db, class_id, student.id or 0)
    response.headers["HX-Retarget"] = "#roster-attended"
    response.headers["HX-Reswap"] = "afterbegin"
    return response
