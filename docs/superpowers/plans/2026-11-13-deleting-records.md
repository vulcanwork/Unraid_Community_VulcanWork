# Deleting Records Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give strains, seed batches and breeding events a delete — blocked when other records depend on them, with a "Delete all" escape hatch — and close the one remaining path that can orphan a record.

**Architecture:** Three new `DELETE` routes in the single-file FastAPI app, each taking `?cascade=true`. A blocked delete returns **409** whose `detail` is an object listing what's in the way and whether cascade would delete or unlink it; the existing 400-with-a-sentence blocks are untouched. One new React component renders the button, the confirm and the blocked dialog for all three pages. Two existing routes gain a guard so pollen can never outlive its source plant.

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic 2, SQLite, pytest + httpx, React 18 + Vite.

**Spec:** `docs/superpowers/specs/2026-11-13-deleting-records-design.md`

## Global Constraints

- Branch is `record-deletes`, already created, already holding the spec. Repo root `E:\johnv\source\repos\Unraid_Community_VulcanWork`; the app is under `seedbreed/`.
- **No schema change, so no migration.** `models.py` is read in this work, never edited.
- Blocked-delete response is **409**, `detail` an object: `{"error": "delete_blocked", "message": str, "blocked_by": [{"label": str, "action": "delete"|"unlink"}]}`. `blocked_by` is ordered deletes-first, then unlinks.
- `label` is a finished phrase built by the backend: count, noun, em-dash, up to **3** names, then `and N more`. The UI prints it verbatim.
- The two new pollen guards on `delete_plant` / `delete_grow` keep the existing `HTTPException(400, "<sentence>")` style and get **no** cascade option.
- Successful deletes return `{"ok": True, "id": N}`; missing target returns 404. Matches every existing delete.
- Writes are gated by the existing auth middleware; no per-route auth code. It matches on `request.url.path`, so `?cascade=true` passes through.
- `main.py` stays one file (house style). `models.py`, `schemas.py` and `database.py` are not touched by any task.
- Run tests from `seedbreed/backend/` with `./.venv/Scripts/python -m pytest`. **27 pass today.** Known-acceptable warnings: StarletteDeprecationWarning (httpx), anyio BlockingPortal, sqlalchemy utcnow. Anything else is a finding.
- No Node locally; frontend tasks are verified by review, then by the container build in Task 6.
- Commit subjects are sentence case, matching the repo (`Add pollen collections API`), not conventional-commits. Every commit ends with:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`

## Review Focus

Five things the spec implies that would otherwise ship untested. Each has a test pinned to the task that owns the code.

1. **A non-JSON error body must not crash `api.js`.** nginx returns HTML on 502/504; a bare `JSON.parse` in the error path would throw and replace a readable failure with a parser exception. (Task 5)
2. **`?cascade=true` on a record with no blockers must simply delete it.** The dialog's counts are a snapshot; by the time the user clicks "Delete all" another tab may have cleared them. (Tasks 1–3)
3. **A plant linked to a strain both directly and through its seed batch must be counted once.** Two queries feed one `blocked_by` entry; the naive union double-counts and the dialog lies. (Task 1)
4. **A plant that already has its own `strain_id` must not have it overwritten** when it inherits from a seed batch being deleted. (Task 2)
5. **The pollen guard must not block deletes that work today.** A plant with no pollen, and a grow whose plants have none, must still delete exactly as before. (Task 4)

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `seedbreed/backend/app/main.py` | modify | the three delete routes, the blocker helpers, the two pollen guards |
| `seedbreed/backend/tests/test_deletes.py` | create | every backend test in this plan |
| `seedbreed/frontend/src/api.js` | modify | parse JSON error bodies; expose `err.detail` |
| `seedbreed/frontend/src/components/DeleteButton.jsx` | create | button + confirm + blocked dialog, used by all three pages |
| `seedbreed/frontend/src/pages/Strains.jsx` | modify | one `<DeleteButton>` in the row actions |
| `seedbreed/frontend/src/pages/Seeds.jsx` | modify | one `<DeleteButton>` in the row actions |
| `seedbreed/frontend/src/pages/Breeding.jsx` | modify | one `<DeleteButton>` on seed-production rows |
| `seedbreed/README.md` | modify | a short "Deleting things" section |

---

### Task 1: Blocker helpers and strain delete

**Files:**
- Modify: `seedbreed/backend/app/main.py` — helpers in a new `# ============ Deletes ============` section placed immediately before `# ============ Strains ============` (line 89); the route itself at the end of the Strains section, after `get_lineage` (ends line ~154)
- Test: `seedbreed/backend/tests/test_deletes.py` (create)

