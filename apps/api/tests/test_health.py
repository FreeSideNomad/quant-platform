def test_health_returns_ok(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["role"] == "api"


def test_health_includes_version(client) -> None:
    response = client.get("/health")
    assert "version" in response.json()
