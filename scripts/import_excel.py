"""Importa el Excel de control a la base de datos y genera data/import_report.md.

Uso:
    uv run python scripts/import_excel.py              # usa data/raw/Katiu_Yoga_CONTROL.xlsx
    uv run python scripts/import_excel.py ruta/al/archivo.xlsx

Se puede ejecutar tantas veces como quieras: no duplica nada (es idempotente).
"""

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlmodel import Session

from katiu.core.db import engine
from katiu.importing.report import render_markdown
from katiu.importing.service import import_workbook

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "xlsx", nargs="?", type=Path, default=ROOT / "data/raw/Katiu_Yoga_CONTROL.xlsx"
    )
    parser.add_argument("--report", type=Path, default=ROOT / "data/import_report.md")
    args = parser.parse_args()

    # 1) La BD siempre al día con las migraciones antes de escribir.
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")

    # 2) Importar y 3) escribir el informe.
    with Session(engine) as session:
        report = import_workbook(session, args.xlsx)
    args.report.write_text(render_markdown(report, args.xlsx.name), encoding="utf-8")

    mismatches = sum(not r.matches for r in report.reconciliation)
    print(f"✓ Importado. Creados: {dict(report.created)} · Actualizados: {dict(report.updated)}")
    print(f"  Anomalías: {len(report.anomalies)} · Alumnos que no cuadran: {mismatches}")
    print(f"  Informe: {args.report.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
