from app.main import APP_VERSION


def test_health_is_open(anon_client):
    r = anon_client.get("/api/health")
    assert r.status_code == 200


def test_writes_require_login(anon_client, client):
    assert anon_client.post("/api/strains", json={"name": "Nope"}).status_code == 401
    assert client.post("/api/strains", json={"name": "Harness Strain"}).status_code == 200


def test_version_is_open_and_matches_the_app(anon_client):
    r = anon_client.get("/api/version")
    assert r.status_code == 200
    assert r.json() == {"version": APP_VERSION}


def test_openapi_is_served_under_the_api_prefix(anon_client):
    # nginx only proxies /api/, so the schema must answer there or the docs
    # are unreachable in the shipped container.
    r = anon_client.get("/api/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["version"] == APP_VERSION
