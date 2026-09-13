from tests.conftest import make_plant


def test_pollen_from_male_plant(client):
    strain = client.post("/api/strains", json={"name": "Pollen Strain M"}).json()
    dad = make_plant(client, "Dad", sex="male", strain_id=strain["id"])
    r = client.post("/api/pollen", json={
        "source_plant_id": dad["id"],
        "collected_date": "2026-08-14",
        "amount": "~0.5 g",
        "storage": "freezer, vial #3",
        "notes": "first drop",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source_plant_id"] == dad["id"]
    assert body["source_plant_label"] == "Dad"
    assert body["source_plant_strain_name"] == "Pollen Strain M"
    assert body["collected_date"] == "2026-08-14"
    assert body["amount"] == "~0.5 g"
    assert body["storage"] == "freezer, vial #3"


def test_pollen_from_hermaphrodite_is_allowed(client):
    herm = make_plant(client, "Herm", sex="hermaphrodite")
    r = client.post("/api/pollen", json={"source_plant_id": herm["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["collected_date"]  # defaulted to today


def test_pollen_from_female_or_unknown_is_rejected(client):
    mom = make_plant(client, "Mom", sex="female")
    mystery = make_plant(client, "Mystery")  # unknown
    for pid in (mom["id"], mystery["id"]):
        r = client.post("/api/pollen", json={"source_plant_id": pid})
        assert r.status_code == 400, r.text
        assert "male or hermaphrodite" in r.json()["detail"]


def test_pollen_unknown_plant_is_rejected(client):
    r = client.post("/api/pollen", json={"source_plant_id": 999999})
    assert r.status_code == 400
    assert r.json()["detail"] == "source_plant_id not found"


def test_pollen_list_and_update(client):
    dad = make_plant(client, "Dad2", sex="male")
    created = client.post("/api/pollen", json={"source_plant_id": dad["id"], "amount": "1 vial"}).json()
    ids = [p["id"] for p in client.get("/api/pollen").json()]
    assert created["id"] in ids

    r = client.patch(f"/api/pollen/{created['id']}", json={"amount": "2 vials"})
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == "2 vials"
    assert r.json()["source_plant_id"] == dad["id"]  # untouched


def test_pollen_update_source_must_be_male_or_herm(client):
    dad = make_plant(client, "Dad3", sex="male")
    mom = make_plant(client, "Mom3", sex="female")
    created = client.post("/api/pollen", json={"source_plant_id": dad["id"]}).json()
    r = client.patch(f"/api/pollen/{created['id']}", json={"source_plant_id": mom["id"]})
    assert r.status_code == 400


def test_pollen_delete_unreferenced(client):
    dad = make_plant(client, "Dad4", sex="male")
    created = client.post("/api/pollen", json={"source_plant_id": dad["id"]}).json()
    r = client.delete(f"/api/pollen/{created['id']}")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "id": created["id"]}
    assert created["id"] not in [p["id"] for p in client.get("/api/pollen").json()]


def test_pollen_writes_require_login(anon_client, client):
    dad = make_plant(client, "Dad5", sex="male")
    assert anon_client.post("/api/pollen", json={"source_plant_id": dad["id"]}).status_code == 401
