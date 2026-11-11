"""Reglas de limpieza de datos. Funciones puras: entra un valor sucio, sale uno limpio.

Cada regla devuelve también, si aplica, una descripción de la anomalía para el informe.
"""

import re
import unicodedata
from datetime import date, datetime, time
from typing import Any

# Caracteres invisibles que WhatsApp mete al copiar teléfonos: marcas de dirección (U+202A/C,
# U+200E/F), espacio duro (U+00A0), espacios de ancho cero...
_INVISIBLE = dict.fromkeys(
    [
        0x00A0,
        0x200B,
        0x200C,
        0x200D,
        0x200E,
        0x200F,
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0x2060,
        0xFEFF,
    ],
    " ",
)

YES = {"sí", "si", "s", "yes", "y", "true", "1", "x"}
NO = {"no", "n", "false", "0", ""}


def strip_invisible(text: str) -> str:
    return text.translate(_INVISIBLE)


def clean_text(value: Any) -> str | None:
    """Quita invisibles, espacios sobrantes y dobles. Vacío → None."""
    if value is None:
        return None
    text = unicodedata.normalize("NFC", strip_invisible(str(value)))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def clean_name(value: Any) -> str | None:
    """ "Oscar " → "Oscar". No cambiamos mayúsculas: "DAlo" puede ser intencionado."""
    return clean_text(value)


def parse_yes_no(value: Any) -> bool | None:
    """ "Sí"/"No" del Excel → bool. Algo no reconocible → None (y el llamador lo reporta)."""
    if isinstance(value, bool):
        return value
    text = (clean_text(value) or "").lower()
    if text in YES:
        return True
    if text in NO:
        return False
    return None


def normalize_phone(value: Any) -> tuple[str | None, str | None]:
    """Teléfono → E.164 (+34600111222). Devuelve (teléfono, anomalía).

    Reglas, en orden:
    - Se quitan invisibles, espacios, guiones, paréntesis. "00" inicial equivale a "+".
    - 9 dígitos que empiezan por 6, 7, 8 o 9 → móvil/fijo español: +34.
    - 11 dígitos que empiezan por 34 → +34 sin el "+" escrito.
    - 12 dígitos que empiezan por 52 → México (+52 + 10 dígitos).
    - Con "+" explícito y 8-15 dígitos → se respeta.
    - Cualquier otra cosa → None + anomalía (mejor sin teléfono que con uno inventado).
    """
    raw = clean_text(value)
    if raw is None:
        return None, None
    has_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits, has_plus = digits[2:], True

    if has_plus and 8 <= len(digits) <= 15:
        return f"+{digits}", None
    if len(digits) == 9 and digits[0] in "6789":
        return f"+34{digits}", None
    if len(digits) == 11 and digits.startswith("34"):
        return f"+{digits}", None
    if len(digits) == 12 and digits.startswith("52"):
        return f"+{digits}", None
    return (
        None,
        f"teléfono con prefijo no reconocido ({len(digits)} dígitos, empieza por {digits[:2]})",
    )


def parse_date(value: Any) -> tuple[date | None, str | None]:
    """Fecha del Excel → date. Acepta datetime, date y texto dd/mm/aa con separadores raros."""
    if value is None or value == "":
        return None, None
    if isinstance(value, datetime):
        return value.date(), None
    if isinstance(value, date):
        return value, None
    text = clean_text(value) or ""
    match = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})", text)
    if match:
        day, month, year = (int(g) for g in match.groups())
        year += 2000 if year < 100 else 0
        try:
            return date(
                year, month, day
            ), f"fecha escrita como texto ({text!r}), interpretada dd/mm/aa"
        except ValueError:
            pass
    return None, f"fecha no reconocible ({text!r})"


def parse_time(value: Any) -> time | None:
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time()
    text = clean_text(value)
    if text and (m := re.fullmatch(r"(\d{1,2})[:.h](\d{2})?", text)):
        return time(int(m.group(1)), int(m.group(2) or 0))
    return None


def parse_duration_minutes(value: Any) -> int | None:
    """ "1h" → 60 · "1.5h" → 90 · "45min" → 45 · 60 → 60."""
    if isinstance(value, int | float):
        return int(value)
    text = (clean_text(value) or "").lower().replace(",", ".")
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)\s*h", text):
        return round(float(m.group(1)) * 60)
    if m := re.fullmatch(r"(\d+)\s*(?:min|m)", text):
        return int(m.group(1))
    return None


STUDENT_COLUMNS = (
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
)


def realign_student_row(row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Detecta y corrige las filas de ALUMNOS con las columnas corridas.

    Síntoma: en "Email" aparece "Sí"/"No" (que es "Activo") y todo lo de su derecha está
    desplazado una columna a la izquierda. Arreglo: insertar un Email vacío y desplazar a la
    derecha. Devuelve (fila corregida, si se corrigió).
    """
    email = row.get("Email")
    if parse_yes_no(email) is None or email in (None, ""):
        return row, False
    cols = list(STUDENT_COLUMNS)
    start = cols.index("Email")
    fixed = dict(row)
    fixed["Email"] = None
    for i in range(len(cols) - 1, start, -1):
        fixed[cols[i]] = row.get(cols[i - 1])
    return fixed, True


def clean_email(value: Any) -> str | None:
    text = clean_text(value)
    if text and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", text):
        return text.lower()
    return None
