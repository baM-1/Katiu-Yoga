"""Lectura del .xlsx: cada hoja como una lista de diccionarios {cabecera: valor}."""

from pathlib import Path
from typing import Any

from openpyxl import load_workbook


def read_sheets(path: Path, names: list[str]) -> dict[str, list[dict[str, Any]]]:
    # data_only=True: leemos el valor calculado, no la fórmula. read_only: rápido y poca memoria.
    wb = load_workbook(path, data_only=True, read_only=True)
    try:
        return {name: _rows(wb[name]) for name in names}
    finally:
        wb.close()


def _rows(sheet: Any) -> list[dict[str, Any]]:
    rows = sheet.iter_rows(values_only=True)
    header = next(rows, ())
    keys = _unique_keys(header)
    out: list[dict[str, Any]] = []
    for row in rows:
        if not any(c not in (None, "") for c in row):
            continue  # Google Sheets exporta cientos de filas vacías
        out.append({k: v for k, v in zip(keys, row, strict=False) if k})
    return out


def _unique_keys(header: tuple[Any, ...]) -> list[str | None]:
    """CATALOGOS tiene varias tablas lado a lado y repite cabeceras ("Día", "Tipo_de_clase").
    La primera aparición conserva el nombre; las siguientes se renombran "Día#2", "Día#3"...
    Sin esto, la segunda columna pisaría a la primera en el diccionario."""
    seen: dict[str, int] = {}
    keys: list[str | None] = []
    for h in header:
        if h is None or str(h).strip() == "":
            keys.append(None)
            continue
        name = str(h).strip()
        seen[name] = seen.get(name, 0) + 1
        keys.append(name if seen[name] == 1 else f"{name}#{seen[name]}")
    return keys
