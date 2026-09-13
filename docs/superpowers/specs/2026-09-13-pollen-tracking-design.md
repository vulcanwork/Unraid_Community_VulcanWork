# Pollen tracking & plant sex — design

**Date:** 2026-09-13
**Scope:** SeedBreed (`seedbreed/`)

## Goal

Let the breeder record pollen collected from male/hermaphrodite plants and
record which pollen record was used in each seed-production event, so every
produced seed batch traces back to a mother plant and a specific pollen
collection. Requires knowing each plant's sex.

## Decisions (from brainstorming)

- Plant sex values: `unknown` (default), `female`, `male`, `hermaphrodite`.
- Pollen is tracked as **one record per collection** (not a per-plant running
  stash). Multiple collections from the same plant are simply multiple rows.
- Pollen source plant is **restricted** to plants whose sex is `male` or
  `hermaphrodite`. Enforced in the backend, not just the dropdown.
- In the seed-production form, the manual **Parent B picker is replaced** by a
  **"Pollen used"** dropdown. Parent B is derived from the pollen's source plant.
- Breeding page shows two **stacked sections**: Pollen library above Seed
  production.

## Data model

### `plants.sex`

- New enum `PlantSex(str, enum.Enum)`: `unknown`, `female`, `male`, `hermaphrodite`.
- Column: `sex = Column(SqlEnum(PlantSex), nullable=False, default=PlantSex.unknown)`.
- Migration (in `run_lightweight_migrations`):
  `ALTER TABLE plants ADD COLUMN sex VARCHAR NOT NULL DEFAULT 'unknown'`.

### `pollen_collections` (new table)

| column            | type                          | notes                                              |
|-------------------|-------------------------------|----------------------------------------------------|
| `id`              | Integer PK                    |                                                    |
| `source_plant_id` | FK `plants.id`, NOT NULL      | plant must be `male` or `hermaphrodite` when saved |
| `collected_date`  | Date, NOT NULL, default today |                                                    |
| `amount`          | String, nullable              | free-form, e.g. "~0.5 g", "2 vials"                |
| `storage`         | String, nullable              | e.g. "freezer, vial #3"                            |
| `notes`           | Text, nullable                |                                                    |
| `created_at`      | DateTime                      |                                                    |

Model class `PollenCollection`, relationship `source_plant` -> `Plant`.
`create_all()` creates the table on existing installs (new tables are fine;
only new columns need the migration step).

### `seed_production_events.pollen_collection_id`

- Nullable FK to `pollen_collections.id`. Relationship `pollen_collection`.
- Migration: `ALTER TABLE seed_production_events ADD COLUMN pollen_collection_id INTEGER`.
- `parent_b_plant_id` is **kept**. Semantics:
  - On create: if `pollen_collection_id` is set, `parent_b_plant_id :=
    pollen.source_plant_id`; otherwise `parent_b_plant_id := NULL`.
  - On update: if `pollen_collection_id` is present in the payload and non-null,
    re-derive `parent_b_plant_id` from the new pollen. If present and null,
    set `parent_b_plant_id := NULL` too. If absent, leave both untouched
    (legacy rows keep their manual Parent B).
- Existing lineage logic (`parent_b` relationship, strain auto-creation, grow /
  plant delete guards) is unchanged.

Rejected alternative: many-to-many pollen/event. A cross has one father; mixed
pollen is logged as separate events or a note.

## API

### Pollen

- `GET /api/pollen` -> `List[PollenOut]`, ordered by `collected_date desc`.
- `POST /api/pollen` (`PollenCreate`) -> `PollenOut`.
- `PATCH /api/pollen/{id}` (`PollenUpdate`, partial) -> `PollenOut`.
- `DELETE /api/pollen/{id}` -> `{ "ok": true }`; **400** if any seed-production
  event references it.

Schemas:

```
PollenCreate:  source_plant_id: int, collected_date: Optional[date],
               amount, storage, notes: Optional[str]
PollenUpdate:  all optional
PollenOut:     id, source_plant_id, collected_date, amount, storage, notes,
               created_at, source_plant_label: Optional[str],
               source_plant_strain_name: Optional[str]
```

Validation (create, and update when `source_plant_id` changes):
- plant must exist -> 400 `"source_plant_id not found"`
- plant.sex must be `male` or `hermaphrodite` -> 400
  `"Pollen can only be collected from a plant marked male or hermaphrodite."`

