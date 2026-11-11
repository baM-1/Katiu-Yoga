"""Panel de Admin: estado de la copia de seguridad y exportación a Excel. Sin nada de HTTP."""

import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlmodel import Session, col, select

from katiu.attendance.models import Attendance
from katiu.classes.models import ClassSession, Plan, ScheduleSlot
from katiu.payments.models import PackPurchase, Payment
from katiu.students.models import Student

# ---------------------------------------------------------------- copia de seguridad


class BackupState(StrEnum):
    OK = "ok"  # todo lo escrito ya está en R2
    SYNCING = "syncing"  # hay cambios recientes que aún viajan hacia R2
    ERROR = "error"  # Litestream no responde o informa errores
    OFF = "off"  # no configurado (en local es lo normal)


@dataclass(frozen=True)
class BackupStatus:
    state: BackupState
    message: str
    db_bytes: int | None = None
    pending_bytes: int | None = None
    sync_errors: int | None = None


def parse_metrics(text: str) -> dict[str, float]:
    """Formato Prometheus de Litestream → {nombre: valor}. Una sola BD y una réplica, así que
    ignoramos las etiquetas ({db="…"})."""
    out: dict[str, float] = {}
    for line in text.splitlines():
        if not line.startswith("litestream_"):
            continue
        name_labels, _, value = line.rpartition(" ")
        name = name_labels.split("{", 1)[0]
        try:
            out[name] = float(value)
        except ValueError:
            continue
    return out


def backup_status_from_metrics(m: dict[str, float]) -> BackupStatus:
    """Compara dónde va la BD (WAL "sombra") con dónde va la réplica en R2."""
    needed = ("litestream_shadow_wal_index", "litestream_replica_wal_index")
    if not all(k in m for k in needed):
        return BackupStatus(BackupState.ERROR, "Litestream no informa de la réplica.")
    errors = int(m.get("litestream_sync_error_count", 0))
    db_bytes = int(m.get("litestream_db_size", 0))
    local = (m["litestream_shadow_wal_index"], m.get("litestream_shadow_wal_size", 0))
    remote = (m["litestream_replica_wal_index"], m.get("litestream_replica_wal_offset", 0))
    if remote >= local:
        pending: int | None = 0
    elif remote[0] == local[0]:
        pending = int(local[1] - remote[1])
    else:
        pending = None  # la réplica va un fichero WAL por detrás: no sabemos cuántos bytes
    if errors:
        return BackupStatus(
            BackupState.ERROR,
            f"Litestream ha tenido {errors} errores al sincronizar. Revisa los logs.",
            db_bytes,
            pending,
            errors,
        )
    if pending == 0:
        return BackupStatus(BackupState.OK, "Al día: todo está copiado en R2.", db_bytes, 0, errors)
    return BackupStatus(
        BackupState.SYNCING,
        "Copiando los últimos cambios (suele tardar un segundo).",
        db_bytes,
        pending,
        errors,
    )


def _fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=1.5) as res:  # URL de configuración, no del usuario
        return res.read().decode()


def backup_status(metrics_url: str | None, fetch: Callable[[str], str] = _fetch) -> BackupStatus:
    if not metrics_url:
        return BackupStatus(
            BackupState.OFF, "Sin copia configurada (normal en local; en el servidor, no)."
        )
    try:
        text = fetch(metrics_url)
    except OSError:
        return BackupStatus(BackupState.ERROR, "Litestream no responde. ¿Se ha parado?")
    return backup_status_from_metrics(parse_metrics(text))


# ---------------------------------------------------------------- exportar a Excel

Cell = str | int | float | bool | date | datetime | time | None


def _eur(cents: int | None) -> float | None:
    return None if cents is None else cents / 100


