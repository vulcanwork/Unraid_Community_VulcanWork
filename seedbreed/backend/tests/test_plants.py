from tests.conftest import make_plant


def test_plant_sex_defaults_to_unknown(client):
    r = client.post("/api/plants", json={"label": "Sexless"})
    assert r.status_code == 200, r.text
    assert r.json()["sex"] == "unknown"


def test_plant_sex_can_be_set_and_updated(client):
    p = make_plant(client, "Him", sex="male")
    assert p["sex"] == "male"
    r = client.patch(f"/api/plants/{p['id']}", json={"sex": "hermaphrodite"})
    assert r.status_code == 200, r.text
    assert r.json()["sex"] == "hermaphrodite"
    assert client.get(f"/api/plants/{p['id']}").json()["sex"] == "hermaphrodite"


def test_plant_sex_rejects_bad_value(client):
    r = client.post("/api/plants", json={"label": "Bad", "sex": "purple"})
    assert r.status_code == 422
