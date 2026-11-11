"""Importación idempotente del Excel de control.

Idempotente = se puede ejecutar N veces y el resultado es el mismo que ejecutarla una: cada fila
se busca por su `legacy_id` (ALU-0001, CLA-0001, REG-0001...) y se actualiza si ya existe.

Fuente de verdad: ALUMNOS, CLASES, CONTROL_DIARIO y CATALOGOS. No se importa nada de
DASHBOARD, RESUMEN_MENSUAL ni CONFIG (son datos derivados); RESUMEN_MENSUAL solo se usa para
cuadrar totales al final.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import Any

from sqlmodel import Session, SQLModel, select

from katiu.attendance.models import Attendance, AttendanceStatus
from katiu.attendance.repository import AttendanceRepository
from katiu.classes.catalog import PACK_VALIDITY_DAYS, TARIFAS_2026
from katiu.classes.models import ClassSession, Modality, Plan, PlanFormat, PlanKind
from katiu.classes.repository import ClassSessionRepository, PlanRepository
from katiu.core.money import to_cents
from katiu.core.repository import Repository
from katiu.importing import cleaning
from katiu.importing.excel import read_sheets
from katiu.payments.models import Payment, PaymentMethod
from katiu.payments.repository import PaymentRepository
from katiu.students.models import Student
from katiu.students.repository import StudentRepository

SHEETS = ["ALUMNOS", "CLASES", "CONTROL_DIARIO", "CATALOGOS", "RESUMEN_MENSUAL"]


@dataclass
class Anomaly:
    sheet: str
    ref: str  # legacy_id de la fila (nunca el nombre: el informe no lleva datos personales)
    problem: str
    resolution: str


@dataclass
class Reconciliation:
    ref: str
    excel_classes: int
    excel_income_cents: int
    imported_classes: int
    imported_income_cents: int

    @property
    def matches(self) -> bool:
        return (self.excel_classes, self.excel_income_cents) == (
            self.imported_classes,
            self.imported_income_cents,
        )


@dataclass
class ImportReport:
    created: Counter[str] = field(default_factory=Counter[str])
    updated: Counter[str] = field(default_factory=Counter[str])
    anomalies: list[Anomaly] = field(default_factory=list[Anomaly])
    reconciliation: list[Reconciliation] = field(default_factory=list[Reconciliation])

    def note(self, sheet: str, ref: str, problem: str, resolution: str) -> None:
        self.anomalies.append(Anomaly(sheet, ref, problem, resolution))


def _upsert[T: SQLModel](
    repo: Repository[T],
    legacy_id: str,
    values: dict[str, Any],
    factory: type[T],
    report: ImportReport,
    kind: str,
) -> T:
    """Busca por legacy_id: si existe lo actualiza, si no lo crea. Es lo que hace idempotente
    la importación."""
    obj = repo.get_by_legacy_id(legacy_id)
    if obj is None:
        obj = repo.add(factory(legacy_id=legacy_id, **values))
        report.created[kind] += 1
    else:
        for key, value in values.items():
            setattr(obj, key, value)
        repo.add(obj)
        report.updated[kind] += 1
    return obj


def import_workbook(session: Session, path: Path) -> ImportReport:
    sheets = read_sheets(path, SHEETS)
    report = ImportReport()
    seed_current_plans(session, report)
    legacy_plans = _import_legacy_plans(session, sheets["CATALOGOS"], report)
    students = _import_students(session, sheets["ALUMNOS"], legacy_plans, report)
    classes = _import_classes(session, sheets["CLASES"], legacy_plans, report)
    _import_attendance(session, sheets["CONTROL_DIARIO"], classes, students, report)
    session.commit()
    _reconcile(session, sheets["RESUMEN_MENSUAL"], report)
    return report


def seed_current_plans(session: Session, report: ImportReport) -> None:
    """Carga las tarifas 2026 si no existen (buscando por nombre)."""
    existing = {p.name for p in session.exec(select(Plan)).all()}
    for seed in TARIFAS_2026:
        if seed.name in existing:
            continue
        PlanRepository(session).add(
            Plan(
                name=seed.name,
                format=seed.format,
                modality=seed.modality,
                kind=seed.kind,
                price_cents=seed.price_cents,
                classes_included=seed.classes_included,
                validity_days=PACK_VALIDITY_DAYS if seed.kind is PlanKind.PACK else None,
            )
        )
        report.created["plan (tarifa 2026)"] += 1


def _import_legacy_plans(
    session: Session, rows: list[dict[str, Any]], report: ImportReport
) -> dict[str, Plan]:
    """Planes del Excel (CATALOGOS): se conservan como históricos e inactivos, para que las
    clases antiguas mantengan su precio. Devuelve {nombre en el Excel: Plan}."""
    repo = PlanRepository(session)
    by_name: dict[str, Plan] = {}
    for row in rows:
        legacy_id = cleaning.clean_text(row.get("Plan_ID"))
        name = cleaning.clean_text(row.get("Tipo_de_clase"))
        if not legacy_id or not name:
            continue
        fmt = PlanFormat.INDIVIDUAL if "individual" in name.lower() else PlanFormat.GROUP
        values = {
            "name": f"{name} (histórico)",
            "kind": PlanKind.DROP_IN,
            "format": fmt,
            "modality": Modality.IN_PERSON,
            "price_cents": to_cents(row.get("Precio") or 0),
            "active": False,
        }
        by_name[name] = _upsert(repo, legacy_id, values, Plan, report, "plan histórico")
    return by_name


def _import_students(
    session: Session,
    rows: list[dict[str, Any]],
    plans: dict[str, Plan],
    report: ImportReport,
) -> dict[str, Student]:
    repo = StudentRepository(session)
    out: dict[str, Student] = {}
    for raw in rows:
        row, shifted = cleaning.realign_student_row(raw)
        ref = cleaning.clean_text(row.get("Alumno_ID")) or "?"
        if shifted:
            report.note("ALUMNOS", ref, "columnas corridas (Email contenía Sí/No)", "realineada")

        raw_name = row.get("Nombre")
        name = cleaning.clean_name(raw_name)
        if not name:
            report.note("ALUMNOS", ref, "sin nombre", "fila ignorada")
            continue
        if isinstance(raw_name, str) and raw_name != name:
            report.note("ALUMNOS", ref, "nombre con espacios sobrantes", "recortado")

        raw_phone = row.get("Teléfono")
        phone, phone_issue = cleaning.normalize_phone(raw_phone)
        if phone_issue:
            report.note("ALUMNOS", ref, phone_issue, "teléfono vacío; original guardado en notas")
        elif raw_phone and cleaning.strip_invisible(str(raw_phone)) != str(raw_phone):
            report.note("ALUMNOS", ref, "teléfono con caracteres invisibles", "normalizado a E.164")

        started_on, date_issue = cleaning.parse_date(row.get("Aniversario"))
        if date_issue:
            report.note("ALUMNOS", ref, date_issue, "ok" if started_on else "fecha vacía")

        active = cleaning.parse_yes_no(row.get("Activo"))
        if active is None:
            report.note("ALUMNOS", ref, f"Activo no reconocible ({row.get('Activo')!r})", "activo")
            active = True

        plan_name = cleaning.clean_text(row.get("TipoClase/Plan"))
        plan = plans.get(plan_name or "")
        if plan_name and plan is None:
            report.note("ALUMNOS", ref, f"plan desconocido ({plan_name!r})", "sin plan")
        price = row.get("Precio_por_clase")
        if plan and price not in (None, "") and to_cents(price) != plan.price_cents:
            report.note(
                "ALUMNOS", ref, "precio por clase distinto al de su plan", "se usa el del plan"
            )

        notes: list[str] = []
        if phone_issue and raw_phone:
            notes.append(f"Teléfono original del Excel: {cleaning.clean_text(raw_phone)}")
        email = cleaning.clean_email(row.get("Email"))
        if row.get("Email") and not email:
            notes.append(f"Email original no válido: {cleaning.clean_text(row.get('Email'))}")

        values = {
            "full_name": name,
            "phone_e164": phone,
            "email": email,
            "started_on": started_on,
            "default_plan_id": plan.id if plan else None,
            "location": cleaning.clean_text(row.get("Ubicación")),
            # Las notas del Excel son lesiones/embarazo: se tratan como dato de salud (sensible).
            "health_notes": cleaning.clean_text(row.get("Notas")),
            "notes": "\n".join(notes) or None,
            "active": active,
        }
        out[ref] = _upsert(repo, ref, values, Student, report, "alumno")
    return out


def _import_classes(
    session: Session,
    rows: list[dict[str, Any]],
    plans: dict[str, Plan],
    report: ImportReport,
) -> dict[str, ClassSession]:
    repo = ClassSessionRepository(session)
    out: dict[str, ClassSession] = {}
    for row in rows:
        ref = cleaning.clean_text(row.get("Clase_ID")) or "?"
        day, issue = cleaning.parse_date(row.get("Fecha"))
        if day is None:
            report.note("CLASES", ref, issue or "sin fecha", "clase ignorada")
            continue
        plan = plans.get(cleaning.clean_text(row.get("Tipo_de_clase")) or "")
        if plan is None or plan.id is None:
            report.note("CLASES", ref, "tipo de clase desconocido", "clase ignorada")
            continue
        start = cleaning.parse_time(row.get("Hora"))
        if start is None:
            report.note("CLASES", ref, "hora no reconocible", "09:00 por defecto")
            start = time(9, 0)
        duration = cleaning.parse_duration_minutes(row.get("Duración"))
        if duration is None:
            report.note("CLASES", ref, "duración no reconocible", "60 min por defecto")
            duration = 60
        price = row.get("Precio")
        values = {
            "date": day,
            "start_time": start,
            "duration_min": duration,
            "plan_id": plan.id,
            "price_cents": to_cents(price) if price not in (None, "") else plan.price_cents,
            "notes": cleaning.clean_text(row.get("Notas")),
        }
        out[ref] = _upsert(repo, ref, values, ClassSession, report, "clase")
    return out


def _import_attendance(
    session: Session,
    rows: list[dict[str, Any]],
    classes: dict[str, ClassSession],
    students: dict[str, Student],
    report: ImportReport,
) -> None:
    attendance_repo = AttendanceRepository(session)
    payment_repo = PaymentRepository(session)
    for row in rows:
        ref = cleaning.clean_text(row.get("Registro_ID")) or "?"
        cls = classes.get(cleaning.clean_text(row.get("Clase_ID")) or "")
        student = students.get(cleaning.clean_text(row.get("Alumno_ID")) or "")
        if cls is None or student is None or cls.id is None or student.id is None:
            report.note("CONTROL_DIARIO", ref, "clase o alumno inexistente", "registro ignorado")
            continue
        if cleaning.parse_yes_no(row.get("Asistió")) is False:
            report.note("CONTROL_DIARIO", ref, "registro con Asistió = No", "no se importa")
            continue
        price = row.get("Precio_cobrado")
        price_cents = to_cents(price) if price not in (None, "") else cls.price_cents
        att = _upsert(
            attendance_repo,
            ref,
            {
                "class_session_id": cls.id,
                "student_id": student.id,
                "status": AttendanceStatus.ATTENDED,
                "price_cents": price_cents,
                "notes": cleaning.clean_text(row.get("Notas")),
            },
            Attendance,
            report,
            "asistencia",
        )
        if cleaning.parse_yes_no(row.get("Cobrado")) and price_cents > 0:
            _upsert(
                payment_repo,
                ref,
                {
                    "student_id": student.id,
                    "paid_on": cls.date,
                    "amount_cents": price_cents,
                    # El Excel no guarda cómo pagó: "other" es honesto; Kat puede corregirlo.
                    "method": PaymentMethod.OTHER,
                    "concept": "Clase (importado del Excel)",
                    "attendance_id": att.id,
                },
                Payment,
                report,
                "pago",
            )


def _reconcile(session: Session, rows: list[dict[str, Any]], report: ImportReport) -> None:
    """Compara, alumno a alumno, RESUMEN_MENSUAL del Excel con lo importado."""
    counts: Counter[int] = Counter()
    income: defaultdict[int, int] = defaultdict(int)
    for att in session.exec(select(Attendance)).all():
        counts[att.student_id] += 1
        income[att.student_id] += att.price_cents
    students = {s.legacy_id: s for s in session.exec(select(Student)).all()}
    for row in rows:
        ref = cleaning.clean_text(row.get("Alumno_ID"))
        student = students.get(ref)
        if not ref or student is None or student.id is None:
            continue
        report.reconciliation.append(
            Reconciliation(
                ref=ref,
                excel_classes=int(row.get("Clases_asistidas") or 0),
                excel_income_cents=to_cents(row.get("Ingreso_generado") or 0),
                imported_classes=counts[student.id],
                imported_income_cents=income[student.id],
            )
        )
