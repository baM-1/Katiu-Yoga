from fastapi.testclient import TestClient


def test_home_saluda_a_kat(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Hola Kat 🌊" in response.text


def test_salud_responde_ok(client: TestClient) -> None:
    assert client.get("/salud").json() == {"estado": "ok"}
