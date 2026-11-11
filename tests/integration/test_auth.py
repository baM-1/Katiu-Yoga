from fastapi.testclient import TestClient

from tests.conftest import PASSWORD, csrf_from


def _login(client: TestClient, password: str) -> int:
    token = csrf_from(client.get("/entrar").text)
    res = client.post(
        "/entrar",
        data={"email": "kat@ejemplo.com", "password": password, "csrf_token": token},
        follow_redirects=False,
    )
    return res.status_code


def test_login_correcto_entra(client: TestClient, user: None) -> None:
    assert _login(client, PASSWORD) == 303
    assert client.get("/").status_code == 200


def test_login_incorrecto(client: TestClient, user: None) -> None:
    assert _login(client, "nope") == 401


def test_login_bloquea_tras_5_fallos(client: TestClient, user: None) -> None:
    for _ in range(5):
        assert _login(client, "nope") == 401
    assert _login(client, PASSWORD) == 429  # ni siquiera con la buena: hay que esperar


def test_post_sin_csrf_se_rechaza(client: TestClient, user: None) -> None:
    res = client.post("/entrar", data={"email": "kat@ejemplo.com", "password": PASSWORD})
    assert res.status_code == 403


def test_post_con_sesion_pero_sin_csrf_se_rechaza(logged: TestClient) -> None:
    del logged.headers["X-CSRF-Token"]
    assert logged.post("/alumnos", data={"full_name": "Intrusa"}).status_code == 403


def test_salir(logged: TestClient) -> None:
    assert logged.post("/salir", follow_redirects=False).status_code == 303
    assert logged.get("/", follow_redirects=False).status_code == 303
