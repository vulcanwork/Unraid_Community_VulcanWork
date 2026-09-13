# Pollen Tracking & Plant Sex Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `sex` field to plants, a pollen-collection log (one row per collection from a male/hermaphrodite plant), and link each seed-production event to the pollen record that fathered it.

**Architecture:** SeedBreed is a FastAPI + SQLAlchemy + SQLite backend (`seedbreed/backend/app/`, single-file API in `main.py`) with a React/Vite frontend (`seedbreed/frontend/src/`). New columns land via the existing hand-rolled `run_lightweight_migrations()` in `database.py`; new tables come from `create_all()`. The Breeding page gains a Pollen library section above the existing Seed production list, and the seed-production form's manual Parent B picker is replaced by a "Pollen used" dropdown from which Parent B is derived server-side.

**Tech Stack:** Python 3.12 in the container (local dev here is 3.14 — see Global Constraints), FastAPI, SQLAlchemy 2, Pydantic 2, SQLite, pytest + httpx (new), React 18 + Vite.

**Spec:** `docs/superpowers/specs/2026-09-13-pollen-tracking-design.md`

## Global Constraints

- All paths below are relative to the repo root `E:\johnv\source\repos\Unraid_Community_VulcanWork` unless noted. The app lives under `seedbreed/`.
- `PlantSex` enum values, exactly: `unknown` (default), `female`, `male`, `hermaphrodite`.
- Pollen source plant must have sex `male` or `hermaphrodite`; enforced in backend with 400 message `"Pollen can only be collected from a plant marked male or hermaphrodite."`
- `SeedProductionCreate` / `SeedProductionUpdate` no longer accept `parent_b_plant_id`; they accept `pollen_collection_id`. `parent_b_plant_id` is derived from the pollen's `source_plant_id` (or set to `NULL` when pollen is explicitly `null`; left untouched when omitted on update).
- `pollen_label` format: `"<source plant label> · <collected_date>"` (ISO date, middle dot U+00B7).
- Migration SQL: `ALTER TABLE plants ADD COLUMN sex VARCHAR NOT NULL DEFAULT 'unknown'` and `ALTER TABLE seed_production_events ADD COLUMN pollen_collection_id INTEGER`.
- Do NOT change `backend/requirements.txt` pins (they're what the Docker image uses). **Local Python is 3.14 and the pinned wheels don't exist for it**, so the local test venv installs the unpinned latest versions (verified working: fastapi 0.141 / pydantic 2.13 / sqlalchemy 2.0.52 / Pillow 12.3). The container still uses the pins.
- Node is not installed locally and Docker Desktop is not running. Frontend tasks are verified by careful review plus, if Docker Desktop can be started, `docker compose up --build`. See Task 8.
- Commit messages end with: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
- Windows/Git Bash: activate the venv with `source seedbreed/backend/.venv/Scripts/activate` or call `seedbreed/backend/.venv/Scripts/python` directly. Run pytest from `seedbreed/backend/` so `app` is importable.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `seedbreed/.gitignore` | create | keep venv, local DB/photos, caches out of git |
| `seedbreed/backend/requirements-dev.txt` | create | test deps (`pytest`, `httpx`) |
| `seedbreed/backend/tests/__init__.py` | create | make tests a package |
| `seedbreed/backend/tests/conftest.py` | create | env setup before app import; `client` (authed TestClient) fixture; helper factories |
| `seedbreed/backend/tests/test_health.py` | create | harness smoke test |
| `seedbreed/backend/tests/test_migrations.py` | create | new-column migration tests |
| `seedbreed/backend/tests/test_plants.py` | create | plant `sex` tests |
| `seedbreed/backend/tests/test_pollen.py` | create | pollen CRUD + validation tests |
| `seedbreed/backend/tests/test_seed_production.py` | create | pollen → parent B derivation tests |
| `seedbreed/backend/app/models.py` | modify | `PlantSex` enum, `Plant.sex`, `PollenCollection`, `SeedProductionEvent.pollen_collection_id` |
| `seedbreed/backend/app/database.py` | modify | migrations for the two new columns; optional engine param for testability |
| `seedbreed/backend/app/schemas.py` | modify | plant `sex`; `Pollen*` schemas; seed-production schema changes |
| `seedbreed/backend/app/main.py` | modify | `/api/pollen` routes; seed-production derive-parent-B logic |
| `seedbreed/frontend/src/pages/GrowDetail.jsx` | modify | Sex dropdown in `PlantModal`; sex badge in `GroupPanel` |
| `seedbreed/frontend/src/pages/Breeding.jsx` | modify | Pollen library section + `PollenModal`; `BreedingModal` pollen dropdown |
| `seedbreed/README.md` | modify | document pollen collections |

---

### Task 1: Test harness

**Files:**
- Create: `seedbreed/.gitignore`
- Create: `seedbreed/backend/requirements-dev.txt`
- Create: `seedbreed/backend/tests/__init__.py`
- Create: `seedbreed/backend/tests/conftest.py`
- Create: `seedbreed/backend/tests/test_health.py`

**Interfaces:**
- Produces: pytest fixture `client` — a `fastapi.testclient.TestClient` whose default headers carry a valid `Authorization: Bearer …` so writes succeed. Fixture `anon_client` — same app, no auth header. Helper `make_plant(client, label, sex="unknown", **extra) -> dict` returning the created plant JSON.

- [ ] **Step 1: Create the venv and install deps**

Run (from repo root, Git Bash):
```bash
cd seedbreed/backend && python -m venv .venv && ./.venv/Scripts/python -m pip install -q --only-binary=:all: fastapi sqlalchemy pydantic python-multipart Pillow pytest httpx && ./.venv/Scripts/python -c "import fastapi, pydantic, sqlalchemy, PIL, pytest, httpx; print('deps ok')"
```
Expected: `deps ok`

- [ ] **Step 2: Write `.gitignore` and `requirements-dev.txt`**

`seedbreed/.gitignore`:
```
.venv/
__pycache__/
.pytest_cache/
backend/data/
backend/photos/
frontend/node_modules/
frontend/dist/
data/
photos/
.env
```

`seedbreed/backend/requirements-dev.txt`:
```
# Test-only deps. Runtime deps are in requirements.txt (pinned for the Docker
# image). If your local Python is newer than the pins support, install the
# runtime deps unpinned in your venv instead:
#   pip install fastapi sqlalchemy pydantic python-multipart Pillow
pytest
httpx
```

- [ ] **Step 3: Write conftest**

`seedbreed/backend/tests/__init__.py` — empty file.

`seedbreed/backend/tests/conftest.py`:
```python
"""Shared test setup.

database.py and auth.py read their config from the environment at import
time, so the env vars are set here — before anything imports `app` — and
point at a throwaway temp dir. Every test module shares one SQLite file for
the session; tests create their own rows and never assume an empty table.
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="seedbreed-test-")
os.environ["SEEDBREED_DATA_DIR"] = os.path.join(_TMP, "data")
os.environ["SEEDBREED_PHOTOS_DIR"] = os.path.join(_TMP, "photos")
os.environ["SEEDBREED_AUTH_USERNAME"] = "tester"
os.environ["SEEDBREED_AUTH_PASSWORD"] = "secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def anon_client():
    """Unauthenticated client — reads work, writes get 401."""
    return TestClient(app)


@pytest.fixture(scope="session")
def client(anon_client):
    """Client with a valid login token on every request."""
    r = anon_client.post("/api/auth/login", json={"username": "tester", "password": "secret"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def make_plant(client, label, sex="unknown", **extra):
    """Create a plant via the API and return its JSON."""
    r = client.post("/api/plants", json={"label": label, "sex": sex, **extra})
    assert r.status_code == 200, r.text
    return r.json()
```

- [ ] **Step 4: Write the smoke test**

`seedbreed/backend/tests/test_health.py`:
```python
def test_health_is_open(anon_client):
    r = anon_client.get("/api/health")
    assert r.status_code == 200


def test_writes_require_login(anon_client, client):
    assert anon_client.post("/api/strains", json={"name": "Nope"}).status_code == 401
    assert client.post("/api/strains", json={"name": "Harness Strain"}).status_code == 200
```

- [ ] **Step 5: Run the smoke test**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest tests/test_health.py -v`
Expected: 2 passed. (A `StarletteDeprecationWarning` about httpx is fine.)

Note: `make_plant` passes `sex`, which the API ignores until Task 2 — Pydantic drops unknown fields, so it's harmless now.

- [ ] **Step 6: Commit**

```bash
git add seedbreed/.gitignore seedbreed/backend/requirements-dev.txt seedbreed/backend/tests/
git commit -m "Add pytest harness for the SeedBreed backend

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Plant sex (model, migration, schema)

**Files:**
- Modify: `seedbreed/backend/app/models.py` (enums block ~line 27; `Plant` class ~line 128)
- Modify: `seedbreed/backend/app/database.py` (`run_lightweight_migrations`, ~line 30)
- Modify: `seedbreed/backend/app/schemas.py` (`PlantCreate`/`PlantUpdate`/`PlantOut`, ~line 160)
- Create: `seedbreed/backend/tests/test_plants.py`
- Create: `seedbreed/backend/tests/test_migrations.py`

**Interfaces:**
- Produces: `models.PlantSex` enum (`unknown`, `female`, `male`, `hermaphrodite`); `Plant.sex` column; `run_lightweight_migrations(target_engine=None)` — optional engine so tests can run it against a hand-built old-schema DB; `sex` on `PlantCreate` (default `unknown`), `PlantUpdate` (optional), `PlantOut`.

- [ ] **Step 1: Write the failing plant tests**

`seedbreed/backend/tests/test_plants.py`:
```python
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
```

- [ ] **Step 2: Write the failing migration test**

`seedbreed/backend/tests/test_migrations.py`:
```python
"""run_lightweight_migrations() must add columns that pre-date this release
and be safe to run repeatedly."""
import os

from sqlalchemy import create_engine, text

from app.database import run_lightweight_migrations


def _old_schema_engine(tmp_path):
    """A DB whose plants / seed_production_events tables lack the new columns."""
    eng = create_engine(f"sqlite:///{os.path.join(tmp_path, 'old.db')}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE seeds (id INTEGER PRIMARY KEY, quantity INTEGER)"))
        conn.execute(text("CREATE TABLE strains (id INTEGER PRIMARY KEY, name VARCHAR)"))
        conn.execute(text("CREATE TABLE plants (id INTEGER PRIMARY KEY, label VARCHAR NOT NULL)"))
        conn.execute(text(
            "CREATE TABLE seed_production_events (id INTEGER PRIMARY KEY, "
            "parent_a_plant_id INTEGER NOT NULL, parent_b_plant_id INTEGER)"
        ))
        conn.execute(text("INSERT INTO plants (label) VALUES ('legacy')"))
    return eng


def _cols(eng, table):
    with eng.begin() as conn:
        return {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}


def test_migration_adds_plant_sex_with_unknown_default(tmp_path):
    eng = _old_schema_engine(tmp_path)
    run_lightweight_migrations(eng)
    assert "sex" in _cols(eng, "plants")
    with eng.begin() as conn:
        assert conn.execute(text("SELECT sex FROM plants")).scalar_one() == "unknown"


def test_migration_adds_pollen_collection_id_to_events(tmp_path):
    eng = _old_schema_engine(tmp_path)
    run_lightweight_migrations(eng)
    assert "pollen_collection_id" in _cols(eng, "seed_production_events")


def test_migration_is_idempotent(tmp_path):
    eng = _old_schema_engine(tmp_path)
    run_lightweight_migrations(eng)
    run_lightweight_migrations(eng)  # must not raise "duplicate column"
    assert "sex" in _cols(eng, "plants")
```

- [ ] **Step 3: Run both test files to verify they fail**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest tests/test_plants.py tests/test_migrations.py -v`
Expected: FAIL — `KeyError: 'sex'` in plant tests; `TypeError: run_lightweight_migrations() takes 0 positional arguments` in migration tests.

- [ ] **Step 4: Add the enum and column to models.py**

In `seedbreed/backend/app/models.py`, after the `SeedProductionType` enum (before `# ---------- Core entities ----------`), add:
```python
class PlantSex(str, enum.Enum):
    unknown = "unknown"
    female = "female"
    male = "male"
    hermaphrodite = "hermaphrodite"
```

In the `Plant` class, after the `position` column, add:
```python
    sex = Column(SqlEnum(PlantSex), nullable=False, default=PlantSex.unknown)
```

- [ ] **Step 5: Add the migrations (and the engine parameter) to database.py**

Replace the whole `run_lightweight_migrations` function in `seedbreed/backend/app/database.py` with:
```python
def run_lightweight_migrations(target_engine=None):
    """Add columns introduced after a DB was first created.

    SQLAlchemy's create_all() only creates missing tables, never alters existing
    ones, so a column added to a model won't appear in an already-populated DB.
    We keep a tiny idempotent ALTER-if-missing step here rather than pull in a
    full migration framework for a single-file app.

    Must run after create_all() (so the tables exist) and before any ORM query
    touches the new columns — both entry points (seed_data and main) call it.

    `target_engine` defaults to the app engine; tests pass their own.
    """
    from sqlalchemy import text

    eng = target_engine or engine
    with eng.begin() as conn:
        seed_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(seeds)"))}
        if "seeds_remaining" not in seed_cols:
            conn.execute(text("ALTER TABLE seeds ADD COLUMN seeds_remaining INTEGER"))
            # Backfill: existing batches start with all of their quantity remaining.
            conn.execute(text(
                "UPDATE seeds SET seeds_remaining = quantity WHERE seeds_remaining IS NULL"
            ))
        if "feminized" not in seed_cols:
            conn.execute(text(
                "ALTER TABLE seeds ADD COLUMN feminized BOOLEAN NOT NULL DEFAULT 0"
            ))
        if "auto_flower" not in seed_cols:
            conn.execute(text(
                "ALTER TABLE seeds ADD COLUMN auto_flower BOOLEAN NOT NULL DEFAULT 0"
            ))

        strain_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(strains)"))}
        if "indica_pct" not in strain_cols:
            conn.execute(text("ALTER TABLE strains ADD COLUMN indica_pct FLOAT"))
        if "sativa_pct" not in strain_cols:
            conn.execute(text("ALTER TABLE strains ADD COLUMN sativa_pct FLOAT"))
        if "thc_pct" not in strain_cols:
            conn.execute(text("ALTER TABLE strains ADD COLUMN thc_pct FLOAT"))

        plant_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(plants)"))}
        if "strain_id" not in plant_cols:
            conn.execute(text("ALTER TABLE plants ADD COLUMN strain_id INTEGER"))
        if "quantity_harvested" not in plant_cols:
            conn.execute(text("ALTER TABLE plants ADD COLUMN quantity_harvested VARCHAR"))
        if "comments" not in plant_cols:
            conn.execute(text("ALTER TABLE plants ADD COLUMN comments TEXT"))
        if "issues" not in plant_cols:
            conn.execute(text("ALTER TABLE plants ADD COLUMN issues TEXT"))
        if "sex" not in plant_cols:
            conn.execute(text(
                "ALTER TABLE plants ADD COLUMN sex VARCHAR NOT NULL DEFAULT 'unknown'"
            ))

        sp_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(seed_production_events)"))}
        if "pollen_collection_id" not in sp_cols:
            conn.execute(text(
                "ALTER TABLE seed_production_events ADD COLUMN pollen_collection_id INTEGER"
            ))
```

- [ ] **Step 6: Add `sex` to the plant schemas**

In `seedbreed/backend/app/schemas.py`:

Change the import line to:
```python
from .models import SeedOrigin, FertilizerType, SeedProductionType, PlantSex
```

In `PlantCreate`, after `position: Optional[str] = None`, add:
```python
    sex: PlantSex = PlantSex.unknown
```

In `PlantUpdate`, after `position: Optional[str] = None`, add:
```python
    sex: Optional[PlantSex] = None
```

In `PlantOut`, after `position: Optional[str]`, add:
```python
    sex: PlantSex
```

- [ ] **Step 7: Run the full suite**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest -v`
Expected: all pass (health 2, plants 3, migrations 3). The migration test for `pollen_collection_id` passes already because Step 5 added that ALTER; the model column itself comes in Task 3.

- [ ] **Step 8: Commit**

```bash
git add seedbreed/backend/app/models.py seedbreed/backend/app/database.py seedbreed/backend/app/schemas.py seedbreed/backend/tests/test_plants.py seedbreed/backend/tests/test_migrations.py
git commit -m "Add sex to plants (unknown/female/male/hermaphrodite)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Pollen collections (model, schemas, CRUD routes)

**Files:**
- Modify: `seedbreed/backend/app/models.py` (add `PollenCollection` before `SeedProductionEvent`; add FK column + relationship to `SeedProductionEvent`)
- Modify: `seedbreed/backend/app/schemas.py` (add `Pollen*` schemas before `# ---------- Seed Production ----------`)
- Modify: `seedbreed/backend/app/main.py` (add `# ============ Pollen ============` section before `# ============ Seed Production (the breeding piece) ============`)
- Create: `seedbreed/backend/tests/test_pollen.py`

**Interfaces:**
- Consumes: `models.PlantSex`, `make_plant` (Task 1/2).
- Produces: `models.PollenCollection` (`id, source_plant_id, collected_date, amount, storage, notes, created_at`, relationship `source_plant`); `SeedProductionEvent.pollen_collection_id` + relationship `pollen_collection`; schemas `PollenCreate`, `PollenUpdate`, `PollenOut` (with `source_plant_label`, `source_plant_strain_name`); routes `GET/POST /api/pollen`, `PATCH/DELETE /api/pollen/{id}`; helper `_pollen_to_out(p) -> PollenOut`; helper `_assert_pollen_source(db, plant_id) -> models.Plant`. The delete guard (400 when referenced by an event) is implemented here; its test lands in Task 4 once events can reference pollen.

- [ ] **Step 1: Write the failing pollen tests**

`seedbreed/backend/tests/test_pollen.py`:
```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest tests/test_pollen.py -v`
Expected: FAIL with 404s (`/api/pollen` doesn't exist) / 405.

- [ ] **Step 3: Add the model and the event FK**

In `seedbreed/backend/app/models.py`, immediately before `class SeedProductionEvent(Base):`, add:
```python
class PollenCollection(Base):
    """Pollen collected from a male or hermaphrodite plant.

    One row per collection. The same plant can appear many times — that's how
    a stash "accumulates". Seed-production events reference the collection
    that fathered them, which is how Parent B is derived.
    """
    __tablename__ = "pollen_collections"

    id = Column(Integer, primary_key=True)
    source_plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    collected_date = Column(Date, nullable=False, default=date.today)
    amount = Column(String, nullable=True)   # free-form: '~0.5 g', '2 vials'
    storage = Column(String, nullable=True)  # 'freezer, vial #3'
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    source_plant = relationship("Plant")
```

In `SeedProductionEvent`, after `parent_b_plant_id = Column(...)`, add:
```python
    # Which pollen collection fathered these seeds. When set, parent_b_plant_id
    # is derived from it (pollen.source_plant_id). Null for self/herm/unknown
    # events and for legacy rows logged before pollen tracking existed.
    pollen_collection_id = Column(Integer, ForeignKey("pollen_collections.id"), nullable=True)
```

and after `parent_b = relationship(...)`, add:
```python
    pollen_collection = relationship("PollenCollection")
```

Also update the `SeedProductionEvent` docstring's second line to read:
```
    parent_b_plant_id is the father (pollen donor) — derived from pollen_collection_id
    when present; null for self/herm/unknown; legacy rows may carry a manual value.
```

- [ ] **Step 4: Add the schemas**

In `seedbreed/backend/app/schemas.py`, before `# ---------- Seed Production ----------`, add:
```python
# ---------- Pollen ----------

class PollenCreate(BaseModel):
    source_plant_id: int
    collected_date: Optional[date] = None
    amount: Optional[str] = None
    storage: Optional[str] = None
    notes: Optional[str] = None


class PollenUpdate(BaseModel):
    """Partial update — only provided fields are changed."""
    source_plant_id: Optional[int] = None
    collected_date: Optional[date] = None
    amount: Optional[str] = None
    storage: Optional[str] = None
    notes: Optional[str] = None


class PollenOut(ORMBase):
    id: int
    source_plant_id: int
    collected_date: date
    amount: Optional[str]
    storage: Optional[str]
    notes: Optional[str]
    created_at: datetime
    source_plant_label: Optional[str] = None
    source_plant_strain_name: Optional[str] = None
```

- [ ] **Step 5: Add the routes**

In `seedbreed/backend/app/main.py`, immediately before the line `# ============ Seed Production (the breeding piece) ============` (line ~669; it precedes `_sp_to_out`), add:
```python
# ============ Pollen ============

POLLEN_SOURCE_SEXES = {models.PlantSex.male, models.PlantSex.hermaphrodite}


def _plant_strain_name(plant: models.Plant) -> Optional[str]:
    strain = plant.strain
    if strain is None and plant.seed and plant.seed.strain:
        strain = plant.seed.strain
    return strain.name if strain else None


def _pollen_to_out(p: models.PollenCollection) -> schemas.PollenOut:
    data = schemas.PollenOut.model_validate(p).model_dump()
    data["source_plant_label"] = p.source_plant.label if p.source_plant else None
    data["source_plant_strain_name"] = _plant_strain_name(p.source_plant) if p.source_plant else None
    return schemas.PollenOut(**data)


def _assert_pollen_source(db: Session, plant_id: int) -> models.Plant:
    """Pollen can only come from a plant we've marked male or hermaphrodite."""
    plant = db.get(models.Plant, plant_id)
    if not plant:
        raise HTTPException(400, "source_plant_id not found")
    if plant.sex not in POLLEN_SOURCE_SEXES:
        raise HTTPException(
            400, "Pollen can only be collected from a plant marked male or hermaphrodite."
        )
    return plant


@app.get("/api/pollen", response_model=List[schemas.PollenOut])
def list_pollen(db: Session = Depends(get_db)):
    return [_pollen_to_out(p) for p in db.query(models.PollenCollection).order_by(
        models.PollenCollection.collected_date.desc(), models.PollenCollection.id.desc()).all()]


@app.post("/api/pollen", response_model=schemas.PollenOut)
def create_pollen(payload: schemas.PollenCreate, db: Session = Depends(get_db)):
    _assert_pollen_source(db, payload.source_plant_id)
    data = payload.model_dump()
    if data.get("collected_date") is None:
        data["collected_date"] = date.today()
    p = models.PollenCollection(**data)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _pollen_to_out(p)


@app.patch("/api/pollen/{pollen_id}", response_model=schemas.PollenOut)
def update_pollen(pollen_id: int, payload: schemas.PollenUpdate, db: Session = Depends(get_db)):
    """Edit a pollen collection. Only the fields you send are changed."""
    p = db.get(models.PollenCollection, pollen_id)
    if not p:
        raise HTTPException(404, "Pollen collection not found")
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("source_plant_id") is not None:
        _assert_pollen_source(db, updates["source_plant_id"])
    for field, value in updates.items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return _pollen_to_out(p)


@app.delete("/api/pollen/{pollen_id}")
def delete_pollen(pollen_id: int, db: Session = Depends(get_db)):
    p = db.get(models.PollenCollection, pollen_id)
    if not p:
        raise HTTPException(404, "Pollen collection not found")
    referenced = db.query(models.SeedProductionEvent).filter_by(pollen_collection_id=pollen_id).first()
    if referenced:
        raise HTTPException(
            400,
            "Can't delete this pollen record: a seed-production event uses it. "
            "Edit that breeding record first.",
        )
    db.delete(p)
    db.commit()
    return {"ok": True, "id": pollen_id}
```

Then simplify `_plant_to_out` (just above the plant routes) to reuse the helper — replace its body with:
```python
def _plant_to_out(plant: models.Plant) -> schemas.PlantOut:
    data = schemas.PlantOut.model_validate(plant).model_dump()
    # Prefer a directly-linked strain; fall back to the seed's strain.
    data["strain_name"] = _plant_strain_name(plant)
    data["group_name"] = plant.group.name if plant.group else None
    return schemas.PlantOut(**data)
```
`_plant_strain_name` is defined later in the file than `_plant_to_out`, which is fine in Python — it's only called at request time. If you'd rather keep definitions ordered, move `_plant_strain_name` up next to `_plant_to_out` instead.

- [ ] **Step 6: Run the full suite**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest -v`
Expected: all pass (previous 8 + pollen 8).

- [ ] **Step 7: Commit**

```bash
git add seedbreed/backend/app/models.py seedbreed/backend/app/schemas.py seedbreed/backend/app/main.py seedbreed/backend/tests/test_pollen.py
git commit -m "Add pollen collections API

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Seed-production events derive Parent B from pollen

**Files:**
- Modify: `seedbreed/backend/app/schemas.py` (`SeedProductionCreate`, `SeedProductionUpdate`, `SeedProductionOut`)
- Modify: `seedbreed/backend/app/main.py` (`_sp_to_out`, `create_seed_production`, `update_seed_production`)
- Create: `seedbreed/backend/tests/test_seed_production.py`

**Interfaces:**
- Consumes: `models.PollenCollection`, `/api/pollen` (Task 3), `make_plant`.
- Produces: `SeedProductionCreate.pollen_collection_id: Optional[int]` (no `parent_b_plant_id`); same on `SeedProductionUpdate`; `SeedProductionOut.pollen_collection_id`, `SeedProductionOut.pollen_label`. Helper `_pollen_label(p) -> str`.

- [ ] **Step 1: Write the failing tests**

`seedbreed/backend/tests/test_seed_production.py`:
```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest tests/test_seed_production.py -v`
Expected: FAIL — `KeyError: 'pollen_collection_id'` / `pollen_label`, and `test_parent_b_plant_id_is_ignored_as_input` fails because the old schema still accepts `parent_b_plant_id`. `test_pollen_referenced_by_event_cannot_be_deleted` may already pass (ignore).

- [ ] **Step 3: Update the schemas**

In `seedbreed/backend/app/schemas.py`, replace the three seed-production classes with:
```python
class SeedProductionCreate(BaseModel):
    date: Optional[date_type] = None
    parent_a_plant_id: int
    # Parent B (pollen donor) is derived server-side from this pollen record.
    pollen_collection_id: Optional[int] = None
    event_type: SeedProductionType
    seed_count: Optional[int] = None
    new_strain_name: Optional[str] = None
    notes: Optional[str] = None


class SeedProductionUpdate(BaseModel):
    """Partial update — only provided fields are changed.

    Edits the event record itself; does not retroactively create/alter the
    strain or seed batch that the original event may have spawned.
    Sending pollen_collection_id re-derives parent B (null clears it);
    omitting it leaves parent B untouched.
    """
    date: Optional[date_type] = None
    parent_a_plant_id: Optional[int] = None
    pollen_collection_id: Optional[int] = None
    event_type: Optional[SeedProductionType] = None
    seed_count: Optional[int] = None
    new_strain_name: Optional[str] = None
    notes: Optional[str] = None


class SeedProductionOut(ORMBase):
    id: int
    date: date
    parent_a_plant_id: int
    parent_b_plant_id: Optional[int]
    pollen_collection_id: Optional[int]
    event_type: SeedProductionType
    seed_count: Optional[int]
    new_strain_name: Optional[str]
    notes: Optional[str]
    created_at: datetime
    parent_a_label: Optional[str] = None
    parent_b_label: Optional[str] = None
    pollen_label: Optional[str] = None
```

- [ ] **Step 4: Update the routes**

In `seedbreed/backend/app/main.py`, replace `_sp_to_out`, `create_seed_production`, and `update_seed_production` with:
```python
def _pollen_label(p: models.PollenCollection) -> str:
    label = p.source_plant.label if p.source_plant else f"Plant #{p.source_plant_id}"
    return f"{label} · {p.collected_date.isoformat()}"


def _sp_to_out(e: models.SeedProductionEvent) -> schemas.SeedProductionOut:
    data = schemas.SeedProductionOut.model_validate(e).model_dump()
    data["parent_a_label"] = e.parent_a.label if e.parent_a else None
    data["parent_b_label"] = e.parent_b.label if e.parent_b else None
    data["pollen_label"] = _pollen_label(e.pollen_collection) if e.pollen_collection else None
    return schemas.SeedProductionOut(**data)


def _get_pollen_or_400(db: Session, pollen_id: int) -> models.PollenCollection:
    p = db.get(models.PollenCollection, pollen_id)
    if not p:
        raise HTTPException(400, "pollen_collection_id not found")
    return p


@app.get("/api/seed-production", response_model=List[schemas.SeedProductionOut])
def list_seed_production(db: Session = Depends(get_db)):
    return [_sp_to_out(e) for e in db.query(models.SeedProductionEvent).order_by(
        models.SeedProductionEvent.date.desc()).all()]


@app.post("/api/seed-production", response_model=schemas.SeedProductionOut)
def create_seed_production(payload: schemas.SeedProductionCreate, db: Session = Depends(get_db)):
    """Log a seed-production event.

    Parent B (the pollen donor) is derived from the pollen collection, never
    set directly. Side effects: create a new Strain (if new_strain_name given
    and not existing), then create a Seed batch linked to that strain with
    origin='produced' and the parent event recorded — closing the lineage loop.
    """
    pa = db.get(models.Plant, payload.parent_a_plant_id)
    if not pa:
        raise HTTPException(400, "parent_a_plant_id not found")
    pollen = _get_pollen_or_400(db, payload.pollen_collection_id) if payload.pollen_collection_id else None
    pb = pollen.source_plant if pollen else None

    data = payload.model_dump()
    if data.get("date") is None:
        data["date"] = date.today()
    data["parent_b_plant_id"] = pb.id if pb else None
    event = models.SeedProductionEvent(**data)
    db.add(event)
    db.flush()

    # Figure out (or create) the resulting strain
    strain = None
    if payload.new_strain_name:
        strain = db.query(models.Strain).filter_by(name=payload.new_strain_name).first()
        if not strain:
            pa_strain = pa.strain or (pa.seed.strain if (pa.seed and pa.seed.strain) else None)
            pb_strain = (pb.strain or (pb.seed.strain if (pb.seed and pb.seed.strain) else None)) if pb else None
            strain = models.Strain(
                name=payload.new_strain_name,
                parent_a_id=pa_strain.id if pa_strain else None,
                parent_b_id=pb_strain.id if pb_strain else None,
                notes=f"Created from seed-production event on {data['date']}",
            )
            db.add(strain)
            db.flush()

    if strain:
        seed = models.Seed(
            strain_id=strain.id,
            origin=models.SeedOrigin.produced,
            source_label="self-produced",
            acquired_date=data["date"],
            quantity=payload.seed_count,
            produced_by_event_id=event.id,
            notes=payload.notes,
        )
        db.add(seed)

    db.commit()
    db.refresh(event)
    return _sp_to_out(event)


@app.patch("/api/seed-production/{event_id}", response_model=schemas.SeedProductionOut)
def update_seed_production(event_id: int, payload: schemas.SeedProductionUpdate, db: Session = Depends(get_db)):
    """Edit an existing seed-production event. Only the fields you send change.

    This edits the event record itself only — it doesn't retroactively create or
    rename the strain/seed batch the original event may have spawned. Sending
    pollen_collection_id re-derives parent B; sending null clears both.
    """
    event = db.get(models.SeedProductionEvent, event_id)
    if not event:
        raise HTTPException(404, "Seed-production event not found")
    updates = payload.model_dump(exclude_unset=True)
    if "parent_a_plant_id" in updates and not db.get(models.Plant, updates["parent_a_plant_id"]):
        raise HTTPException(400, "parent_a_plant_id not found")
    if "pollen_collection_id" in updates:
        if updates["pollen_collection_id"] is None:
            updates["parent_b_plant_id"] = None
        else:
            pollen = _get_pollen_or_400(db, updates["pollen_collection_id"])
            updates["parent_b_plant_id"] = pollen.source_plant_id
    for field, value in updates.items():
        setattr(event, field, value)
    db.commit()
    db.refresh(event)
    return _sp_to_out(event)
```

Note the strain lookup for the new cross now prefers the plant's direct `strain_id` (matching `_plant_to_out`) and falls back to the seed's strain. Previously only the seed's strain was used — that's why `test_named_cross_links_both_parent_strains_via_pollen` sets `strain_id` on the plants.

- [ ] **Step 5: Run the full suite**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest -v`
Expected: all pass (previous 16 + seed production 8 = 24).

- [ ] **Step 6: Commit**

```bash
git add seedbreed/backend/app/schemas.py seedbreed/backend/app/main.py seedbreed/backend/tests/test_seed_production.py
git commit -m "Derive seed-production Parent B from the pollen collection used

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Frontend — plant sex dropdown and badge

**Files:**
- Modify: `seedbreed/frontend/src/pages/GrowDetail.jsx` (`GroupPanel` ~line 185; `PlantModal` ~line 483)

**Interfaces:**
- Consumes: `PlantOut.sex`, `PlantCreate.sex`, `PlantUpdate.sex` (Task 2).
- Produces: exported helper `sexBadge(sex)` at the top of `GrowDetail.jsx` — returns `{ symbol, text }` or `null` for `unknown` — so Breeding can reuse it.

- [ ] **Step 1: Add the badge helper**

In `seedbreed/frontend/src/pages/GrowDetail.jsx`, after `const MAX_PLANTS_PER_GROUP = 4;`, add:
```jsx
export const PLANT_SEX_OPTIONS = [
  { value: 'unknown', label: 'Unknown' },
  { value: 'female', label: 'Female' },
  { value: 'male', label: 'Male' },
  { value: 'hermaphrodite', label: 'Hermaphrodite' },
];

// Small ♀ / ♂ / ⚥ tag for a plant's sex; null when we don't know it yet.
export function sexBadge(sex) {
  switch (sex) {
    case 'female': return { symbol: '♀', text: 'female' };
    case 'male': return { symbol: '♂', text: 'male' };
    case 'hermaphrodite': return { symbol: '⚥', text: 'herm' };
    default: return null;
  }
}
```

- [ ] **Step 2: Show the badge on plant cards**

In `GroupPanel`, replace:
```jsx
                <div>
                  <strong>{p.label}</strong>
                  {p.strain_name && <span className="muted"> · {p.strain_name}</span>}
                </div>
```
with:
```jsx
                <div>
                  <strong>{p.label}</strong>
                  {p.strain_name && <span className="muted"> · {p.strain_name}</span>}
                  {sexBadge(p.sex) && (
                    <span className="badge" style={{ marginLeft: 8 }} title={`Sex: ${p.sex}`}>
                      {sexBadge(p.sex).symbol} {sexBadge(p.sex).text}
                    </span>
                  )}
                </div>
```

- [ ] **Step 3: Add the Sex dropdown to `PlantModal`**

In `PlantModal`'s `useState` initialiser, add `sex` to both branches:
```jsx
  const [form, setForm] = useState(() => existing ? {
    label: existing.label || '',
    strain_id: existing.strain_id ? String(existing.strain_id) : '',
    sex: existing.sex || 'unknown',
    quantity_harvested: existing.quantity_harvested || '',
    comments: existing.comments || '',
    issues: existing.issues || '',
  } : {
    label: '', strain_id: '', sex: 'unknown', quantity_harvested: '', comments: '', issues: '',
  });
```

In `submit`, add `sex` to the payload:
```jsx
      const payload = {
        label: form.label,
        strain_id: form.strain_id ? parseInt(form.strain_id) : null,
        sex: form.sex,
        quantity_harvested: form.quantity_harvested || null,
        comments: form.comments || null,
        issues: form.issues || null,
      };
```

In the JSX, replace the `Quantity harvested` field block:
```jsx
        <div className="field">
          <label>Quantity harvested</label>
          <input value={form.quantity_harvested}
                 onChange={(e) => setForm({ ...form, quantity_harvested: e.target.value })}
                 placeholder="e.g. 3 oz, 85 g, 1 plant" />
        </div>
```
with a two-column row containing Sex and Quantity harvested:
```jsx
        <div className="grid grid-2">
          <div className="field">
            <label>Sex</label>
            <select value={form.sex} onChange={(e) => setForm({ ...form, sex: e.target.value })}>
              {PLANT_SEX_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <p className="small muted" style={{ margin: '6px 0 0' }}>
              Mark males/herms so you can log pollen from them under Breeding.
            </p>
          </div>
          <div className="field">
            <label>Quantity harvested</label>
            <input value={form.quantity_harvested}
                   onChange={(e) => setForm({ ...form, quantity_harvested: e.target.value })}
                   placeholder="e.g. 3 oz, 85 g, 1 plant" />
          </div>
        </div>
```

- [ ] **Step 4: Review the diff for syntax**

Run: `git diff seedbreed/frontend/src/pages/GrowDetail.jsx`
Check: balanced JSX tags, `sexBadge`/`PLANT_SEX_OPTIONS` defined before use, no stray commas. (No local Node — see Task 8 for a real build.)

- [ ] **Step 5: Commit**

```bash
git add seedbreed/frontend/src/pages/GrowDetail.jsx
git commit -m "Add sex dropdown and badge to plants

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Frontend — Breeding page pollen library + pollen-driven crosses

**Files:**
- Modify: `seedbreed/frontend/src/pages/Breeding.jsx` (full rewrite)

**Interfaces:**
- Consumes: `/api/pollen` (`PollenOut` with `source_plant_label`, `source_plant_strain_name`, `collected_date`, `amount`, `storage`, `notes`), `/api/seed-production` (`pollen_collection_id`, `pollen_label`, `parent_b_label`), `PlantOut.sex`, `sexBadge` from `GrowDetail.jsx`.

- [ ] **Step 1: Replace `Breeding.jsx` with the new page**

Overwrite `seedbreed/frontend/src/pages/Breeding.jsx` with:
```jsx
import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { sexBadge } from './GrowDetail.jsx';

const POLLEN_SEXES = new Set(['male', 'hermaphrodite']);

function plantOptionLabel(p) {
  const badge = sexBadge(p.sex);
  return `${p.label}${p.strain_name ? ` — ${p.strain_name}` : ''}${badge ? ` (${badge.symbol} ${badge.text})` : ''}`;
}

function pollenOptionLabel(p) {
  return `${p.source_plant_label || `Plant #${p.source_plant_id}`}`
    + `${p.source_plant_strain_name ? ` — ${p.source_plant_strain_name}` : ''}`
    + ` · ${p.collected_date}`;
}

export default function Breeding() {
  const [events, setEvents] = useState([]);
  const [plants, setPlants] = useState([]);
  const [pollen, setPollen] = useState([]);
  const [showNewEvent, setShowNewEvent] = useState(false);
  const [editEvent, setEditEvent] = useState(null);
  const [showNewPollen, setShowNewPollen] = useState(false);
  const [editPollen, setEditPollen] = useState(null);

  const load = async () => {
    const [e, p, po] = await Promise.all([
      api.get('/api/seed-production'),
      api.get('/api/plants'),
      api.get('/api/pollen'),
    ]);
    setEvents(e); setPlants(p); setPollen(po);
  };
  useEffect(() => { load(); }, []);

  const deletePollen = async (p) => {
    if (!confirm(`Delete pollen from ${p.source_plant_label} (${p.collected_date})?`)) return;
    try {
      await api.del(`/api/pollen/${p.id}`);
      load();
    } catch (e) { alert(e.message); }
  };

  return (
    <>
      <div className="page-header">
        <div className="eyebrow">Crosses & accidents</div>
        <h1>Breeding</h1>
      </div>

      {/* ---- Pollen library ---- */}
      <div className="flex-between mt-6">
        <div>
          <div className="eyebrow">Pollen library</div>
          <h2 style={{ margin: 0 }}>Collected pollen</h2>
        </div>
        <button className="primary" onClick={() => setShowNewPollen(true)}>+ Log pollen collection</button>
      </div>
      <p className="muted" style={{ maxWidth: 640 }}>
        Each time you collect pollen from a male or hermaphrodite plant, log it here. Pick one of
        these records when logging a cross below and the father is filled in automatically.
      </p>

      {pollen.length === 0 ? (
        <div className="empty card mt-4">
          <div className="empty-title">No pollen collected yet</div>
          <div className="small muted">
            Mark a plant male or hermaphrodite (edit it on its grow page), then log a collection.
          </div>
        </div>
      ) : (
        <div className="list mt-4">
          {pollen.map((p) => (
            <div key={p.id} className="list-row">
              <div className="list-row-main">
                <div className="list-row-title">
                  {p.source_plant_label || `Plant #${p.source_plant_id}`}
                  {p.source_plant_strain_name && <span className="muted"> — {p.source_plant_strain_name}</span>}
                </div>
                <div className="list-row-meta">
                  collected {p.collected_date}
                  {p.amount ? ` · ${p.amount}` : ''}
                  {p.storage ? ` · ${p.storage}` : ''}
                </div>
                {p.notes && <div className="small mt-2">{p.notes}</div>}
              </div>
              <div className="row-actions">
                <button className="small-btn" onClick={() => setEditPollen(p)}>Edit</button>
                <button className="small-btn danger" onClick={() => deletePollen(p)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ---- Seed production ---- */}
      <div className="flex-between" style={{ marginTop: 40 }}>
        <div>
          <div className="eyebrow">Seed production</div>
          <h2 style={{ margin: 0 }}>Crosses & seed events</h2>
        </div>
        <button className="primary" onClick={() => setShowNewEvent(true)}>+ Log seed production</button>
      </div>
      <p className="muted" style={{ maxWidth: 640 }}>
        Anytime a plant produces seeds — intentional cross, accidental pollination, or a hermie —
        log it here. The seeds get linked back to the mother and the pollen used, giving you a full
        genetic trail to follow forward and backward.
      </p>

      {events.length === 0 ? (
        <div className="empty card mt-4">
          <div className="empty-title">No breeding events recorded</div>
          <div className="small muted">Log the first one when seeds show up.</div>
        </div>
      ) : (
        <div className="list mt-4">
          {events.map((e) => (
            <div key={e.id} className="list-row">
              <div className="list-row-main">
                <div className="list-row-title">
                  {e.parent_a_label}
                  {e.parent_b_label ? <span className="muted"> × </span> : ''}
                  {e.parent_b_label || ''}
                  {e.new_strain_name && (
                    <span style={{ marginLeft: 12 }} className="badge produced">
                      → {e.new_strain_name}
                    </span>
                  )}
                </div>
                <div className="list-row-meta">
                  {e.date}
                  {' · '}{e.event_type.replace(/_/g, ' ')}
                  {e.seed_count ? ` · ${e.seed_count} seeds` : ''}
                  {e.pollen_label ? ` · pollen: ${e.pollen_label}` : ''}
                </div>
                {e.notes && <div className="small mt-2">{e.notes}</div>}
              </div>
              <div className="row-actions">
                <button className="small-btn" onClick={() => setEditEvent(e)}>Edit</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {(showNewPollen || editPollen) && (
        <PollenModal
          plants={plants}
          existing={editPollen}
          onClose={() => { setShowNewPollen(false); setEditPollen(null); }}
          onSaved={() => { setShowNewPollen(false); setEditPollen(null); load(); }}
        />
      )}

      {(showNewEvent || editEvent) && (
        <BreedingModal
          plants={plants}
          pollen={pollen}
          existing={editEvent}
          onClose={() => { setShowNewEvent(false); setEditEvent(null); }}
          onSaved={() => { setShowNewEvent(false); setEditEvent(null); load(); }}
        />
      )}
    </>
  );
}

function PollenModal({ plants, existing, onClose, onSaved }) {
  const isEdit = !!existing;
  const donors = plants.filter((p) => POLLEN_SEXES.has(p.sex));
  const [form, setForm] = useState(() => existing ? {
    source_plant_id: String(existing.source_plant_id),
    collected_date: existing.collected_date || '',
    amount: existing.amount || '',
    storage: existing.storage || '',
    notes: existing.notes || '',
  } : {
    source_plant_id: '', collected_date: '', amount: '', storage: '', notes: '',
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const payload = {
        source_plant_id: parseInt(form.source_plant_id),
        collected_date: form.collected_date || null,
        amount: form.amount || null,
        storage: form.storage || null,
        notes: form.notes || null,
      };
      if (isEdit) {
        await api.patch(`/api/pollen/${existing.id}`, payload);
      } else {
        await api.post('/api/pollen', payload);
      }
      onSaved();
    } catch (e) { alert(e.message); setBusy(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit pollen collection' : 'Log pollen collection'}</h2>

        <div className="field">
          <label>Source plant (male or hermaphrodite)</label>
          <select value={form.source_plant_id} disabled={donors.length === 0}
                  onChange={(e) => setForm({ ...form, source_plant_id: e.target.value })}>
            <option value="">— Select plant —</option>
            {donors.map((p) => (
              <option key={p.id} value={p.id}>{plantOptionLabel(p)}</option>
            ))}
          </select>
          {donors.length === 0 && (
            <p className="small muted" style={{ margin: '6px 0 0' }}>
              No plants are marked male or hermaphrodite yet. Edit a plant on its grow page and set its sex first.
            </p>
          )}
        </div>

        <div className="grid grid-2">
          <div className="field">
            <label>Date collected</label>
            <input type="date" value={form.collected_date}
                   onChange={(e) => setForm({ ...form, collected_date: e.target.value })} />
          </div>
          <div className="field">
            <label>Amount</label>
            <input value={form.amount} placeholder="e.g. ~0.5 g, 2 vials"
                   onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </div>
        </div>

        <div className="field">
          <label>Storage</label>
          <input value={form.storage} placeholder="e.g. freezer, vial #3"
                 onChange={(e) => setForm({ ...form, storage: e.target.value })} />
        </div>

        <div className="field">
          <label>Notes</label>
          <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>

        <div className="modal-actions">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" disabled={busy || !form.source_plant_id} onClick={submit}>
            {busy ? 'Saving…' : isEdit ? 'Save changes' : 'Log collection'}
          </button>
        </div>
      </div>
    </div>
  );
}

function BreedingModal({ plants, pollen, existing, onClose, onSaved }) {
  const isEdit = !!existing;
  const [form, setForm] = useState(() => existing ? {
    date: existing.date || '',
    parent_a_plant_id: existing.parent_a_plant_id ? String(existing.parent_a_plant_id) : '',
    pollen_collection_id: existing.pollen_collection_id ? String(existing.pollen_collection_id) : '',
    event_type: existing.event_type || 'intentional_cross',
    seed_count: existing.seed_count ?? '',
    new_strain_name: existing.new_strain_name || '',
    notes: existing.notes || '',
  } : {
    date: '', parent_a_plant_id: '', pollen_collection_id: '',
    event_type: 'intentional_cross', seed_count: '', new_strain_name: '', notes: '',
  });
  const [busy, setBusy] = useState(false);

  // A pre-pollen-tracking event that still carries a manually-picked father.
  const legacyDonor = isEdit && existing.parent_b_label && !existing.pollen_collection_id
    ? existing.parent_b_label : null;

  const submit = async () => {
    setBusy(true);
    try {
      const payload = {
        date: form.date || null,
        parent_a_plant_id: parseInt(form.parent_a_plant_id),
        pollen_collection_id: form.pollen_collection_id ? parseInt(form.pollen_collection_id) : null,
        event_type: form.event_type,
        seed_count: form.seed_count !== '' ? parseInt(form.seed_count) : null,
        new_strain_name: form.new_strain_name || null,
        notes: form.notes || null,
      };
      if (isEdit) {
        // Don't wipe a legacy manual father unless the user actually picked pollen.
        if (legacyDonor && !form.pollen_collection_id) delete payload.pollen_collection_id;
        await api.patch(`/api/seed-production/${existing.id}`, payload);
      } else {
        await api.post('/api/seed-production', payload);
      }
      onSaved();
    } catch (e) { alert(e.message); setBusy(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit seed production' : 'Log seed production'}</h2>

        <div className="grid grid-2">
          <div className="field">
            <label>Date</label>
            <input type="date" value={form.date}
                   onChange={(e) => setForm({ ...form, date: e.target.value })} />
          </div>
          <div className="field">
            <label>Event type</label>
            <select value={form.event_type}
                    onChange={(e) => setForm({ ...form, event_type: e.target.value })}>
              <option value="intentional_cross">Intentional cross</option>
              <option value="accidental_pollination">Accidental pollination</option>
              <option value="hermaphrodite">Hermaphrodite</option>
              <option value="self_pollinated">Self-pollinated</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>
        </div>

        <div className="field">
          <label>Parent A — mother (seed bearer)</label>
          <select value={form.parent_a_plant_id}
                  onChange={(e) => setForm({ ...form, parent_a_plant_id: e.target.value })}>
            <option value="">— Select plant —</option>
            {plants.map((p) => (
              <option key={p.id} value={p.id}>{plantOptionLabel(p)}</option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Pollen used (sets the father)</label>
          <select value={form.pollen_collection_id}
                  onChange={(e) => setForm({ ...form, pollen_collection_id: e.target.value })}>
            <option value="">— None (self / herm / unknown / not collected) —</option>
            {pollen.map((p) => (
              <option key={p.id} value={p.id}>{pollenOptionLabel(p)}</option>
            ))}
          </select>
          {legacyDonor && !form.pollen_collection_id && (
            <p className="small muted" style={{ margin: '6px 0 0' }}>
              Current pollen donor: {legacyDonor} (no pollen record). Pick a pollen record to replace it.
            </p>
          )}
          {pollen.length === 0 && (
            <p className="small muted" style={{ margin: '6px 0 0' }}>
              No pollen logged yet — add a collection in the Pollen library above to record a father.
            </p>
          )}
        </div>

        <div className="grid grid-2">
          <div className="field">
            <label>Seed count</label>
            <input type="number" value={form.seed_count}
                   onChange={(e) => setForm({ ...form, seed_count: e.target.value })} />
          </div>
          <div className="field">
            <label>New strain name (optional)</label>
            <input value={form.new_strain_name}
                   onChange={(e) => setForm({ ...form, new_strain_name: e.target.value })}
                   placeholder="e.g. Black Panty" />
          </div>
        </div>
        <p className="small muted" style={{ marginTop: -8 }}>
          {isEdit
            ? 'Editing updates this event record only — it won’t create or rename a strain/seed batch.'
            : 'If you name the cross, it auto-creates a strain with both parents linked and adds a seed batch.'}
        </p>

        <div className="field">
          <label>Notes</label>
          <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>

        <div className="modal-actions">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" disabled={busy || !form.parent_a_plant_id} onClick={submit}>
            {busy ? 'Saving…' : isEdit ? 'Save changes' : 'Log event'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

Note on the legacy-donor case: the spec says "omitting `pollen_collection_id` on update leaves Parent B alone". The modal implements that by deleting the key from the payload when editing a legacy event and the user left the dropdown blank; if they pick a record, the key is sent and Parent B is re-derived.

- [ ] **Step 2: Review the diff for syntax and imports**

Run: `git diff seedbreed/frontend/src/pages/Breeding.jsx | head -50` and re-read the file once top to bottom.
Check: `sexBadge` import path is `./GrowDetail.jsx` and it is `export`ed there (Task 5); `Link` import was removed because nothing uses it; every `useState` setter used is declared.

- [ ] **Step 3: Commit**

```bash
git add seedbreed/frontend/src/pages/Breeding.jsx
git commit -m "Add pollen library to Breeding and pick pollen for crosses

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: README

**Files:**
- Modify: `seedbreed/README.md` ("What's in here" list, ~line 18)

- [ ] **Step 1: Update the bullets**

In `seedbreed/README.md`, replace:
```
- **Plants** — individual plants linked to a seed, a grow, and a group.
```
with:
```
- **Plants** — individual plants linked to a seed, a grow, and a group, with a
  sex (unknown / female / male / hermaphrodite).
```

and replace the **Seed production events** bullet:
```
- **Seed production events** — log when a plant throws seeds (intentional
  cross, accidental pollination, hermie). If you name the cross, it auto-
  creates a new strain with both parents linked and adds a seed batch with
  `origin=produced` pointing back to the event — closing the lineage loop.
```
with:
```
- **Pollen collections** — every time you collect pollen from a male or
  hermaphrodite plant, log it (date, amount, where it's stored). The
  Breeding page lists your pollen library.
- **Seed production events** — log when a plant throws seeds (intentional
  cross, accidental pollination, hermie). Pick the pollen collection you
  used and the father is filled in from it. If you name the cross, it auto-
  creates a new strain with both parents linked and adds a seed batch with
  `origin=produced` pointing back to the event — closing the lineage loop.
```

Also, in the "Working on it locally" backend block, add after the `pip install -r requirements.txt` line:
```bash
pip install -r requirements-dev.txt   # pytest + httpx
python -m pytest                      # run the backend tests
```

- [ ] **Step 2: Commit**

```bash
git add seedbreed/README.md
git commit -m "Document pollen collections and plant sex

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: End-to-end verification

**Files:** none (verification only).

The backend suite is the automated gate. The frontend has no local Node, so the real check is a container build.

- [ ] **Step 1: Backend suite, final run**

Run: `cd seedbreed/backend && ./.venv/Scripts/python -m pytest -v`
Expected: 24 passed.

- [ ] **Step 2: Try the container build**

Start Docker Desktop if it isn't running, then:
```bash
cd seedbreed && docker compose up -d --build
```
Expected: image builds (this compiles the React frontend — a JSX syntax error in Tasks 5/6 fails here) and the container starts. If Docker cannot be started, stop here and report that the frontend is unverified so the user can run this step.

- [ ] **Step 3: Click through the flows**

Open `http://localhost:8080`, log in (`admin` / `changeme` unless `.env` overrides), then:
1. Grows → open the example grow → Edit a plant → set Sex = Male → save. Card shows `♂ male`.
2. Breeding → "+ Log pollen collection" → the male plant is listed; save with a date and amount. Row appears in the Pollen library.
3. Breeding → "+ Log seed production" → pick a mother, pick the pollen record, name the cross "Test Cross" → save. Row shows `Mother × Male plant`, meta shows `pollen: Male plant · <date>`, badge `→ Test Cross`.
4. Try deleting that pollen record → alert with the "seed-production event uses it" message.
5. Strains → "Test Cross" shows both parents.

- [ ] **Step 4: Tear down**

```bash
cd seedbreed && docker compose down
```
(The compose file mounts `./data` and `./photos`; both are git-ignored from Task 1.)

---

## Self-review notes

- Spec coverage: data model (T2, T3), API (T3, T4), UI plant modal + badge (T5), Breeding page (T6), tests 1–6 (T2 migrations; T2 plants; T3 pollen rejects/allows; T4 derive + label; T4 update semantics; T3 delete-unreferenced + T4 delete-referenced), docs (T7), frontend manual verification (T8). ✔
- Type consistency: `pollen_collection_id`, `pollen_label`, `source_plant_label`, `source_plant_strain_name`, `collected_date`, `sexBadge`, `PLANT_SEX_OPTIONS` used identically across tasks. ✔
- One deliberate deviation from the original code, called out in T4 Step 4: the new-cross strain lookup now honours a plant's direct `strain_id` before falling back to its seed's strain, matching how the rest of the app resolves a plant's strain.