def _sheet(wb: Workbook, title: str, header: list[str], rows: Sequence[Sequence[Cell]]) -> None:
    ws = wb.create_sheet(title)
    ws.append(header)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append(row)
    ws.freeze_panes = "A2"
    for i, name in enumerate(header, start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = max(12, len(name) + 2)


def export_workbook(session: Session, *, include_health: bool = False) -> bytes:
    """Todo en un .xlsx: tu red de seguridad para salir de la app cuando quieras.

    Las notas de salud solo van si se piden expresamente (dato sensible, RGPD)."""
    plans = {p.id: p for p in session.exec(select(Plan).order_by(col(Plan.id))).all()}
    students = session.exec(select(Student).order_by(col(Student.full_name))).all()
    names = {s.id: s.full_name for s in students}
    classes = session.exec(
        select(ClassSession).order_by(col(ClassSession.date), col(ClassSession.start_time))
    ).all()
    class_by_id = {c.id: c for c in classes}

    def plan_name(plan_id: int | None) -> str | None:
        plan = plans.get(plan_id)
        return plan.name if plan else None

    wb = Workbook()
    wb.remove(wb.active)  # pyright: ignore[reportArgumentType]

    header = ["ID", "Nombre", "Teléfono", "Email", "Activo", "Cumpleaños", "Inicio con Kat"]
    header += ["Ubicación", "Plan habitual", "Acepta WhatsApp", "Notas"]
    if include_health:
        header.append("Salud")
    rows: list[list[Cell]] = []
    for s in students:
        row: list[Cell] = [s.id, s.full_name, s.phone_e164, s.email, s.active, s.birthday]
        row += [s.started_on, s.location, plan_name(s.default_plan_id), s.whatsapp_consent]
        row.append(s.notes)
        if include_health:
            row.append(s.health_notes)
        rows.append(row)
    _sheet(wb, "Alumnos", header, rows)

    _sheet(
        wb,
        "Clases",
        ["ID", "Fecha", "Hora", "Minutos", "Tipo", "Precio €", "Ubicación", "Notas"],
        [
            (
                c.id,
                c.date,
                c.start_time,
                c.duration_min,
                plan_name(c.plan_id),
                _eur(c.price_cents),
                c.location,
                c.notes,
            )
            for c in classes
        ],
    )

    paid = {p.attendance_id for p in session.exec(select(Payment)).all() if p.attendance_id}
    att_rows: list[tuple[Cell, ...]] = []
    for a in session.exec(select(Attendance).order_by(col(Attendance.id))).all():
        cls = class_by_id.get(a.class_session_id)
        att_rows.append(
            (
                a.id,
                cls.date if cls else None,
                cls.start_time if cls else None,
                names.get(a.student_id),
                a.status.value,
                _eur(a.price_cents),
                a.id in paid,
            )
        )
    _sheet(
        wb,
        "Asistencias",
        ["ID", "Fecha", "Hora", "Alumno", "Estado", "Precio €", "Pagada"],
        att_rows,
    )

    _sheet(
        wb,
        "Pagos",
        ["ID", "Fecha", "Alumno", "Importe €", "Método", "Concepto"],
        [
            (
                p.id,
                p.paid_on,
                names.get(p.student_id),
                _eur(p.amount_cents),
                p.method.value,
                p.concept,
            )
            for p in session.exec(select(Payment).order_by(col(Payment.paid_on))).all()
        ],
    )

    _sheet(
        wb,
        "Bonos",
        ["ID", "Alumno", "Tipo", "Comprado", "Clases", "Precio €", "Caduca"],
        [
            (
                b.id,
                names.get(b.student_id),
                plan_name(b.plan_id),
                b.purchased_on,
                b.classes_total,
                _eur(b.price_cents),
                b.expires_on,
            )
            for b in session.exec(select(PackPurchase)).all()
        ],
    )

    _sheet(
        wb,
        "Tarifas",
        ["ID", "Nombre", "Tipo", "Formato", "Modalidad", "Precio €", "Clases", "Días", "Activa"],
        [
            (
                p.id,
                p.name,
                p.kind.value,
                p.format.value,
                p.modality.value,
                _eur(p.price_cents),
                p.classes_included,
                p.validity_days,
                p.active,
            )
            for p in plans.values()
        ],
    )

    weekdays = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    _sheet(
        wb,
        "Horario",
        ["ID", "Día", "Hora", "Minutos", "Tipo", "Activo"],
        [
            (
                h.id,
                weekdays[h.weekday],
                h.start_time,
                h.duration_min,
                plan_name(h.plan_id),
                h.active,
            )
            for h in session.exec(select(ScheduleSlot)).all()
        ],
    )

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


@dataclass(frozen=True)
class Totals:
    students_active: int
    students_total: int
    classes: int
    attendances: int


def totals(session: Session) -> Totals:
    students = session.exec(select(Student)).all()
    return Totals(
        students_active=sum(1 for s in students if s.active),
        students_total=len(students),
        classes=len(session.exec(select(ClassSession.id)).all()),
        attendances=len(session.exec(select(Attendance.id)).all()),
    )
