"""Panel de Admin: acceso, usuarios, actividad, copia de seguridad y exportación."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlmodel import Session, select

from katiu.accounts.models import User
from katiu.accounts.service import AccountError, create_user, make_admin, set_active
from katiu.admin import service as admin
from katiu.audit.models import AuditAction, AuditEvent
from katiu.classes.models import ClassSession
from katiu.students.models import Student
from tests.conftest import PASSWORD, csrf_from


@pytest.fixture
def as_admin(logged: TestClient, session: Session) -> TestClient:
    make_admin(session, "kat@ejemplo.com")
    return logged


def _events(session: Session, action: AuditAction) -> list[AuditEvent]:
    session.expire_all()
    return list(session.exec(select(AuditEvent).where(AuditEvent.action == action)).all())


def _login(client: TestClient, email: str, password: str) -> int:
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)  # el token del admin ya no vale
    token = csrf_from(client.get("/entrar").text)
    res = client.post(
        "/entrar",
        data={"email": email, "password": password, "csrf_token": token},
        follow_redirects=False,
    )
    return res.status_code


# ---------------------------------------------------------------- acceso


@pytest.mark.parametrize(
    "path", ["/admin", "/admin/usuarios", "/admin/actividad", "/admin/exportar"]
)
def test_quien_no_es_admin_ve_un_404(logged: TestClient, path: str) -> None:
    assert logged.get(path).status_code == 404


def test_quien_no_es_admin_no_puede_exportar(logged: TestClient) -> None:
    assert logged.post("/admin/exportar").status_code == 404


def test_sin_sesion_redirige_a_entrar(client: TestClient) -> None:
    res = client.get("/admin", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/entrar"


def test_el_enlace_solo_aparece_para_admins(logged: TestClient, session: Session) -> None:
    assert "Panel de Admin" not in logged.get("/mas").text
    make_admin(session, "kat@ejemplo.com")
    assert "Panel de Admin" in logged.get("/mas").text


def test_panel_muestra_cifras_y_copia(as_admin: TestClient, students: list[Student]) -> None:
    html = as_admin.get("/admin").text
    assert "Copia de seguridad" in html
    assert "Apagada" in html  # en tests no hay Litestream
    assert "asistencias" in html


# ---------------------------------------------------------------- usuarios


def test_crear_usuario_y_que_pueda_entrar(as_admin: TestClient, session: Session) -> None:
    res = as_admin.post(
        "/admin/usuarios",
        data={
            "email": "Ayuda@Ejemplo.com ",
            "display_name": "Ayuda",
            "password": "una-clave-larga",
        },
        follow_redirects=False,
    )
    assert res.status_code == 303
    user = session.exec(select(User).where(User.email == "ayuda@ejemplo.com")).one()
    assert not user.is_admin
    assert len(_events(session, AuditAction.USER_CREATED)) == 1
    assert _login(as_admin, "ayuda@ejemplo.com", "una-clave-larga") == 303


def test_crear_usuario_con_errores_conserva_el_formulario(as_admin: TestClient) -> None:
    res = as_admin.post(
        "/admin/usuarios",
        data={"email": "kat@ejemplo.com", "display_name": "Otra", "password": "una-clave-larga"},
    )
    assert res.status_code == 422
    assert "Ya existe un usuario con ese email." in res.text
    assert 'value="Otra"' in res.text

    res = as_admin.post(
        "/admin/usuarios", data={"email": "sin-arroba", "display_name": "X", "password": "12345678"}
    )
    assert res.status_code == 422
    assert "no parece válido" in res.text


def test_poner_contrasena_nueva(as_admin: TestClient, session: Session) -> None:
    other = create_user(session, "otra@ejemplo.com", "Otra", "clave-vieja-1")
    res = as_admin.post(
        f"/admin/usuarios/{other.id}/contrasena",
        data={"password": "clave-nueva-1"},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert len(_events(session, AuditAction.USER_PASSWORD_RESET)) == 1
    assert _login(as_admin, "otra@ejemplo.com", "clave-vieja-1") == 401
    assert _login(as_admin, "otra@ejemplo.com", "clave-nueva-1") == 303


def test_contrasena_corta_se_rechaza(as_admin: TestClient, session: Session) -> None:
    other = create_user(session, "otra@ejemplo.com", "Otra", "clave-vieja-1")
    res = as_admin.post(f"/admin/usuarios/{other.id}/contrasena", data={"password": "corta"})
    assert res.status_code == 422


def test_desactivar_usuario_le_impide_entrar(as_admin: TestClient, session: Session) -> None:
    other = create_user(session, "otra@ejemplo.com", "Otra", "clave-vieja-1")
    res = as_admin.post(f"/admin/usuarios/{other.id}/activo", follow_redirects=False)
    assert res.status_code == 303
    assert _login(as_admin, "otra@ejemplo.com", "clave-vieja-1") == 401
    assert len(_events(session, AuditAction.USER_DEACTIVATED)) == 1


def test_no_puedes_desactivarte_a_ti_mismo(as_admin: TestClient, session: Session) -> None:
    me = session.exec(select(User)).one()
    res = as_admin.post(f"/admin/usuarios/{me.id}/activo")
    assert res.status_code == 422
    assert "tu propia cuenta" in res.text


def test_siempre_queda_un_admin_activo(session: Session) -> None:
    a = create_user(session, "a@ejemplo.com", "A", "clave-larga-1")
    b = create_user(session, "b@ejemplo.com", "B", "clave-larga-1")
    make_admin(session, "a@ejemplo.com")
    with pytest.raises(AccountError, match="al menos un administrador"):
        set_active(session, b, a.id or 0, False)


# ---------------------------------------------------------------- actividad


def test_entradas_y_fallos_quedan_registrados(client: TestClient, session: Session) -> None:
    create_user(session, "kat@ejemplo.com", "Kat", PASSWORD)
    assert _login(client, "kat@ejemplo.com", "mal") == 401
    assert _login(client, "nadie@ejemplo.com", "mal") == 401
    assert _login(client, "kat@ejemplo.com", PASSWORD) == 303
    failed = _events(session, AuditAction.LOGIN_FAILED)
    assert [e.user_id is not None for e in failed] == [True, False]
    assert len(_events(session, AuditAction.LOGIN)) == 1
    # Nunca se guarda el email tecleado.
    assert all(e.detail is None for e in failed)


def test_editar_salud_se_apunta_sin_guardar_el_texto(
    as_admin: TestClient, session: Session, students: list[Student]
) -> None:
    sid = students[0].id
    res = as_admin.post(
        f"/alumnos/{sid}",
        data={"full_name": "Ana Prueba", "health_notes": "Lesión ficticia de rodilla"},
        follow_redirects=False,
    )
    assert res.status_code == 303
    (event,) = _events(session, AuditAction.STUDENT_UPDATED)
    assert event.target_id == sid
    assert event.detail == "cambió salud"
    rows = session.exec(select(AuditEvent)).all()
    assert not any("rodilla" in (e.detail or "") for e in rows)

    html = as_admin.get("/admin/actividad").text
    assert "editó una ficha (cambió salud)" in html
    assert "rodilla" not in html


def test_marcar_asistencia_y_cobro_se_registra(
    as_admin: TestClient,
    session: Session,
    friday_class: ClassSession,
    students: list[Student],
) -> None:
    cid, sid = friday_class.id, students[0].id
    assert as_admin.post(f"/clases/{cid}/alumnos/{sid}/asistencia").status_code == 200
    assert as_admin.post(f"/clases/{cid}/alumnos/{sid}/pago").status_code == 200
    (att,) = _events(session, AuditAction.ATTENDANCE_TOGGLED)
    assert att.detail == "13/11 09:00 · vino"
    (pay,) = _events(session, AuditAction.PAYMENT_TOGGLED)
    assert pay.detail == "13/11 09:00 · pagado"


# ---------------------------------------------------------------- exportar


def test_exportar_sin_salud_por_defecto(
    as_admin: TestClient, session: Session, students: list[Student]
) -> None:
    students[0].health_notes = "Lesión ficticia"
    session.add(students[0])
    session.commit()
    res = as_admin.post("/admin/exportar")
    assert res.status_code == 200
    assert "attachment" in res.headers["content-disposition"]
    assert res.headers["cache-control"] == "no-store"
    wb = load_workbook(BytesIO(res.content))
    assert wb.sheetnames == [
        "Alumnos", "Clases", "Asistencias", "Pagos", "Bonos", "Tarifas", "Horario"
    ]  # fmt: skip
    header = [c.value for c in wb["Alumnos"][1]]
    assert "Salud" not in header
    assert wb["Alumnos"].max_row == 1 + len(students)
    (event,) = _events(session, AuditAction.EXPORT_DOWNLOADED)
    assert event.detail == "sin salud"


def test_exportar_con_salud_si_se_pide(
    as_admin: TestClient, session: Session, students: list[Student]
) -> None:
    students[0].health_notes = "Lesión ficticia"
    session.add(students[0])
    session.commit()
    res = as_admin.post("/admin/exportar", data={"salud": "1"})
    ws = load_workbook(BytesIO(res.content))["Alumnos"]
    header = [c.value for c in ws[1]]
    col = header.index("Salud")
    assert "Lesión ficticia" in [row[col].value for row in ws.iter_rows(min_row=2)]
    assert _events(session, AuditAction.EXPORT_DOWNLOADED)[0].detail == "con salud"


# ---------------------------------------------------------------- copia de seguridad

# Copiado de un Litestream 0.3.13 real (réplica en disco).
METRICS = """# HELP litestream_db_size The current size of the real DB
litestream_db_size{db="/data/katiu.db"} 16384
litestream_replica_wal_index{db="/data/katiu.db",name="s3"} 0
litestream_replica_wal_offset{db="/data/katiu.db",name="s3"} 20632
litestream_shadow_wal_index{db="/data/katiu.db"} 0
litestream_shadow_wal_size{db="/data/katiu.db"} 20632
litestream_sync_error_count{db="/data/katiu.db"} 0
"""


def test_copia_al_dia() -> None:
    status = admin.backup_status("http://x/metrics", fetch=lambda _url: METRICS)
    assert status.state == admin.BackupState.OK
    assert status.db_bytes == 16384


def test_copia_con_cambios_pendientes() -> None:
    text = METRICS.replace('name="s3"} 20632', 'name="s3"} 16512')
    status = admin.backup_status("http://x/metrics", fetch=lambda _url: text)
    assert status.state == admin.BackupState.SYNCING
    assert status.pending_bytes == 4120


def test_copia_con_errores() -> None:
    text = METRICS.replace(
        'sync_error_count{db="/data/katiu.db"} 0', 'sync_error_count{db="/data/katiu.db"} 3'
    )
    status = admin.backup_status("http://x/metrics", fetch=lambda _url: text)
    assert status.state == admin.BackupState.ERROR
    assert "3 errores" in status.message


def test_copia_sin_respuesta_de_litestream() -> None:
    def boom(_url: str) -> str:
        raise OSError("connection refused")

    status = admin.backup_status("http://x/metrics", fetch=boom)
    assert status.state == admin.BackupState.ERROR


def test_copia_no_configurada() -> None:
    assert admin.backup_status(None).state == admin.BackupState.OFF
