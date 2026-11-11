"""Panel de Admin: usuarios, actividad, copia de seguridad y exportar.

Todo cuelga de AdminUser: quien no es admin recibe un 404, como si /admin no existiera.
"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from katiu.accounts import service as accounts
from katiu.admin import service
from katiu.audit import service as audit
from katiu.audit.models import AuditAction, AuditTarget
from katiu.core import clock
from katiu.core.config import get_settings
from katiu.core.security import verify_csrf
from katiu.core.templating import templates
from katiu.core.web import AdminUser, DbSession

router = APIRouter(prefix="/admin")
write = APIRouter(prefix="/admin", dependencies=[Depends(verify_csrf)])

OK_MESSAGES = {
    "alta": "Usuario creado. Pásale su contraseña en persona, no por chat.",
    "clave": "Contraseña nueva guardada. Pásasela en persona.",
    "activo": "Usuario activado.",
    "inactivo": "Usuario desactivado: ya no puede entrar.",
}


@router.get("", response_class=HTMLResponse)
def overview(request: Request, db: DbSession, admin: AdminUser) -> Response:
    since = clock.now() - timedelta(days=1)
    context = {
        "section": "mas",
        "backup": service.backup_status(get_settings().litestream_metrics_url),
        "totals": service.totals(db),
        "users": accounts.all_users(db),
        "failed_24h": audit.failed_logins_since(db, since),
        "events": audit.recent(db, limit=5),
    }
    return templates.TemplateResponse(request, "admin.html", context)


def _users_page(
    request: Request,
    db: DbSession,
    admin: AdminUser,
    *,
    message: str | None = None,
    error: str | None = None,
    form: dict[str, object] | None = None,
    status: int = 200,
) -> Response:
    return templates.TemplateResponse(
        request,
        "admin_users.html",
        {
            "section": "mas",
            "me": admin,
            "users": accounts.all_users(db),
            "last_logins": audit.last_logins(db),
            "message": message,
            "error": error,
            "form": form or {},
        },
        status_code=status,
    )


@router.get("/usuarios", response_class=HTMLResponse)
def users(request: Request, db: DbSession, admin: AdminUser, ok: str = "") -> Response:
    return _users_page(request, db, admin, message=OK_MESSAGES.get(ok))


@write.post("/usuarios", response_class=HTMLResponse)
def create_user(
    request: Request,
    db: DbSession,
    admin: AdminUser,
    email: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    password: Annotated[str, Form()],
    is_admin: Annotated[str, Form()] = "",
) -> Response:
    try:
        user = accounts.admin_create_user(
            db, email, display_name, password, is_admin=bool(is_admin)
        )
    except accounts.AccountError as exc:
        db.rollback()
        form: dict[str, object] = {
            "email": email,
            "display_name": display_name,
            "is_admin": bool(is_admin),
        }
        return _users_page(request, db, admin, error=str(exc), form=form, status=422)
    audit.record(db, admin.id, AuditAction.USER_CREATED, AuditTarget.USER, user.id)
    return RedirectResponse("/admin/usuarios?ok=alta", status_code=303)


@write.post("/usuarios/{user_id}/contrasena", response_class=HTMLResponse)
def set_password(
    request: Request,
    db: DbSession,
    admin: AdminUser,
    user_id: int,
    password: Annotated[str, Form()],
) -> Response:
    try:
        accounts.set_password(db, user_id, password)
    except accounts.AccountError as exc:
        return _users_page(request, db, admin, error=str(exc), status=422)
    audit.record(db, admin.id, AuditAction.USER_PASSWORD_RESET, AuditTarget.USER, user_id)
    return RedirectResponse("/admin/usuarios?ok=clave", status_code=303)


@write.post("/usuarios/{user_id}/activo", response_class=HTMLResponse)
def set_active(
    request: Request,
    db: DbSession,
    admin: AdminUser,
    user_id: int,
    active: Annotated[str, Form()] = "",
) -> Response:
    try:
        accounts.set_active(db, admin, user_id, bool(active))
    except accounts.AccountError as exc:
        return _users_page(request, db, admin, error=str(exc), status=422)
    action = AuditAction.USER_ACTIVATED if active else AuditAction.USER_DEACTIVATED
    audit.record(db, admin.id, action, AuditTarget.USER, user_id)
    return RedirectResponse(
        f"/admin/usuarios?ok={'activo' if active else 'inactivo'}", status_code=303
    )


@router.get("/actividad", response_class=HTMLResponse)
def activity(request: Request, db: DbSession, admin: AdminUser) -> Response:
    context = {"section": "mas", "events": audit.recent(db, limit=200)}
    return templates.TemplateResponse(request, "admin_activity.html", context)


@router.get("/exportar", response_class=HTMLResponse)
def export_form(request: Request, db: DbSession, admin: AdminUser) -> Response:
    context = {"section": "mas", "totals": service.totals(db)}
    return templates.TemplateResponse(request, "admin_export.html", context)


@write.post("/exportar")
def export(db: DbSession, admin: AdminUser, salud: Annotated[str, Form()] = "") -> Response:
    """POST (no GET) para que la descarga lleve token CSRF y no se dispare desde un enlace."""
    include_health = bool(salud)
    data = service.export_workbook(db, include_health=include_health)
    detail = "con salud" if include_health else "sin salud"
    audit.record(db, admin.id, AuditAction.EXPORT_DOWNLOADED, detail=detail)
    filename = f"katiu-yoga-{clock.today():%Y-%m-%d}.xlsx"
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
