def test_health_is_open(anon_client):
    r = anon_client.get("/api/health")
    assert r.status_code == 200


def test_writes_require_login(anon_client, client):
    assert anon_client.post("/api/strains", json={"name": "Nope"}).status_code == 401
    assert client.post("/api/strains", json={"name": "Harness Strain"}).status_code == 200