Write routes are already gated by the existing auth middleware.

### Plant

- `PlantCreate.sex: PlantSex = PlantSex.unknown`
- `PlantUpdate.sex: Optional[PlantSex]`
- `PlantOut.sex: PlantSex`

Changing a plant's sex away from male/herm does **not** cascade to or block on
existing pollen records (history stays; the restriction applies at logging time).

### Seed production

- `SeedProductionCreate`: remove `parent_b_plant_id`; add
  `pollen_collection_id: Optional[int]`.
- `SeedProductionUpdate`: remove `parent_b_plant_id`; add
  `pollen_collection_id: Optional[int]`.
- `SeedProductionOut`: keep `parent_b_plant_id` / `parent_b_label`; add
  `pollen_collection_id: Optional[int]` and `pollen_label: Optional[str]`
  (format: `"<source plant label> · <collected_date>"`).
- Validation: `pollen_collection_id` must exist -> 400
  `"pollen_collection_id not found"`.
- Strain auto-creation continues to use the derived Parent B plant's strain.

## UI

### Plant modal (`GrowDetail.jsx` -> `PlantModal`)

- Add a **Sex** `<select>` in a 2-column grid row alongside the existing
  fields. Options: Unknown, Female, Male, Hermaphrodite. Sent as `sex` on
  create and edit.
- Plant cards in `GroupPanel`: show a small badge after the strain name when
  `sex !== 'unknown'`: `♀ female`, `♂ male`, `⚥ herm`.

### Breeding page (`Breeding.jsx`)

Loads `/api/seed-production`, `/api/plants`, `/api/pollen`.

**Section 1 — Pollen library**
- Header row: eyebrow "Pollen library", `+ Log pollen collection` button.
- Empty state: "No pollen collected yet — mark a plant male or hermaphrodite,
  then log a collection."
- Rows: title `<source plant label> — <strain>`; meta
  `collected <date> · <amount> · <storage>`; notes below; Edit / Delete buttons.
  Delete confirms, surfaces the 400 message if referenced.
- `PollenModal`: Source plant select (only plants with sex `male` or
  `hermaphrodite`; if none, disabled select + helper text), Date, Amount,
  Storage, Notes. Save disabled until a source plant is chosen.

**Section 2 — Seed production** (existing list, moved under a section header)
- Row title: `<mother label> × <parent_b_label>` as today; meta line appends
  `· pollen: <pollen_label>` when present.
- `BreedingModal`: Parent B `<select>` replaced by **Pollen used** `<select>`:
  blank option "— None (self / herm / unknown / not collected) —", then each
  pollen record as `<source plant label> — <strain> · <date>`. When editing a
  legacy event with `parent_b_plant_id` but no pollen, show read-only text
  under the select: "Current pollen donor: <label> (no pollen record)".
  Payload sends `pollen_collection_id` (int or null) instead of
  `parent_b_plant_id`.
- Helper text under new-strain-name unchanged.

## Testing

No test suite exists today. Add `backend/tests/` (pytest, `httpx` for
TestClient) with a fixture that points `SEEDBREED_DATA_DIR` / `SEEDBREED_PHOTOS_DIR`
at a temp dir before importing `app.main`, and logs in to obtain a token for
writes. Add `pytest` and `httpx` to a `backend/requirements-dev.txt`.

Cases:
1. Migration: creating a DB then calling `run_lightweight_migrations` leaves
   `sex` and `pollen_collection_id` columns present (idempotent on re-run).
2. `POST /api/plants` defaults `sex` to `unknown`; `PATCH` can set it.
3. `POST /api/pollen` with a female/unknown source -> 400; with male -> 200.
4. `POST /api/seed-production` with `pollen_collection_id` sets
   `parent_b_plant_id` to the pollen's source plant and returns `pollen_label`.
5. `PATCH /api/seed-production/{id}` with `pollen_collection_id: null` clears
   `parent_b_plant_id`; omitting it leaves a legacy Parent B alone.
6. `DELETE /api/pollen/{id}` referenced by an event -> 400; unreferenced -> ok.

Frontend: manual verification via the Vite dev server (set plant sex, log
pollen, log a cross using that pollen, confirm the list shows the lineage).

## Docs

README "What's in here": add a **Pollen collections** bullet and update the
Seed-production bullet to mention the pollen link.