**Interfaces:**
- Consumes: `models.Strain`, `models.Seed`, `models.Plant`; `conftest.make_plant(client, label, sex="unknown", **extra)`.
- Produces, for Tasks 2–4:
  - `_blocker(names: List[str], singular: str, plural: str, action: str) -> dict` — one `blocked_by` entry. `action` is `"delete"` or `"unlink"`. Builds the label as `"<n> <noun> — <up to 3 names> and <k> more"`, dropping the `and k more` when everything fits and the em-dash clause when `names` is empty.
  - `_raise_blocked(message: str, blockers: List[dict]) -> NoReturn` — raises `HTTPException(409, {"error": "delete_blocked", "message": message, "blocked_by": blockers})`.
  - `_strain_dependents(db: Session, strain_id: int) -> Tuple[List[models.Seed], List[models.Plant], List[models.Strain]]` — seed batches of the strain; plants linked to the strain directly **or** to any of those batches, **deduplicated by plant id**; strains naming it as `parent_a_id` or `parent_b_id`.

- [ ] **Step 1: Write the failing tests**

In `seedbreed/backend/tests/test_deletes.py`. Import `make_plant` from `tests.conftest`, matching the other test modules. Add a module-level helper `strain(client, name)` that POSTs `/api/strains` and returns the JSON, and `batch(client, strain_id, **extra)` that POSTs `/api/seeds`.

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest tests/test_deletes.py -v`
Expected: FAIL — 405 Method Not Allowed, since `/api/strains/{id}` has no DELETE.

- [ ] **Step 3: Implement the three helpers in `main.py`**

`_blocker`, `_raise_blocked` and `_strain_dependents`, signatures exactly as in Interfaces above, under a new `# ============ Deletes ============` banner before the Strains section.

For `_strain_dependents`, build the plant list from one query with an `or_` over `Plant.strain_id == strain_id` and `Plant.seed_id.in_(batch_ids)` so the database does the deduplication; guard the `in_` against an empty `batch_ids`.

- [ ] **Step 4: Implement `delete_strain(strain_id: int, cascade: bool = False, db: Session = Depends(get_db))` in `main.py`**

Route `@app.delete("/api/strains/{strain_id}")`, no `response_model`, placed after `get_lineage`.

