from pathlib import Path

import pytest
from sqlmodel import Session, col, func, select

from katiu.attendance.models import Attendance
from katiu.classes.models import ClassSession, Plan
from katiu.importing.report import render_markdown
from katiu.importing.service import ImportReport, import_workbook
from katiu.payments.models import Payment
from katiu.students.models import Student
from tests.factories import build_fake_workbook


@pytest.fixture
def xlsx(tmp_path: Path) -> Path:
    return build_fake_workbook(tmp_path / "fake.xlsx")


@pytest.fixture
def report(session: Session, xlsx: Path) -> ImportReport:
    return import_workbook(session, xlsx)


def _count(session: Session, model: type) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


def test_importa_todo(session: Session, report: ImportReport) -> None:
    assert _count(session, Student) == 4
    assert _count(session, ClassSession) == 3
    assert _count(session, Attendance) == 4
    assert _count(session, Payment) == 3  # REG-0003 no estaba cobrado


def test_es_idempotente(session: Session, xlsx: Path, report: ImportReport) -> None:
    second = import_workbook(session, xlsx)
    assert not second.created  # nada nuevo la segunda vez
    assert _count(session, Student) == 4
    assert _count(session, Attendance) == 4
    assert _count(session, Payment) == 3
    assert _count(session, Plan) == 10 + 2


def test_limpia_alumnos(session: Session, report: ImportReport) -> None:
    by_ref = {s.legacy_id: s for s in session.exec(select(Student)).all()}
    assert by_ref["ALU-0002"].full_name == "Bea Ficticia"
    assert by_ref["ALU-0002"].phone_e164 == "+34600333444"
    assert by_ref["ALU-0002"].health_notes == "Lesión ficticia"
    # fila corrida realineada
    carla = by_ref["ALU-0003"]
    assert carla.active is False
    assert carla.location == "Ciudad de México"
    assert carla.phone_e164 == "+34600555666"
    # teléfono dudoso: vacío y original en notas
    dani = by_ref["ALU-0004"]
    assert dani.phone_e164 is None
    assert dani.notes and "38 900000000" in dani.notes
    assert dani.started_on is not None and dani.started_on.isoformat() == "2026-09-11"


def test_planes_no_se_mezclan_con_cabeceras_repetidas(
    session: Session, report: ImportReport
) -> None:
    legacy = {
        p.legacy_id: p for p in session.exec(select(Plan).where(col(Plan.legacy_id).is_not(None)))
    }
    assert legacy["PLA-01"].name.startswith("Clase individual")
    assert legacy["PLA-01"].price_cents == 3000
    assert legacy["PLA-02"].name.startswith("Grupo Reggio")
    assert legacy["PLA-02"].price_cents == 2100
    assert not legacy["PLA-01"].active


def test_dinero_en_centimos(session: Session, report: ImportReport) -> None:
    prices = {a.legacy_id: a.price_cents for a in session.exec(select(Attendance)).all()}
    assert prices == {"REG-0001": 2100, "REG-0002": 2100, "REG-0003": 2100, "REG-0004": 3000}


def test_anomalias_reportadas(report: ImportReport) -> None:
    problems = {(a.ref, a.problem.split(" (")[0]) for a in report.anomalies}
    assert ("ALU-0003", "columnas corridas") in problems
    assert ("ALU-0002", "nombre con espacios sobrantes") in problems
    assert ("ALU-0002", "teléfono con caracteres invisibles") in problems
    assert ("ALU-0004", "teléfono con prefijo no reconocido") in problems


def test_cuadre_detecta_el_error_del_resumen(report: ImportReport) -> None:
    mismatches = {r.ref: r for r in report.reconciliation if not r.matches}
    assert set(mismatches) == {"ALU-0001"}
    assert mismatches["ALU-0001"].imported_classes == 2
    assert mismatches["ALU-0001"].imported_income_cents == 4200


def test_informe_sin_nombres(report: ImportReport) -> None:
    md = render_markdown(report, "fake.xlsx")
    for name in ("Ana", "Bea", "Carla", "Dani", "Lesión"):
        assert name not in md  # el informe solo lleva IDs y cifras


def test_tarifa_reggio_activa(session: Session, report: ImportReport) -> None:
    plans = {p.name: p for p in session.exec(select(Plan)).all()}
    reggio = plans["Grupo Reggio · clase suelta"]
    assert reggio.active
    assert reggio.price_cents == 2100
    assert plans["Grupal presencial · clase suelta"].price_cents == 3000
