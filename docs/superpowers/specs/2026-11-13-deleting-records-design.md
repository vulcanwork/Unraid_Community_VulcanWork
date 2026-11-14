# Deleting strains, seeds and breeding events — design

**Date:** 2026-11-13
**Scope:** SeedBreed (`seedbreed/`)

## Intent and why

Strains, seed batches and breeding events can be created and edited but never
deleted. The immediate consequence is that the example records a fresh install
seeds (`Example Strain A`/`B` and their seed batches) are permanent — the
README tells you to "edit or delete it once you're logging your own", and you
can't. The same gap bites any real mistyped record.

Deletes already exist for grows, plants, check-ins, photos, fertilizer events
and pollen. This closes the gap for the three objects that have a UI and don't.

## Goals

- Delete a strain, a seed batch, or a breeding event from the page that lists it.
- When other records depend on it, say so plainly and name them, rather than
  failing with a database error or silently orphaning data.
- Offer a one-click way through that block when the user means it.
- A fresh install's example data can be cleared entirely through the UI.
- No delete anywhere in the app can leave a record pointing at something that
  no longer exists.

## Non-goals

- Harvests and Groups. Both lack a delete *and* an edit *and* any UI at all
  (harvest records are unused — plants carry a free-text `quantity_harvested`
  instead; groups are fixed when a grow is created). Giving them delete buttons
  means first giving them a UI. Explicitly out of scope, confirmed with the user.
- Reworking the existing deletes. Grow and plant delete each gain **one new
  guard** (below) and nothing else; pollen delete is untouched. No existing
  cascade behaviour, block message or route shape changes.
- Undo, soft-delete, or a trash can.
- A dedicated "reset example data" button. The three deletes plus the existing
  grow delete already clear a fresh install in three steps.

## Anti-goals

Things that would make this a failure even if it shipped working:

- A delete that reaches further than the dialog said it would.
- Any path where deleting a strain or seed silently destroys check-ins, photos
  or harvest history belonging to a grow.
- A plant left showing no genetics when the information was preservable.
- A block the user cannot get past without editing the database by hand.

## Constraints

- Existing house style: `main.py` is deliberately a single file; deletes return
  `{"ok": True, "id": N}`; blocks raise `HTTPException(400, "<sentence>")`.
- Writes are gated by the existing auth middleware on `/api/` — no per-route
  auth code. The middleware matches on `request.url.path`, which excludes the
  query string, so `?cascade=true` passes through unaffected.
- SQLite with `create_all()` plus the hand-rolled ALTER-if-missing step in
  `database.py`. **No schema change in this work**, so no migration.
- Foreign keys are not enforced by SQLite here (`PRAGMA foreign_keys` is never
  set), so orphaning is silent if the application doesn't prevent it. All
  guarding is application-level, as it already is elsewhere.
- No Node on the dev machine; the frontend is verified by review plus a
  `docker compose` build and a click-through on the running container.

## Approaches

Three ways to handle a delete whose target other records depend on:

1. **Block only.** Refuse with a message naming what's in the way; the user
   clears the dependents first. Matches the app today. Rejected on its own:
   it makes clearing the example data a chore and offers no way out when the
   user genuinely wants the whole line gone.
2. **Block, with a "Delete all" escape hatch that reaches one level.** The
   default is the refusal above, rendered as a dialog listing the blockers,
   with a second button that deletes the target plus its directly dependent
   records and unlinks the rest. **Chosen.**
3. **Full transitive cascade.** "Delete all" on a strain also removes the
   plants grown from it and their check-ins, photos, harvests, pollen and
   crosses. Rejected: one misclick destroys months of grow history, and the
   blast radius can't be stated honestly in a dialog.

A fourth option — adding the same escape hatch to the *existing* blocks on
grows, plants and pollen — was considered and rejected. It only saves a click,
and it would let someone wipe breeding history from the grow page. It is also
unnecessary: every existing block is caused by something being a parent in a
breeding event, and breeding events become deletable in this work, so there is
now a path through all of them.

The new pollen guard below follows the same reasoning and gets no escape hatch
either: the user clears the forward records by hand, in order.

## How it works

### Dependency map

What points *at* each of the three objects (all five foreign keys into these
tables; none enforced by SQLite):

| Target | Referenced by | Nullable? | On "Delete all" |
|---|---|---|---|
| Strain | `Seed.strain_id` | no | seed batch **deleted** |
| Strain | `Plant.strain_id` | yes | plant **unlinked**, kept |
| Strain | `Strain.parent_a_id` / `parent_b_id` | yes | child strain **unlinked**, kept |
| Seed | `Plant.seed_id` | yes | plant **unlinked**, kept |
| Breeding event | `Seed.produced_by_event_id` | yes | seed batch **deleted** |

Cascade is one level of deletion plus an unlink sweep. It can never reach a
check-in, photo, harvest, grow or pollen record.

