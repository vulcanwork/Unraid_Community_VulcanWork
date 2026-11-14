"""Delete routes for strains, seed batches and breeding events."""
from tests.conftest import make_plant


def strain(client, name):
    r = client.post("/api/strains", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()


def batch(client, strain_id, **extra):
    r = client.post("/api/seeds", json={"strain_id": strain_id, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_unused_strain_deletes(client):
    s = strain(client, "Lonely Strain")
    r = client.delete(f"/api/strains/{s['id']}")
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "id": s["id"]}
    assert client.get(f"/api/strains/{s['id']}").status_code == 404


def test_strain_blocked_lists_seeds_plants_and_children(client):
    s = strain(client, "Blocked Strain")
    batch(client, s["id"], quantity=2)
    make_plant(client, "Direct Plant", strain_id=s["id"])
    client.post("/api/strains", json={"name": "Child Strain", "parent_a_id": s["id"]})

    r = client.delete(f"/api/strains/{s['id']}")
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert d["error"] == "delete_blocked"
    labels = [b["label"] for b in d["blocked_by"]]
    actions = [b["action"] for b in d["blocked_by"]]
    assert actions == ["delete", "unlink", "unlink"]        # deletes first
    assert labels[0].startswith("1 seed batch")
    assert labels[1].startswith("1 plant")
    assert "Direct Plant" in labels[1]
    assert "Child Strain" in labels[2]


def test_strain_blockers_reach_plants_through_the_seed_batch(client):
    """seed_data.py's shape: plants carry seed_id and no strain_id of their own."""
    s = strain(client, "Via Batch Strain")
    b = batch(client, s["id"], quantity=2)
    make_plant(client, "Batch Plant", seed_id=b["id"])

    d = client.delete(f"/api/strains/{s['id']}").json()["detail"]
    plant_entry = [x for x in d["blocked_by"] if "plant" in x["label"]][0]
    assert "Batch Plant" in plant_entry["label"]
    assert plant_entry["action"] == "unlink"


def test_plant_linked_both_ways_is_counted_once(client):
    """Review Focus 3 — direct strain_id and seed_id to the same strain."""
    s = strain(client, "Both Ways Strain")
    b = batch(client, s["id"], quantity=1)
    make_plant(client, "Double Linked", strain_id=s["id"], seed_id=b["id"])

    d = client.delete(f"/api/strains/{s['id']}").json()["detail"]
    plant_entry = [x for x in d["blocked_by"] if "plant" in x["label"]][0]
    assert plant_entry["label"].startswith("1 plant —")
    assert plant_entry["label"].count("Double Linked") == 1


def test_strain_cascade_deletes_batches_and_unlinks_the_rest(client):
    s = strain(client, "Cascade Strain")
    b = batch(client, s["id"], quantity=2)
    p = make_plant(client, "Cascade Plant", seed_id=b["id"])
    child = client.post("/api/strains", json={"name": "Cascade Child", "parent_b_id": s["id"]}).json()

    r = client.delete(f"/api/strains/{s['id']}?cascade=true")
    assert r.status_code == 200, r.text

    assert client.get(f"/api/strains/{s['id']}").status_code == 404
    assert b["id"] not in [x["id"] for x in client.get("/api/seeds").json()]
    after = client.get(f"/api/plants/{p['id']}").json()
    assert after["seed_id"] is None
    assert after["strain_id"] is None          # the strain is going too — nothing to inherit
    assert after["strain_name"] is None
    assert client.get(f"/api/strains/{child['id']}").json()["parent_b_id"] is None


def test_strain_cascade_with_no_blockers_succeeds(client):
    """Review Focus 2 — a stale dialog, or a second tab that already cleared them."""
    s = strain(client, "Already Clear Strain")
    r = client.delete(f"/api/strains/{s['id']}?cascade=true")
    assert r.status_code == 200, r.text


def test_strain_delete_missing_and_anonymous(client, anon_client):
    assert client.delete("/api/strains/999999").status_code == 404
    s = strain(client, "Guarded Strain")
    assert anon_client.delete(f"/api/strains/{s['id']}").status_code == 401


def test_unused_seed_batch_deletes(client):
    s = strain(client, "Seed Delete Strain")
    b = batch(client, s["id"], quantity=3)
    r = client.delete(f"/api/seeds/{b['id']}")
    assert r.status_code == 200, r.text
    assert b["id"] not in [x["id"] for x in client.get("/api/seeds").json()]


def test_seed_blocked_by_its_plants(client):
    s = strain(client, "Planted Batch Strain")
    b = batch(client, s["id"], quantity=2)
    make_plant(client, "Grown From Batch", seed_id=b["id"])

    r = client.delete(f"/api/seeds/{b['id']}")
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert [x["action"] for x in d["blocked_by"]] == ["unlink"]
    assert "Grown From Batch" in d["blocked_by"][0]["label"]


def test_seed_cascade_lets_the_plant_inherit_the_strain(client):
    s = strain(client, "Inherited Strain")
    b = batch(client, s["id"], quantity=2)
    p = make_plant(client, "Inheritor", seed_id=b["id"])
    assert client.get(f"/api/plants/{p['id']}").json()["strain_name"] == "Inherited Strain"

    assert client.delete(f"/api/seeds/{b['id']}?cascade=true").status_code == 200
    after = client.get(f"/api/plants/{p['id']}").json()
    assert after["seed_id"] is None
    assert after["strain_id"] == s["id"]          # inherited, not blanked
    assert after["strain_name"] == "Inherited Strain"


def test_seed_cascade_does_not_overwrite_an_existing_strain(client):
    """Review Focus 4 — the plant's own strain wins over the batch's."""
    own = strain(client, "Plant Own Strain")
    other = strain(client, "Batch Other Strain")
    b = batch(client, other["id"], quantity=1)
    p = make_plant(client, "Keeps Own Strain", strain_id=own["id"], seed_id=b["id"])

    assert client.delete(f"/api/seeds/{b['id']}?cascade=true").status_code == 200
    after = client.get(f"/api/plants/{p['id']}").json()
    assert after["strain_id"] == own["id"]
    assert after["strain_name"] == "Plant Own Strain"


def test_seed_cascade_with_no_blockers_succeeds(client):
    """Review Focus 2."""
    s = strain(client, "Clear Batch Strain")
    b = batch(client, s["id"], quantity=1)
    assert client.delete(f"/api/seeds/{b['id']}?cascade=true").status_code == 200


def test_seed_delete_missing_and_anonymous(client, anon_client):
    assert client.delete("/api/seeds/999999").status_code == 404
    s = strain(client, "Guarded Batch Strain")
    b = batch(client, s["id"], quantity=1)
    assert anon_client.delete(f"/api/seeds/{b['id']}").status_code == 401


def test_strain_cascade_keeps_a_plants_unrelated_strain(client):
    """A plant reached via this strain's batch keeps its own, different strain."""
    doomed = strain(client, "Doomed Strain")
    keeper = strain(client, "Keeper Strain")
    b = batch(client, doomed["id"], quantity=2)
    p = make_plant(client, "Cross Plant", strain_id=keeper["id"], seed_id=b["id"])

    assert client.delete(f"/api/strains/{doomed['id']}?cascade=true").status_code == 200
    after = client.get(f"/api/plants/{p['id']}").json()
    assert after["seed_id"] is None
    assert after["strain_id"] == keeper["id"]


def test_strain_blocker_label_uses_singular_seed(client):
    s = strain(client, "One Seed Strain")
    batch(client, s["id"], quantity=1)
    label = client.delete(f"/api/strains/{s['id']}").json()["detail"]["blocked_by"][0]["label"]
    assert "(1 seed)" in label
    assert "1 seeds" not in label
