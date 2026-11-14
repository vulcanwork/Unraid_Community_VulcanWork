"""Delete routes for strains, seed batches and breeding events."""
from tests.conftest import make_plant


def cross(client, tag):
    """A female mother, a male father with one pollen record. Returns (mom, dad, pollen)."""
    mom_strain = client.post("/api/strains", json={"name": f"Mom Strain {tag}"}).json()
    dad_strain = client.post("/api/strains", json={"name": f"Dad Strain {tag}"}).json()
    mom = make_plant(client, f"Mom {tag}", sex="female", strain_id=mom_strain["id"])
    dad = make_plant(client, f"Dad {tag}", sex="male", strain_id=dad_strain["id"])
    pollen = client.post("/api/pollen", json={
        "source_plant_id": dad["id"], "collected_date": "2026-08-14",
    }).json()
    return mom, dad, pollen


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
    assert labels[0] == "1 seed batch — Blocked Strain (2 seeds)"
    assert labels[1].startswith("1 plant")
    assert "Direct Plant" in labels[1]
    assert "Child Strain" in labels[2]


def test_strain_blocker_truncates_to_three_names(client):
    s = strain(client, "Crowded Strain")
    for i in range(1, 5):
        make_plant(client, f"Crowd Plant {i}", strain_id=s["id"])

    d = client.delete(f"/api/strains/{s['id']}").json()["detail"]
    label = [x for x in d["blocked_by"] if "plant" in x["label"]][0]["label"]
    assert label.startswith("4 plants")
    assert label.endswith("and 1 more")
    assert sum(f"Crowd Plant {i}" in label for i in range(1, 5)) == 3


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
    grow = client.post("/api/grows", json={
        "name": "Cascade Grow", "groups": [{"name": "G1"}],
    }).json()
    p = make_plant(client, "Cascade Plant", seed_id=b["id"],
                   grow_id=grow["id"], group_id=grow["groups"][0]["id"])
    ci = client.post("/api/checkins", json={
        "grow_id": grow["id"], "plant_id": p["id"], "notes": "Cascade check-in",
    }).json()
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
    # the grow, its plant and its check-in are untouched
    assert client.get(f"/api/grows/{grow['id']}").status_code == 200
    assert client.get(f"/api/plants/{p['id']}").status_code == 200
    assert ci["id"] in [c["id"] for c in client.get(f"/api/checkins?grow_id={grow['id']}").json()]


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


def test_cross_with_unplanted_seeds_deletes_in_one_call(client):
    mom, dad, pollen = cross(client, "D1")
    ev = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"], "pollen_collection_id": pollen["id"],
        "event_type": "intentional_cross", "new_strain_name": "Unplanted Cross",
    }).json()
    produced = [s for s in client.get("/api/seeds").json()
                if s["produced_by_event_id"] == ev["id"]]
    assert len(produced) == 1

    r = client.delete(f"/api/seed-production/{ev['id']}")
    assert r.status_code == 200, r.text
    assert ev["id"] not in [e["id"] for e in client.get("/api/seed-production").json()]
    assert produced[0]["id"] not in [s["id"] for s in client.get("/api/seeds").json()]
    # the named strain survives on its own
    assert "Unplanted Cross" in [s["name"] for s in client.get("/api/strains").json()]


def test_cross_with_planted_seeds_is_blocked(client):
    mom, dad, pollen = cross(client, "D2")
    ev = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"], "pollen_collection_id": pollen["id"],
        "event_type": "intentional_cross", "new_strain_name": "Planted Cross",
    }).json()
    produced = [s for s in client.get("/api/seeds").json()
                if s["produced_by_event_id"] == ev["id"]][0]
    make_plant(client, "Child Of Cross", seed_id=produced["id"])

    r = client.delete(f"/api/seed-production/{ev['id']}")
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert [x["action"] for x in d["blocked_by"]] == ["delete", "unlink"]
    assert "Child Of Cross" in d["blocked_by"][1]["label"]


def test_cross_cascade_unlinks_the_plant_and_keeps_the_strain(client):
    mom, dad, pollen = cross(client, "D3")
    ev = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"], "pollen_collection_id": pollen["id"],
        "event_type": "intentional_cross", "new_strain_name": "Cascade Cross",
    }).json()
    produced = [s for s in client.get("/api/seeds").json()
                if s["produced_by_event_id"] == ev["id"]][0]
    p = make_plant(client, "Survivor Of Cross", seed_id=produced["id"])

    assert client.delete(f"/api/seed-production/{ev['id']}?cascade=true").status_code == 200
    after = client.get(f"/api/plants/{p['id']}").json()
    assert after["seed_id"] is None
    assert after["strain_name"] == "Cascade Cross"     # inherited from the batch
    assert "Cascade Cross" in [s["name"] for s in client.get("/api/strains").json()]


def test_unnamed_cross_deletes_with_no_produced_batch(client):
    mom, dad, pollen = cross(client, "D4")
    ev = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"], "pollen_collection_id": pollen["id"],
        "event_type": "intentional_cross",
    }).json()
    assert client.delete(f"/api/seed-production/{ev['id']}").status_code == 200


