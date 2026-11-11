"""Informe de la importación en Markdown (sin nombres: solo IDs del Excel y cifras)."""

from datetime import datetime

from katiu.core.money import format_eur
from katiu.importing.service import ImportReport


def render_markdown(report: ImportReport, source_name: str) -> str:
    lines = [
        "# Informe de importación",
        "",
        f"- Origen: `{source_name}`",
        f"- Fecha: {datetime.now():%Y-%m-%d %H:%M}",
        "",
        "## Registros",
        "",
        "| Tipo | Creados | Actualizados |",
        "|---|---:|---:|",
    ]
    for kind in sorted(set(report.created) | set(report.updated)):
        lines.append(f"| {kind} | {report.created[kind]} | {report.updated[kind]} |")

    lines += ["", f"## Anomalías ({len(report.anomalies)})", ""]
    if report.anomalies:
        lines += ["| Hoja | Fila | Problema | Resolución |", "|---|---|---|---|"]
        lines += [
            f"| {a.sheet} | {a.ref} | {a.problem} | {a.resolution} |" for a in report.anomalies
        ]
    else:
        lines.append("Ninguna. 🙏")

    rec = report.reconciliation
    mismatches = [r for r in rec if not r.matches]
    excel_n = sum(r.excel_classes for r in rec)
    excel_eur = sum(r.excel_income_cents for r in rec)
    ours_n = sum(r.imported_classes for r in rec)
    ours_eur = sum(r.imported_income_cents for r in rec)
    lines += [
        "",
        "## Cuadre con RESUMEN_MENSUAL",
        "",
        "| | Asistencias | Ingresos |",
        "|---|---:|---:|",
        f"| Excel (RESUMEN_MENSUAL) | {excel_n} | {format_eur(excel_eur)} |",
        f"| Importado (CONTROL_DIARIO) | {ours_n} | {format_eur(ours_eur)} |",
        "",
        f"Alumnos que cuadran: {len(rec) - len(mismatches)} de {len(rec)}.",
    ]
    if mismatches:
        lines += [
            "",
            "Diferencias (la fuente de verdad es CONTROL_DIARIO, registro a registro):",
            "",
            "| Alumno | Excel | Importado |",
            "|---|---|---|",
        ]
        lines += [
            f"| {r.ref} | {r.excel_classes} clases · {format_eur(r.excel_income_cents)} "
            f"| {r.imported_classes} clases · {format_eur(r.imported_income_cents)} |"
            for r in mismatches
        ]
    return "\n".join(lines) + "\n"