### Blockers are found two levels deep

A seed batch deleted by a cascade may itself have plants pointing at it, and
those plants get unlinked. **The blocker list must include them**, or the
dialog under-reports what the button is about to do — the first anti-goal.

This is the normal case, not a corner one. `seed_data.py` creates the four
example plants with `seed_id` set and `strain_id` left empty, so
`Example Strain A` is reachable from its plants *only* through its seed batch.
A one-level query would report "1 seed batch" and silently clear `seed_id` on
two plants.

So the strain query is: its seed batches, **plus** plants linked to the strain
directly **or** to any of those batches, plus child strains. Plants reached by
both routes are deduplicated by id and reported as one entry — the action is
the same either way, and the user does not care which link caused it.

### Unlinking preserves genetics where it can

`_plant_strain_name` displays `plant.strain`, falling back to
`plant.seed.strain`. Clearing a plant's `seed_id` therefore blanks its
genetics in the UI — and no form in the frontend ever sets `seed_id`
(the API accepts it; nothing sends it), so the user cannot put it back.

Rule: **when a plant is unlinked from a seed batch, it inherits that batch's
`strain_id` onto its own `strain_id`, unless it already has one, or unless
that strain is itself being deleted in the same cascade.** The plant keeps
displaying its genetics. In the strain cascade the strain is going away
regardless, so there the plant is simply cleared; that loss is inherent.

### Deleting a cross: block only once its seeds are planted

`create_seed_production` creates a seed batch whenever the cross was named, so
treating that batch as an ordinary blocker would make *every* named cross
require the two-click "Delete all" path — including one logged by mistake a
minute ago.

Instead: the produced batch exists only because the event does, so it goes
with the event on a plain delete, and the confirm text says so. Once plants
have been grown from that batch, it is real data — then the event blocks
normally and the dialog lists both the batch and the plants.

- No plants use the produced batch → plain delete removes batch and event.
- Plants use it → 409, listing the batch (`delete`) and the plants (`unlink`).
- `?cascade=true` → batch deleted, plants unlinked (inheriting the batch's
  strain, which survives), event deleted.

Two deliberate omissions:

- Deleting a breeding event does **not** delete the strain the event
  auto-created for a named cross. The strain is a named thing the user may
  still want; it can be deleted on its own from the Strains page.
- `SeedProductionEvent.new_strain_name` is free text, not a foreign key, so it
  never blocks a strain delete. A strain whose name appears there deletes
  normally.

### Closing the last orphan: pollen points at a plant nothing protects

Every foreign key in `models.py` was audited against every delete path. All
are covered — check-ins are detached from a deleted plant, harvests and photos
go with it, groups and fertilizer events go with the grow, breeding events
block on their parent plant and their pollen — with one exception:
`PollenCollection.source_plant_id`. Deleting a plant (or the grow containing
it) leaves pollen rows pointing at nothing, which the Pollen library then
renders as "Plant #N" via the fallbacks in `_pollen_to_out` / `_pollen_label`.

This was previously ruled "leave as-is" (2026-09-13); the user has since
reversed that and asked for it closed. The rule they gave: **if anything
forward of a record uses it, the record can't be deleted — clear the forward
records by hand first.**

So two existing routes each gain one guard, in the style of the guards already
there, returning the same 400-with-a-sentence they already use:

- `delete_plant` — blocked if any `PollenCollection.source_plant_id` is this
  plant.
- `delete_grow` — blocked if any plant in the grow has pollen collected from
  it, checked alongside the breeding-parent guard already in that route.

No escape hatch, and no dead end, because the chain unwinds in order and every
link is a button that exists once this work lands:

```
  breeding event  →  pollen record  →  plant  →  grow
     (new)            (exists)        (exists)  (exists)
```

### API

Three new routes, following the shape of `delete_pollen`:

- `DELETE /api/strains/{strain_id}`
- `DELETE /api/seeds/{seed_id}`
- `DELETE /api/seed-production/{event_id}`

Each takes an optional `?cascade=true`. Without it, a target with blockers is
refused. With it, the rules above are applied and the target is deleted.
Success returns `{"ok": true, "id": N}`; a missing target returns 404, as
elsewhere.

**The refusal is 409, not 400,** and its `detail` is an object rather than a
string, so the UI can render the dialog and know a cascade is available. 400
is left alone so the existing string-detail blocks keep working untouched:

```json
{
  "detail": {
    "error": "delete_blocked",
    "message": "Other records use this strain.",
    "blocked_by": [
      { "label": "1 seed batch — Example Strain A (2 seeds)",            "action": "delete" },
      { "label": "4 plants — Strain A (G1 left), Strain A (G2 left) and 2 more", "action": "unlink" },
      { "label": "parent of \"Lime-Chata\"",                              "action": "unlink" }
    ]
  }
}
```

