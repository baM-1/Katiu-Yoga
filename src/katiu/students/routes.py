"""Alumnos: lista con buscador, ficha, alta y edición."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from katiu.core.security import verify_csrf
from katiu.core.templating import templates
from katiu.core.web import CurrentUser, DbSession, is_htmx
from katiu.students import service

router = APIRouter(prefix="/alumnos")
write = APIRouter(prefix="/alumnos", dependencies=[Depends(verify_csrf)])


@router.get("", response_class=HTMLResponse)
def student_list(
    request: Request, db: DbSession, user: CurrentUser, q: str = "", todos: bool = False
) -> Response:
    students = service.search(db, q, include_inactive=todos)
    context = {"section": "alumnos", "students": students, "q": q, "todos": todos}
    # Con HTMX solo devolvemos la lista (el buscador pide resultados mientras escribes).
    template = "_student_list.html" if is_htmx(request) else "students.html"
    return templates.TemplateResponse(request, template, context)


@router.get("/{student_id}", response_class=HTMLResponse)
def student_profile(
    request: Request, db: DbSession, user: CurrentUser, student_id: int, guardado: bool = False
) -> Response:
    try:
        profile = service.profile(db, student_id)
    except service.StudentError as exc:
        raise HTTPException(404, str(exc)) from exc
    context = {"section": "alumnos", "p": profile, "saved": guardado}
    return templates.TemplateResponse(request, "student.html", context)


@write.post("", response_class=HTMLResponse)
def create(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    full_name: Annotated[str, Form()],
    phone: Annotated[str, Form()] = "",
) -> Response:
    try:
        student = service.create_student(db, full_name, phone or None)
    except service.StudentError as exc:
        students = service.search(db)
        return templates.TemplateResponse(
            request,
            "students.html",
            {
                "section": "alumnos",
                "students": students,
                "q": "",
                "error": str(exc),
                "form": {"full_name": full_name, "phone": phone},
            },
            status_code=422,
        )
    return RedirectResponse(f"/alumnos/{student.id}", status_code=303)


def _form_context(db: DbSession, student_id: int, **extra: object) -> dict[str, object]:
    profile = service.profile(db, student_id, history_limit=0)
    s = profile.student
    return {
        "section": "alumnos",
        "s": s,
        "plans": service.plan_choices(db, s.default_plan_id),
        **extra,
    }


@router.get("/{student_id}/editar", response_class=HTMLResponse)
def edit_form(request: Request, db: DbSession, user: CurrentUser, student_id: int) -> Response:
    try:
        context = _form_context(db, student_id)
    except service.StudentError as exc:
        raise HTTPException(404, str(exc)) from exc
    return templates.TemplateResponse(request, "student_edit.html", context)


def _date(value: str) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError as exc:
        raise service.StudentError("Hay una fecha que no se entiende.") from exc


@write.post("/{student_id}", response_class=HTMLResponse)
def update(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    student_id: int,
    full_name: Annotated[str, Form()],
    phone: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    birthday: Annotated[str, Form()] = "",
    started_on: Annotated[str, Form()] = "",
    location: Annotated[str, Form()] = "",
    default_plan_id: Annotated[str, Form()] = "",
    health_notes: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    active: Annotated[str, Form()] = "",
    whatsapp_consent: Annotated[str, Form()] = "",
) -> Response:
    try:
        changes = service.StudentChanges(
            full_name=full_name,
            phone=phone or None,
            email=email or None,
            birthday=_date(birthday),
            started_on=_date(started_on),
            location=location or None,
            default_plan_id=int(default_plan_id) if default_plan_id else None,
            health_notes=health_notes,
            notes=notes,
            active=bool(active),
            whatsapp_consent=bool(whatsapp_consent),
        )
        service.update_student(db, student_id, changes)
    except service.StudentError as exc:
        db.rollback()
        try:
            context = _form_context(
                db,
                student_id,
                error=str(exc),
                form=dict(
                    full_name=full_name,
                    phone=phone,
                    email=email,
                    birthday=birthday,
                    started_on=started_on,
                    location=location,
                    default_plan_id=default_plan_id,
                    health_notes=health_notes,
                    notes=notes,
                    active=bool(active),
                    whatsapp_consent=bool(whatsapp_consent),
                ),
            )
        except service.StudentError as missing:
            raise HTTPException(404, str(missing)) from missing
        return templates.TemplateResponse(request, "student_edit.html", context, status_code=422)
    # PRG: tras guardar, redirigimos a la ficha (recargar no reenvía el formulario).
    return RedirectResponse(f"/alumnos/{student_id}?guardado=1", status_code=303)
