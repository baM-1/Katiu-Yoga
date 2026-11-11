"""Una prueba por cada regla de limpieza del Excel. Datos ficticios."""

from datetime import date, datetime, time

import pytest

from katiu.importing import cleaning


class TestTelefonos:
    def test_quita_invisibles_de_whatsapp(self) -> None:
        assert cleaning.normalize_phone("‪34\xa0600\xa0111 222‬") == ("+34600111222", None)

    @pytest.mark.parametrize(
        ("raw", "e164"),
        [
            ("34 600 111 222", "+34600111222"),
            ("600111222", "+34600111222"),
            ("+34 600-111-222", "+34600111222"),
            ("0034 600 111 222", "+34600111222"),
            ("52 55 1234 5678", "+525512345678"),  # México
            ("+380 95 123 4567", "+380951234567"),  # "+" explícito: se respeta
        ],
    )
    def test_formatos_validos(self, raw: str, e164: str) -> None:
        assert cleaning.normalize_phone(raw) == (e164, None)

    def test_prefijo_dudoso_no_se_inventa(self) -> None:
        phone, issue = cleaning.normalize_phone("38 954954333")
        assert phone is None
        assert issue is not None and "prefijo" in issue

    def test_vacio(self) -> None:
        assert cleaning.normalize_phone(None) == (None, None)
        assert cleaning.normalize_phone("  ") == (None, None)


class TestNombres:
    def test_recorta_espacios_sobrantes(self) -> None:
        assert cleaning.clean_name("Oscar ") == "Oscar"
        assert cleaning.clean_name("  Ana   María\xa0 ") == "Ana María"

    def test_no_toca_mayusculas(self) -> None:
        assert cleaning.clean_name("Ana DAlo") == "Ana DAlo"


class TestFechas:
    def test_datetime_del_excel(self) -> None:
        assert cleaning.parse_date(datetime(2026, 9, 9)) == (date(2026, 9, 9), None)

    def test_texto_con_separadores_raros(self) -> None:
        parsed, issue = cleaning.parse_date("11/09.26")
        assert parsed == date(2026, 9, 11)
        assert issue is not None  # se reporta aunque se arregle

    def test_irreconocible(self) -> None:
        parsed, issue = cleaning.parse_date("pronto")
        assert parsed is None and issue is not None


class TestOtros:
    @pytest.mark.parametrize(("raw", "value"), [("Sí", True), ("si", True), ("No", False)])
    def test_si_no(self, raw: str, value: bool) -> None:
        assert cleaning.parse_yes_no(raw) is value

    def test_si_no_desconocido(self) -> None:
        assert cleaning.parse_yes_no("quizá") is None

    @pytest.mark.parametrize(
        ("raw", "minutes"), [("1h", 60), ("1.5h", 90), ("1,5 h", 90), ("45min", 45)]
    )
    def test_duracion(self, raw: str, minutes: int) -> None:
        assert cleaning.parse_duration_minutes(raw) == minutes

    def test_hora(self) -> None:
        assert cleaning.parse_time(time(9, 0)) == time(9, 0)
        assert cleaning.parse_time("18:30") == time(18, 30)

    def test_email(self) -> None:
        assert cleaning.clean_email(" Ana@Ejemplo.com ") == "ana@ejemplo.com"
        assert cleaning.clean_email("Sí") is None


class TestFilasCorridas:
    def test_detecta_y_realinea(self) -> None:
        corrida = {
            "Alumno_ID": "ALU-0099",
            "Nombre": "Ana Prueba",
            "Teléfono": "600111222",
            "Email": "Sí",  # en realidad es "Activo"
            "Activo": "Grupo Reggio",  # en realidad es el plan
            "TipoClase/Plan": 21,
            "Precio_por_clase": datetime(2026, 1, 1),
            "Aniversario": "Madrid",
            "Ubicación": "Lesión de rodilla",
            "Notas": None,
        }
        fixed, shifted = cleaning.realign_student_row(corrida)
        assert shifted
        assert fixed["Email"] is None
        assert fixed["Activo"] == "Sí"
        assert fixed["TipoClase/Plan"] == "Grupo Reggio"
        assert fixed["Precio_por_clase"] == 21
        assert fixed["Ubicación"] == "Madrid"
        assert fixed["Notas"] == "Lesión de rodilla"

    def test_fila_correcta_no_se_toca(self) -> None:
        row = {"Alumno_ID": "ALU-0001", "Email": "ana@ejemplo.com", "Activo": "Sí"}
        assert cleaning.realign_student_row(row) == (row, False)
