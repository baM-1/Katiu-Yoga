"""Dinero: quién le debe a Kat y cobrar desde aquí."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from katiu.audit import service as audit
from katiu.audit.models import AuditAction, AuditTarget
from katiu.core import clock
from katiu.core.money import format_eur
from katiu.core.security import verify_csrf
from katiu.core.templating import templates
from katiu.core.web import CurrentUser, DbSession
from katiu.payments import service
from katiu.payments.models import PaymentMethod

router = APIRouter(prefix="/dinero")
write = APIRouter(prefix="/dinero", dependencies=[Depends(verify_csrf)])

MESSAGES = {
    "cobrada": "¡Cobrada! Una deuda menos, un chakra más alineado.",
    "todo": "¡Todo cobrado! Cuentas en equilibrio, como un buen árbol (vrksasana).",
}


def reminder_text(debtor: service.Debtor) -> str:
    """El WhatsApp que Kat puede mandar con un toque (lo revisa antes de enviarlo)."""
    first = debtor.student.full_name.split()[0]
    n = len(debtor.unpaid)
    days = ", ".join(f"{u.session.date:%d/%m}" for u in debtor.unpaid[-6:])
    classes = "1 clase pendiente" if n == 1 else f"{n} clases pendientes"
    return (
        f"¡Hola, {first}! 🙏 Te escribo de Katiu Yoga: tienes {classes} de pago ({days}). "
        f"En total son {format_eur(debtor.balance_cents, decimals=False)}. "
        "Cuando puedas, por Bizum o en mano en la próxima clase. ¡Gracias! Namasté ✨"
    )


def _page(
    request: Request,
    db: DbSession,
    *,
    message: str | None = None,
    error: str | None = None,
    status: int = 200,
) -> Response:
    return templates.TemplateResponse(
        request,
        "money.html",
        {
            "section": "dinero",
            "overview": service.money_overview(db),
            "reminder_text": reminder_text,
            "message": message,
            "error": error,
        },
        status_code=status,
    )


@router.get("", response_class=HTMLResponse)
def money(request: Request, db: DbSession, user: CurrentUser, ok: str = "") -> Response:
    return _page(request, db, message=MESSAGES.get(ok))


@write.post("/asistencias/{attendance_id}/cobrar")
def collect_one(request: Request, db: DbSession, user: CurrentUser, attendance_id: int) -> Response:
    try:
        att = service.collect_attendance(db, attendance_id, clock.today(), PaymentMethod.CASH)
    except service.PaymentError as exc:
        return _page(request, db, error=str(exc), status=422)
    detail = f"dinero · {format_eur(att.price_cents, decimals=False)}"
    audit.record(
        db, user.id, AuditAction.PAYMENT_TOGGLED, AuditTarget.STUDENT, att.student_id, detail
    )
    return RedirectResponse("/dinero?ok=cobrada", status_code=303)


@write.post("/alumnos/{student_id}/cobrar-todo")
def collect_all(request: Request, db: DbSession, user: CurrentUser, student_id: int) -> Response:
    n = service.collect_all(db, student_id, clock.today(), PaymentMethod.CASH)
    if n == 0:
        return _page(request, db, error="No le quedaba nada pendiente.", status=422)
    detail = f"dinero · {n} clase{'' if n == 1 else 's'}"
    audit.record(db, user.id, AuditAction.PAYMENT_TOGGLED, AuditTarget.STUDENT, student_id, detail)
    return RedirectResponse("/dinero?ok=todo", status_code=303)