404 when missing. Gather dependents; when any exist and not `cascade`, `_raise_blocked` with message `"Other records use this strain."` and blockers in order: seed batches (`"seed batch"`/`"seed batches"`, action `delete`, named by their strain's name plus `f"({q} seeds)"` when `quantity` is set), plants (`"plant"`/`"plants"`, `unlink`, named by `label`), child strains (`"child strain"`/`"child strains"`, `unlink`, named by `name`). When `cascade`: delete the batches, clear `seed_id` and `strain_id` on the plants, null whichever parent column points at this strain on each child, delete the strain, commit.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest tests/test_deletes.py -v`
Expected: 7 passed.

- [ ] **Step 6: Run the full suite**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest -q`
Expected: 34 passed.

- [ ] **Step 7: Commit**

```bash
git add seedbreed/backend/app/main.py seedbreed/backend/tests/test_deletes.py
git commit -m "Add strain delete with blocker reporting and cascade

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Seed batch delete

**Files:**
- Modify: `seedbreed/backend/app/main.py` — route at the end of the Seeds section, after `update_seed` (ends line ~199)
- Test: `seedbreed/backend/tests/test_deletes.py` (append)

**Interfaces:**
- Consumes: `_blocker`, `_raise_blocked` (Task 1).
- Produces, for Task 3: `_unlink_plants_from_seed(seed: models.Seed, plants: List[models.Plant]) -> None` — clears each plant's `seed_id`, and copies `seed.strain_id` onto `plant.strain_id` **only** when the plant has none of its own. Callers that are also deleting that strain must clear `strain_id` themselves afterwards.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest tests/test_deletes.py -v -k seed`
Expected: FAIL — 405, no DELETE on `/api/seeds/{id}`.

- [ ] **Step 3: Implement `_unlink_plants_from_seed` and `delete_seed(seed_id: int, cascade: bool = False, db: Session = Depends(get_db))`**

Helper goes in the Deletes section beside Task 1's; route is `@app.delete("/api/seeds/{seed_id}")` at the end of the Seeds section.

404 when missing. Blockers: plants with `seed_id == seed_id` (`"plant"`/`"plants"`, `unlink`, named by `label`); message `"Plants were grown from this seed batch."` Cascade calls `_unlink_plants_from_seed`, deletes the batch, commits.

- [ ] **Step 4: Go back and use the helper in Task 1's strain cascade**

`delete_strain`'s cascade now calls `_unlink_plants_from_seed` for each batch, then clears `strain_id` on every affected plant — the strain is being deleted, so nothing inherits it. `test_strain_cascade_deletes_batches_and_unlinks_the_rest` already asserts `strain_id is None` and must still pass.

- [ ] **Step 5: Run the full suite**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest -q`
Expected: 40 passed.

- [ ] **Step 6: Commit**

```bash
git add seedbreed/backend/app/main.py seedbreed/backend/tests/test_deletes.py
git commit -m "Add seed batch delete, inheriting the strain on unlink

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Breeding event delete

**Files:**
- Modify: `seedbreed/backend/app/main.py` — route at the end of the Seed Production section, after `update_seed_production` (ends line ~866)
- Test: `seedbreed/backend/tests/test_deletes.py` (append)

**Interfaces:**
- Consumes: `_blocker`, `_raise_blocked` (Task 1); `_unlink_plants_from_seed` (Task 2).
- Produces: nothing later tasks call.

Behaviour, from the spec: the seed batch a named cross auto-creates exists only because the event does, so a plain delete takes it. Once plants have been grown from that batch it is real data, and the event blocks instead. The strain the event auto-created is never deleted.

- [ ] **Step 1: Write the failing tests**

Add a module-level helper `cross(client, tag)` that builds a female mother, a male father, a pollen record and returns `(mom, dad, pollen)` — the same shape as `_cross_setup` in `tests/test_seed_production.py`; copy it rather than importing across test modules.

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest tests/test_deletes.py -v -k cross`
Expected: FAIL — 405.

- [ ] **Step 3: Implement `delete_seed_production(event_id: int, cascade: bool = False, db: Session = Depends(get_db))`**

Route `@app.delete("/api/seed-production/{event_id}")` at the end of the Seed Production section.

404 when missing. Find the produced batches (`Seed.produced_by_event_id == event_id`) and the plants using them. **No plants** → delete the batches and the event regardless of `cascade`. **Plants exist and not `cascade`** → `_raise_blocked`, message `"Plants were grown from the seeds this cross produced."`, blockers: the batches (`delete`) then the plants (`unlink`). **Plants exist and `cascade`** → `_unlink_plants_from_seed` per batch (the batch's strain survives, so the inheritance applies), delete the batches, delete the event. Never touch the strain named by `new_strain_name`.

- [ ] **Step 4: Run the full suite**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest -q`
Expected: 46 passed.

- [ ] **Step 5: Commit**

```bash
git add seedbreed/backend/app/main.py seedbreed/backend/tests/test_deletes.py
git commit -m "Add breeding event delete, taking its unplanted seed batch

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Pollen guard on plant and grow delete

**Files:**
- Modify: `seedbreed/backend/app/main.py` — `delete_plant` (line 395, guard beside the existing `SeedProductionEvent` check at ~400-409) and `delete_grow` (line 242, guard beside the existing check at ~255-270)
- Test: `seedbreed/backend/tests/test_deletes.py` (append)

**Interfaces:**
- Consumes: `models.PollenCollection`.
- Produces: nothing. Both guards raise the existing `HTTPException(400, "<sentence>")` style, not 409 — there is no cascade here by design.

- [ ] **Step 1: Write the failing tests**

```python
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
    """cross -> pollen -> plant -> grow, each step blocked until the one before."""
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
    assert client.delete(f"/api/pollen/{po['id']}").status_code == 200
    assert client.delete(f"/api/plants/{dad['id']}").status_code == 200
    assert client.delete(f"/api/grows/{grow['id']}").status_code == 200
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest tests/test_deletes.py -v -k "pollen or chain"`
Expected: the two guard tests and the chain test FAIL — the deletes currently return 200 where 400 is expected.

- [ ] **Step 3: Add the guard to `delete_plant`**

Beside the existing breeding-parent check: refuse when any `PollenCollection.source_plant_id` is this plant, with a sentence matching the house voice — *"Can't delete this plant: pollen was collected from it. Delete those pollen records first."*

- [ ] **Step 4: Add the guard to `delete_grow`**

Beside the existing breeding-parent check, reusing the `plant_ids` list already computed there: refuse when any pollen record's `source_plant_id` is in it — *"Can't delete this grow: pollen was collected from one of its plants. Delete those pollen records first."*

- [ ] **Step 5: Run the full suite**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest -q`
Expected: 50 passed. The pre-existing plant and grow delete tests must pass unchanged — that is the real check that the guard didn't overreach.

- [ ] **Step 6: Commit**

```bash
git add seedbreed/backend/app/main.py seedbreed/backend/tests/test_deletes.py
git commit -m "Block deleting a plant or grow that pollen was collected from

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Frontend — error parsing, DeleteButton, and the three pages

**Files:**
- Modify: `seedbreed/frontend/src/api.js` — the `if (!r.ok)` block, lines 28-45
- Create: `seedbreed/frontend/src/components/DeleteButton.jsx`
- Modify: `seedbreed/frontend/src/pages/Strains.jsx` — row actions, line 43-46
- Modify: `seedbreed/frontend/src/pages/Seeds.jsx` — row actions, line 50-53
- Modify: `seedbreed/frontend/src/pages/Breeding.jsx` — seed-production row actions, line 140-142
- Modify: `seedbreed/README.md`

**Interfaces:**
- Consumes: the 409 `detail` shape from Tasks 1-3.
- Produces: `<DeleteButton path label confirmText? onDeleted />` — default export of `components/DeleteButton.jsx`. `path` is the DELETE path without a query string (`/api/strains/5`); `label` names the record in the default confirm and the dialog title; `confirmText` overrides the confirm sentence; `onDeleted` is called after a successful delete.

There is no JS test runner in this project, so this task is verified by reading and by Task 6's container build. Keep each change small enough to check by eye.

- [ ] **Step 1: Make `api.js` parse JSON error bodies**

In the `if (!r.ok)` block, after the existing 401 branch, read the body once as text and attempt `JSON.parse` **inside a try/catch** — Review Focus 1: nginx serves HTML on 502/504 and an unguarded parse would throw from the error handler and hide the real failure. Then:

- parsed `detail` is an object → `err.detail = detail`, and `err.message` stays the current `` `${r.status} ${r.statusText}: ${text}` `` form;
- parsed `detail` is a string → `err.message = detail` (this is the free fix: existing blocks stop reaching the user as raw JSON);
- body is not JSON, or has no `detail` → exactly today's behaviour.

`err.status` keeps being set in every branch.

- [ ] **Step 2: Write `components/DeleteButton.jsx`**

Default export with the signature in Interfaces. Behaviour:

1. Renders `<button className="small-btn danger">Delete</button>`.
2. On click, `confirm(confirmText || `Delete "${label}"?`)`; bail if declined.
3. `api.del(path)`; on success call `onDeleted()`.
4. On an error whose `detail.error === 'delete_blocked'`, store `detail` in state to open the dialog; any other error is `alert(e.message)`.
5. The dialog uses the existing `.modal-backdrop`, `.modal` and `.modal-actions` classes — no new CSS. Title `Can't delete "{label}"`, then `detail.message`, then one row per `blocked_by` entry showing `label` and, on the right in `.muted .small`, `will be deleted` or `will be unlinked` from `action`. Actions are `Cancel` and a `primary` **Delete all**.
6. **Delete all** calls `api.del(`${path}?cascade=true`)`, then `onDeleted()`; failures `alert(e.message)`. Disable both buttons while a request is in flight, matching the `busy` pattern the other modals use.

- [ ] **Step 3: Wire it into the three pages**

- `Strains.jsx`: `<DeleteButton path={`/api/strains/${s.id}`} label={s.name} onDeleted={load} />` after the Edit button. `load` already exists.
- `Seeds.jsx`: same shape, `path={`/api/seeds/${s.id}`}`, `label={s.strain_name || `Strain #${s.strain_id}`}`, `onDeleted={load}`.
- `Breeding.jsx`: on the seed-production rows only, `path={`/api/seed-production/${e.id}`}`, `label` built from the parents the row already renders (`e.parent_b_label ? `${e.parent_a_label} × ${e.parent_b_label}` : e.parent_a_label`), and `confirmText="Delete this cross? The seed batch it created goes with it."` — the spec's wording. `onDeleted={load}`. The pollen rows keep their existing `deletePollen` handler untouched.

- [ ] **Step 4: Re-read each changed file top to bottom**

Check: balanced JSX; every identifier imported or defined; no bare ASCII apostrophe inside a single-quoted JS string (this bit the last branch); `DeleteButton` imported in all three pages.

- [ ] **Step 5: Add a "Deleting things" section to `seedbreed/README.md`**

After the "What's in here" list. Four or five lines: anything can be deleted from the page that lists it; a record other records depend on is refused with a list of what's in the way and an option to take them with it; pollen, plants and grows must be unwound by hand in the order cross → pollen → plant → grow; and the example data a fresh install seeds can now be cleared entirely.

- [ ] **Step 6: Commit**

```bash
git add seedbreed/frontend/src/api.js seedbreed/frontend/src/components/DeleteButton.jsx seedbreed/frontend/src/pages/Strains.jsx seedbreed/frontend/src/pages/Seeds.jsx seedbreed/frontend/src/pages/Breeding.jsx seedbreed/README.md
git commit -m "Add delete buttons for strains, seeds and crosses

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: End-to-end verification

**Files:** none — verification only.

- [ ] **Step 1: Full backend suite**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest -q`
Expected: 50 passed, no warnings beyond the three known-acceptable ones.

- [ ] **Step 2: Build and start the container on a fresh database**

A fresh DB is the point — it gives the example data this work exists to clear. From `seedbreed/`, with a scratch directory for `/data` and `/photos` so nothing real is touched:

```bash
docker compose -p seedbreed-del -f docker-compose.yml -f <scratch>/compose.override.yml up -d --build
```

The override sets `container_name: seedbreed-del`, port `8089:80`, and binds both volumes into the scratch directory. A JSX error in Task 5 fails the build here.

- [ ] **Step 3: Clear the example data through the UI**

At `http://localhost:8089`, logged in: delete the example grow (works today), then both example seed batches, then both example strains — each one hitting the blocked dialog and its "Delete all" at least once. Confirm Strains, Seeds and Grows all end up empty.

- [ ] **Step 4: Check the guard and the dialog**

Mark a plant male, log pollen from it, then try to delete that plant and its grow — both refused, and the message reads as a sentence rather than raw JSON (the Task 5 `api.js` fix). Log a cross using that pollen, delete the cross, then the pollen, then the plant, then the grow, in that order.

- [ ] **Step 5: Tear down**

```bash
cd seedbreed && docker compose -p seedbreed-del -f docker-compose.yml -f <scratch>/compose.override.yml down
```

Delete the scratch directory. Report anything that behaved differently from the plan rather than fixing it silently.

---

## Self-review notes

- **Spec coverage:** three deletes (T1-3), 409 shape and label format (T1, used by all), two-level blockers (T1), inheritance rule (T2, reused T3), cross rule (T3), pollen guard (T4), `api.js` and the dialog (T5), README (T5), the spec's six called-out test cases (T1 ×2, T2 ×2, T3 ×2) plus the pollen and chain cases (T4). ✔
- **Type consistency:** `_blocker`, `_raise_blocked`, `_strain_dependents`, `_unlink_plants_from_seed`, and `<DeleteButton path label confirmText onDeleted />` are spelled identically everywhere they appear. ✔
- **Review Focus:** all five have a test — 1 in T5 Step 1, 2 in T1 and T2, 3 in T1, 4 in T2, 5 in T4. ✔
- **Known wrinkle for the executor:** Task 2 Step 4 revisits code Task 1 wrote. That is deliberate — the inheritance helper only becomes definable once the seed route needs it, and Task 1's own tests pin the strain-cascade behaviour so the refactor can't drift.
