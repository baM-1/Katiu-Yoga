"""Alumnos: lista con buscador, ficha y alta."""

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
    request: Request, db: DbSession, user: CurrentUser, student_id: int
) -> Response:
    try:
        profile = service.profile(db, student_id)
    except service.StudentError as exc:
        raise HTTPException(404, str(exc)) from exc
    return templates.TemplateResponse(request, "student.html", {"section": "alumnos", "p": profile})


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