def test_deleting_a_cross_frees_its_pollen(client):
    """The block on pollen delete is what made events need deleting."""
    mom, dad, pollen = cross(client, "D5")
    ev = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"], "pollen_collection_id": pollen["id"],
        "event_type": "intentional_cross",
    }).json()
    assert client.delete(f"/api/pollen/{pollen['id']}").status_code == 400
    assert client.delete(f"/api/seed-production/{ev['id']}").status_code == 200
    assert client.delete(f"/api/pollen/{pollen['id']}").status_code == 200


def test_cross_delete_missing_and_anonymous(client, anon_client):
    assert client.delete("/api/seed-production/999999").status_code == 404
    mom, dad, pollen = cross(client, "D6")
    ev = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"], "pollen_collection_id": pollen["id"],
        "event_type": "intentional_cross",
    }).json()
    assert anon_client.delete(f"/api/seed-production/{ev['id']}").status_code == 401


def test_cross_cascade_with_no_blockers_succeeds(client):
    """Review Focus 2."""
    mom, dad, pollen = cross(client, "D7")
    ev = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"], "pollen_collection_id": pollen["id"],
        "event_type": "intentional_cross", "new_strain_name": "Idle Cascade Cross",
    }).json()
    produced = [s for s in client.get("/api/seeds").json()
                if s["produced_by_event_id"] == ev["id"]]
    assert len(produced) == 1

    r = client.delete(f"/api/seed-production/{ev['id']}?cascade=true")
    assert r.status_code == 200, r.text
    assert ev["id"] not in [e["id"] for e in client.get("/api/seed-production").json()]
    assert produced[0]["id"] not in [x["id"] for x in client.get("/api/seeds").json()]


def test_plant_with_pollen_cannot_be_deleted(client):
    dad = make_plant(client, "Pollen Donor Plant", sex="male")
    po = client.post("/api/pollen", json={"source_plant_id": dad["id"]}).json()

    r = client.delete(f"/api/plants/{dad['id']}")
    assert r.status_code == 400, r.text
    assert "pollen" in r.json()["detail"].lower()

    assert client.delete(f"/api/pollen/{po['id']}").status_code == 200
    assert client.delete(f"/api/plants/{dad['id']}").status_code == 200


def test_grow_with_pollen_on_a_plant_cannot_be_deleted(client):
    grow = client.post("/api/grows", json={
        "name": "Pollen Guard Grow", "groups": [{"name": "G1"}],
    }).json()
    dad = make_plant(client, "In Grow Donor", sex="male",
                     grow_id=grow["id"], group_id=grow["groups"][0]["id"])
    po = client.post("/api/pollen", json={"source_plant_id": dad["id"]}).json()

    r = client.delete(f"/api/grows/{grow['id']}")
    assert r.status_code == 400, r.text
    assert "pollen" in r.json()["detail"].lower()

    assert client.delete(f"/api/pollen/{po['id']}").status_code == 200
    assert client.delete(f"/api/grows/{grow['id']}").status_code == 200


def test_plants_and_grows_without_pollen_still_delete(client):
    """Review Focus 5 — the guard must not catch what works today."""
    p = make_plant(client, "No Pollen Plant")
    assert client.delete(f"/api/plants/{p['id']}").status_code == 200

    grow = client.post("/api/grows", json={
        "name": "No Pollen Grow", "groups": [{"name": "G1"}],
    }).json()
    make_plant(client, "Ordinary Plant", grow_id=grow["id"],
               group_id=grow["groups"][0]["id"])
    assert client.delete(f"/api/grows/{grow['id']}").status_code == 200


def test_the_whole_chain_unwinds_in_order(client):
    """Unwind cross -> pollen -> plant -> grow in order.

    First the cross blocks all three deletes. Then, with the cross gone but the
    pollen still there, the pollen guards on plant and grow are the only thing
    stopping those two deletes. Only then does the rest unwind.
    """
    grow = client.post("/api/grows", json={
        "name": "Chain Grow", "groups": [{"name": "G1"}],
    }).json()
    gid = grow["groups"][0]["id"]
    mom = make_plant(client, "Chain Mom", sex="female", grow_id=grow["id"], group_id=gid)
    dad = make_plant(client, "Chain Dad", sex="male", grow_id=grow["id"], group_id=gid)
    po = client.post("/api/pollen", json={"source_plant_id": dad["id"]}).json()
    ev = client.post("/api/seed-production", json={
        "parent_a_plant_id": mom["id"], "pollen_collection_id": po["id"],
        "event_type": "intentional_cross",
    }).json()

    assert client.delete(f"/api/grows/{grow['id']}").status_code == 400
    assert client.delete(f"/api/plants/{dad['id']}").status_code == 400
    assert client.delete(f"/api/pollen/{po['id']}").status_code == 400

    assert client.delete(f"/api/seed-production/{ev['id']}").status_code == 200

    # Cross gone, pollen still present: only the new pollen guards can fire here.
    assert client.delete(f"/api/plants/{dad['id']}").status_code == 400
    assert client.delete(f"/api/grows/{grow['id']}").status_code == 400

    assert client.delete(f"/api/pollen/{po['id']}").status_code == 200
    assert client.delete(f"/api/plants/{dad['id']}").status_code == 200
    assert client.delete(f"/api/grows/{grow['id']}").status_code == 200
