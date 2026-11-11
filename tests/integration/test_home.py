from fastapi.testclient import TestClient


def test_sin_sesion_redirige_a_entrar(client: TestClient) -> None:
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/entrar"


def test_htmx_sin_sesion_recibe_hx_redirect(client: TestClient) -> None:
    res = client.get("/alumnos", headers={"HX-Request": "true"}, follow_redirects=False)
    assert res.status_code == 401
    assert res.headers["HX-Redirect"] == "/entrar"


def test_salud_responde_ok(client: TestClient) -> None:
    assert client.get("/salud").json() == {"estado": "ok"}


def test_pwa_manifest_y_service_worker(client: TestClient) -> None:
    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    assert manifest.json()["display"] == "standalone"
    assert "serviceWorker" not in client.get("/sw.js").text  # es el propio SW
    assert client.get("/sw.js").headers["content-type"].startswith("text/javascript")


def test_cabeceras_de_seguridad(client: TestClient) -> None:
    res = client.get("/entrar")
    assert "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]
    assert res.headers["X-Content-Type-Options"] == "nosniff"