`label` is a finished human phrase built by the backend — count, then up to
three names, then "and N more". The UI prints it verbatim and never does
arithmetic on it, so naming records costs no schema change. `action` is
`delete` or `unlink`, which is what lets the dialog say what "Delete all"
actually does. Order is stable: deletes first, then unlinks.

### Frontend

A new `frontend/src/components/DeleteButton.jsx` (first component outside
`pages/` — my call; three pages need identical behaviour and duplicating it
three ways is how the copies drift). Props: the API path, a human label, an
optional confirm override, and `onDeleted`.

Behaviour:

1. Renders the same `small-btn danger` button the other delete actions use.
2. Click → plain `confirm()`, matching every other delete in the app. Default
   text `Delete "<label>"?`; the breeding rows pass the override
   *"Delete this cross? The seed batch it created goes with it."*
3. `DELETE <path>` → on success, `onDeleted()`.
4. On a 409 `delete_blocked` → open the modal below.
5. Any other error → `alert(e.message)`, as elsewhere.

The modal uses the existing `.modal-backdrop` / `.modal` / `.modal-actions`
classes, so it inherits the app's look with no new CSS:

```
  Can't delete "Example Strain A"
  ────────────────────────────────────────────────
  These records use this strain:
    • 1 seed batch — Example Strain A (2 seeds)
                                      will be deleted
    • 4 plants — Strain A (G1 left),
      Strain A (G2 left) and 2 more   will be unlinked
    • parent of "Lime-Chata"          will be unlinked

  Remove them first, or delete the strain and
  everything listed above.
                         [ Cancel ]  [ Delete all ]
```

"Delete all" re-issues the request with `?cascade=true`, then `onDeleted()`.

Wired into three places, one line each: `Strains.jsx` and `Seeds.jsx` row
actions (beside the existing Edit), and the seed-production rows in
`Breeding.jsx` (beside Edit — the pollen rows there already have their own
Delete and are not touched).

`StrainDetail.jsx` deliberately gets no delete button: deleting from a detail
page means handling the navigate-away, and the list page already covers it.

### One change to `api.js`

`req()` currently turns every failure into
`new Error("<status> <statusText>: <body text>")`. It needs to parse a JSON
error body and:

- when `detail` is an object, hang it off the error as `err.detail` so the
  component can read `blocked_by`;
- when `detail` is a plain string, use it as `err.message`.

The second half is a free fix for the existing blocks. Today every one of them
reaches the user as `alert()` showing
`400 Bad Request: {"detail":"Can't delete this plant: ..."}`; after this they
read as the sentence the backend wrote. `err.status` is already set and no
caller inspects `err.message`'s shape, so nothing else changes.

## Testing

Backend, in a new `seedbreed/backend/tests/test_deletes.py` (pytest harness
already exists; 27 tests pass today). Each of the three objects gets: delete
with no blockers succeeds; delete with blockers returns 409 carrying the
expected `blocked_by` labels and actions; `?cascade=true` deletes what the
rules say and unlinks what they say, with survivors asserted still present;
404 on a missing id; 401 for an unauthenticated caller.

The cases that actually matter, because they are where this breaks:

- **Two-level blockers.** A strain whose plants link to it only through its
  seed batch — exactly the `seed_data.py` shape. Assert the plants appear in
  `blocked_by` before any cascade runs.
- **Strain cascade.** Plants survive with both `seed_id` and `strain_id`
  cleared; child strains survive with the parent link nulled; check-ins,
  photos and the grow are untouched.
- **Strain inheritance exclusion.** Plants unlinked by a *strain* cascade do
  not inherit the strain that is being deleted.
- **Seed cascade.** A plant with no `strain_id` of its own inherits the
  batch's strain and still reports a `strain_name`.
- **Cross with unplanted seeds.** Plain delete succeeds and takes the produced
  batch; the auto-created strain survives.
- **Cross with planted seeds.** Plain delete 409s; cascade removes the batch,
  leaves the plant with the batch's strain inherited, and leaves the strain.
- **Pollen guard.** Deleting a plant that pollen was collected from is
  refused; so is deleting the grow that plant lives in. Deleting the pollen
  first lets both succeed. A plant with no pollen still deletes as it does
  today — the existing plant and grow delete tests must keep passing
  unchanged, which is the real check that the guard didn't overreach.
- **The chain unwinds.** One end-to-end test: cross → pollen → plant → grow,
  deleted in that order, each step succeeding only after the one before it.

Frontend is verified by review plus `docker compose up --build` and a
click-through: delete an unused strain, hit the block on a used one, then
clear the example data end to end.

## Left to the builder

- Exact wording of each `label` and `message`, within the shape above, and the
  name cap (three is a suggestion, not a requirement).
- Whether the blocker queries live in one helper per object or one generic
  helper driven by a table — either is fine at three objects.
- Internal structure of `DeleteButton.jsx` (one component, or a component plus
  a small hook).
