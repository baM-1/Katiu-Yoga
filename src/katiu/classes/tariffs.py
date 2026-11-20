"""Tarifas: Kat (y Lalo) las crean, cambian de precio y archivan desde Más → Tarifas.

Regla de oro: cambiar el precio de una tarifa NO reescribe el pasado. Cada clase y cada
asistencia guardan una copia del precio del momento en que se crearon (ver ADR-0008).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlmodel import Session, col, func, select

from katiu.classes.catalog import NORMAL_GROUP_PLAN
from katiu.classes.models import Modality, Plan, PlanFormat, PlanKind, ScheduleSlot
from katiu.classes.repository import PlanRepository
from katiu.core.money import MAX_CLASS_PRICE_CENTS, to_cents
from katiu.students.models import Student


class TariffError(ValueError):
    pass


@dataclass(frozen=True)
class TariffRow:
    plan: Plan
    students: int  # alumnos activos con esta tarifa
    is_normal: bool


def normal_plan(session: Session) -> Plan | None:
    """La tarifa de grupo por defecto (30 €): la de todo alumno nuevo."""
    return session.exec(select(Plan).where(Plan.name == NORMAL_GROUP_PLAN)).first()


def group_choices(session: Session) -> Sequence[Plan]:
    """Tarifas de grupo de clase suelta activas: las que se eligen en la ficha del alumno."""
    return session.exec(
        select(Plan)
        .where(col(Plan.active), Plan.kind == PlanKind.DROP_IN, Plan.format == PlanFormat.GROUP)
        .order_by(col(Plan.price_cents).desc(), col(Plan.name))
    ).all()


def tariff_list(session: Session) -> list[TariffRow]:
    """Tarifas activas con cuántos alumnos activos las tienen. Grupo primero."""
    counts = dict(
        session.exec(
            select(Student.default_plan_id, func.count())
            .where(col(Student.active), col(Student.default_plan_id).is_not(None))
            .group_by(col(Student.default_plan_id))
        ).all()
    )
    plans = PlanRepository(session).active()
    order = {PlanFormat.GROUP: 0, PlanFormat.INDIVIDUAL: 1}
    rows = [TariffRow(p, counts.get(p.id, 0), p.name == NORMAL_GROUP_PLAN) for p in plans]
    rows.sort(key=lambda r: (order[r.plan.format], r.plan.kind != PlanKind.DROP_IN, r.plan.name))
    return rows


def _clean(session: Session, name: str, price: str, plan_id: int | None = None) -> tuple[str, int]:
    clean_name = " ".join((name or "").split())
    if not clean_name:
        raise TariffError("Ponle un nombre a la tarifa.")
    if len(clean_name) > 80:
        raise TariffError("El nombre es demasiado largo (máximo 80 letras).")
    clash = session.exec(
        select(Plan).where(
            func.lower(Plan.name) == clean_name.lower(), col(Plan.active), col(Plan.id) != plan_id
        )
    ).first()
    if clash:
        raise TariffError("Ya hay una tarifa con ese nombre.")
    try:
        cents = to_cents(price)
    except ValueError as exc:
        raise TariffError("Ese precio no se entiende. Escribe por ejemplo 25 o 22,50.") from exc
    if not 0 <= cents <= MAX_CLASS_PRICE_CENTS:
        raise TariffError("El precio tiene que estar entre 0 y 999 €.")
    return clean_name, cents


def create_tariff(
    session: Session,
    name: str,
    price: str,
    fmt: PlanFormat = PlanFormat.GROUP,
    modality: Modality = Modality.IN_PERSON,
) -> Plan:
    """Nueva tarifa de clase suelta. Los bonos (4/8 clases) llegan con la Fase 3 (Dinero)."""
    clean_name, cents = _clean(session, name, price)
    plan = PlanRepository(session).add(
        Plan(
            name=clean_name,
            kind=PlanKind.DROP_IN,
            format=fmt,
            modality=modality,
            price_cents=cents,
        )
    )
    session.commit()
    return plan


def update_tariff(session: Session, plan_id: int, name: str, price: str) -> tuple[Plan, int]:
    """Cambia nombre y precio. Devuelve (tarifa, precio anterior). Solo afecta a lo que se
    marque a partir de ahora."""
    plan = PlanRepository(session).get(plan_id)
    if plan is None or not plan.active:
        raise TariffError("Esa tarifa no existe.")
    clean_name, cents = _clean(session, name, price, plan_id)
    if plan.name == NORMAL_GROUP_PLAN and clean_name != plan.name:
        raise TariffError("La tarifa normal no se puede renombrar (es la de los alumnos nuevos).")
    before = plan.price_cents
    plan.name, plan.price_cents = clean_name, cents
    session.add(plan)
    session.commit()
    return plan, before


def archive_tariff(session: Session, plan_id: int) -> Plan:
    """Retira una tarifa sin borrarla: las clases antiguas siguen apuntando a ella."""
    plan = PlanRepository(session).get(plan_id)
    if plan is None or not plan.active:
        raise TariffError("Esa tarifa no existe.")
    if plan.name == NORMAL_GROUP_PLAN:
        raise TariffError("La tarifa normal no se puede archivar (es la de los alumnos nuevos).")
    students = session.exec(
        select(func.count())
        .select_from(Student)
        .where(col(Student.active), Student.default_plan_id == plan_id)
    ).one()
    if students:
        raise TariffError(
            f"{students} alumno(s) tienen esta tarifa. Cámbiales la tarifa antes de archivarla."
        )
    if session.exec(
        select(ScheduleSlot.id).where(col(ScheduleSlot.active), ScheduleSlot.plan_id == plan_id)
    ).first():
        raise TariffError("Un horario fijo usa esta tarifa. Pausa ese horario antes de archivarla.")
    plan.active = False
    session.add(plan)
    session.commit()
    return plan
