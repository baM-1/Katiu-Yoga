"""Genera un Excel FICTICIO con la misma forma (y los mismos defectos) que el real.

Nunca usamos el Excel real en tests: tiene datos personales y de salud.
"""

from datetime import datetime, time
from pathlib import Path
from typing import Any

from openpyxl import Workbook


def _sheet(wb: Workbook, name: str, rows: list[list[Any]]) -> None:
    ws = wb.create_sheet(name)
    for row in rows:
        ws.append(row)
    for _ in range(5):  # filas vacías al final, como exporta Google Sheets
        ws.append([None] * len(rows[0]))


def build_fake_workbook(path: Path) -> Path:
    wb = Workbook()
    wb.remove(wb.active)  # pyright: ignore[reportArgumentType]
    _sheet(
        wb,
        "ALUMNOS",
        [
            [
                "Alumno_ID",
                "Nombre",
                "Teléfono",
                "Email",
                "Activo",
                "TipoClase/Plan",
                "Precio_por_clase",
                "Aniversario",
                "Ubicación",
                "Notas",
            ],
            [
                "ALU-0001",
                "Ana Prueba",
                "34 600 111 222",
                None,
                "Sí",
                "Grupo Reggio",
                21,
                datetime(2026, 2, 1),
                "Madrid",
                None,
            ],
            [
                "ALU-0002",
                "Bea Ficticia ",
                "‪34\xa0600\xa0333 444‬",
                None,
                "Sí",
                "Grupo Reggio",
                21.0,
                datetime(2026, 3, 1),
                "Madrid",
                "Lesión ficticia",
            ],
            # fila con columnas corridas (falta el Email)
            [
                "ALU-0003",
                "Carla Inventada",
                "600555666",
                "No",
                "Clase individual",
                30.0,
                datetime(2025, 5, 5),
                "Ciudad de México",
                None,
                None,
            ],
            [
                "ALU-0004",
                "Dani Demo",
                "38 900000000",
                None,
                "Sí",
                "Clase individual",
                30.0,
                "11/09.26",
                "Madrid",
                None,
            ],
        ],
    )
    _sheet(
        wb,
        "CLASES",
        [
            ["Clase_ID", "Fecha", "Día", "Hora", "Duración", "Tipo_de_clase", "Precio", "Notas"],
            [
                "CLA-0001",
                datetime(2026, 3, 6),
                "viernes",
                time(9, 0),
                "1h",
                "Grupo Reggio",
                21,
                None,
            ],
            [
                "CLA-0002",
                datetime(2026, 3, 13),
                "viernes",
                time(10, 0),
                "1h",
                "Grupo Reggio",
                21.0,
                None,
            ],
            [
                "CLA-0003",
                datetime(2026, 4, 10),
                "viernes",
                time(9, 0),
                "1h",
                "Clase individual",
                30.0,
                None,
            ],
        ],
    )
    _sheet(
        wb,
        "CONTROL_DIARIO",
        [
            [
                "Registro_ID",
                "Fecha",
                "Clase_ID",
                "Alumno_ID",
                "Alumno",
                "Asistió",
                "Precio_cobrado",
                "Cobrado",
                "Notas",
            ],
            [
                "REG-0001",
                datetime(2026, 3, 6),
                "CLA-0001",
                "ALU-0001",
                "Ana Prueba",
                "Sí",
                21,
                "Sí",
                None,
            ],
            [
                "REG-0002",
                datetime(2026, 3, 6),
                "CLA-0001",
                "ALU-0002",
                "Bea Ficticia ",
                "Sí",
                21.0,
                "Sí",
                None,
            ],
            [
                "REG-0003",
                datetime(2026, 3, 13),
                "CLA-0002",
                "ALU-0001",
                "Ana Prueba",
                "Sí",
                21.0,
                "No",
                None,
            ],
            [
                "REG-0004",
                datetime(2026, 4, 10),
                "CLA-0003",
                "ALU-0004",
                "Dani Demo",
                "Sí",
                30.0,
                "Sí",
                None,
            ],
        ],
    )
    _sheet(
        wb,
        "CATALOGOS",
        [
            # Dos tablas lado a lado que repiten cabecera "Tipo_de_clase", como en el real
            [
                "Día_ID",
                "Día",
                None,
                "Plan_ID",
                "Tipo_de_clase",
                "Precio",
                "Activo",
                None,
                "Horario_ID",
                "Día",
                "Hora",
                "Duración",
                "Tipo_de_clase",
            ],
            [
                "DIA-01",
                "Martes",
                None,
                "PLA-01",
                "Clase individual",
                30.0,
                "Sí",
                None,
                "HOR-01",
                "Martes",
                time(18, 0),
                "1h",
                "Grupo Reggio",
            ],
            [
                "DIA-02",
                "Miércoles",
                None,
                "PLA-02",
                "Grupo Reggio",
                21.0,
                "Sí",
                None,
                "HOR-02",
                "Miércoles",
                time(9, 0),
                "1h",
                "Clase individual",
            ],
        ],
    )
    _sheet(
        wb,
        "RESUMEN_MENSUAL",
        [
            [
                "Alumno_ID",
                "Alumno",
                "Plan",
                "Precio_por_clase",
                "Clases_asistidas",
                "Ingreso_generado",
                "Pagado",
                "Pendiente",
            ],
            ["ALU-0001", "Ana Prueba", "Grupo Reggio", 21, 1, 21, 21, 0],  # error como el real
            ["ALU-0002", "Bea Ficticia", "Grupo Reggio", 21, 1, 21, 21, 0],
            ["ALU-0003", "Carla Inventada", "Clase individual", 30, 0, 0, 0, 0],
            ["ALU-0004", "Dani Demo", "Clase individual", 30, 1, 30, 30, 0],
        ],
    )
    wb.save(path)
    return path
