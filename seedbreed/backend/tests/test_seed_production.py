from tests.conftest import make_plant


def _cross_setup(client, tag):
    """A female mother, a male father with one pollen record. Returns (mom, dad, pollen)."""
    mom_strain = client.post("/api/strains", json={"name": f"Mom Strain {tag}"}).json()
    dad_strain = client.post("/api/strains", json={"name": f"Dad Strain {tag}"}).json()
    mom = make_plant(client, f"Mom {tag}", sex="female", strain_id=mom_strain["id"])
    dad = make_plant(client, f"Dad {tag}", sex="male", strain_id=dad_strain["id"])
    pollen = client.post("/api/pollen", json={
        "source_plant_id": dad["id"], "collected_date": "2026-08-14",
    }).json()
    return mom, dad, pollen


def test_event_with_pollen_derives_parent_b(client):
    mom, dad, pollen = _cross_setup(client, "A")
    r = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"],
        "pollen_collection_id": pollen["id"],
        "event_type": "intentional_cross",
        "seed_count": 12,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pollen_collection_id"] == pollen["id"]
    assert body["parent_b_plant_id"] == dad["id"]
    assert body["parent_b_label"] == "Dad A"
    assert body["pollen_label"] == "Dad A · 2026-08-14"


def test_event_without_pollen_has_no_parent_b(client):
    mom, _, _ = _cross_setup(client, "B")
    r = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"],
        "event_type": "hermaphrodite",
    })
    assert r.status_code == 200, r.text
    assert r.json()["parent_b_plant_id"] is None
    assert r.json()["pollen_collection_id"] is None
    assert r.json()["pollen_label"] is None


def test_parent_b_plant_id_is_ignored_as_input(client):
    """The manual Parent B picker is gone — clients can't set it directly."""
    mom, dad, _ = _cross_setup(client, "C")
    r = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"],
        "parent_b_plant_id": dad["id"],
        "event_type": "intentional_cross",
    })
    assert r.status_code == 200, r.text
    assert r.json()["parent_b_plant_id"] is None


def test_unknown_pollen_is_rejected(client):
    mom, _, _ = _cross_setup(client, "D")
    r = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"],
        "pollen_collection_id": 999999,
        "event_type": "intentional_cross",
    })
    assert r.status_code == 400
    assert r.json()["detail"] == "pollen_collection_id not found"


def test_named_cross_links_both_parent_strains_via_pollen(client):
    mom, dad, pollen = _cross_setup(client, "E")
    r = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"],
        "pollen_collection_id": pollen["id"],
        "event_type": "intentional_cross",
        "new_strain_name": "Cross E",
    })
    assert r.status_code == 200, r.text
    strains = {s["name"]: s for s in client.get("/api/strains").json()}
    new = strains["Cross E"]
    assert new["parent_a_id"] == strains["Mom Strain E"]["id"]
    assert new["parent_b_id"] == strains["Dad Strain E"]["id"]


def test_update_pollen_rederives_parent_b(client):
    mom, dad, pollen = _cross_setup(client, "F")
    dad2 = make_plant(client, "Dad F2", sex="male")
    pollen2 = client.post("/api/pollen", json={"source_plant_id": dad2["id"]}).json()
    ev = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"],
        "pollen_collection_id": pollen["id"],
        "event_type": "intentional_cross",
    }).json()

    r = client.patch(f"/api/seed-production/{ev['id']}", json={"pollen_collection_id": pollen2["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["parent_b_plant_id"] == dad2["id"]

    r = client.patch(f"/api/seed-production/{ev['id']}", json={"pollen_collection_id": None})
    assert r.status_code == 200, r.text
    assert r.json()["parent_b_plant_id"] is None
    assert r.json()["pollen_collection_id"] is None


def test_update_without_pollen_key_leaves_parent_b_alone(client):
    mom, dad, pollen = _cross_setup(client, "G")
    ev = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"],
        "pollen_collection_id": pollen["id"],
        "event_type": "intentional_cross",
    }).json()
    r = client.patch(f"/api/seed-production/{ev['id']}", json={"seed_count": 40})
    assert r.status_code == 200, r.text
    assert r.json()["seed_count"] == 40
    assert r.json()["parent_b_plant_id"] == dad["id"]
    assert r.json()["pollen_collection_id"] == pollen["id"]


def test_repointing_pollen_rederives_parent_b_on_events(client):
    mom, dad, pollen = _cross_setup(client, "I")
    ev = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"],
        "pollen_collection_id": pollen["id"],
        "event_type": "intentional_cross",
    }).json()
    assert ev["parent_b_plant_id"] == dad["id"]

    dad2 = make_plant(client, "Dad I2", sex="male")
    r = client.patch(f"/api/pollen/{pollen['id']}", json={"source_plant_id": dad2["id"]})
    assert r.status_code == 200, r.text

    events = {e["id"]: e for e in client.get("/api/seed-production").json()}
    assert events[ev["id"]]["parent_b_plant_id"] == dad2["id"]
    assert events[ev["id"]]["parent_b_label"] == "Dad I2"
    assert events[ev["id"]]["pollen_label"].startswith("Dad I2 · ")


def test_pollen_referenced_by_event_cannot_be_deleted(client):
    mom, dad, pollen = _cross_setup(client, "H")
    client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"],
        "pollen_collection_id": pollen["id"],
        "event_type": "intentional_cross",
    })
    r = client.delete(f"/api/pollen/{pollen['id']}")
    assert r.status_code == 400
    assert "seed-production event uses it" in r.json()["detail"]
