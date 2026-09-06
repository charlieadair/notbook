def test_health(client):
    for path in ("/health", "/api/v1/health"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_create_list_get_notebook(client):
    created = client.post("/api/v1/notebooks", json={"title": "Calc II"})
    assert created.status_code == 201
    notebook_id = created.json()["id"]

    listed = client.get("/api/v1/notebooks")
    assert listed.status_code == 200
    assert any(n["id"] == notebook_id for n in listed.json())

    got = client.get(f"/api/v1/notebooks/{notebook_id}")
    assert got.status_code == 200
    assert got.json()["title"] == "Calc II"

    missing = client.get("/api/v1/notebooks/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
