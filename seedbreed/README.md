# SeedBreed

A self-hosted grow journal + genetics tracker. Log check-ins with photos,
compare side-by-side groups (natural vs. chemical, indoor vs. outdoor,
whatever), and trace every seed backward to its parents and forward to
whatever it produces.

Stack: FastAPI + SQLite + React, packaged as **one container** (nginx serves
the frontend and reverse-proxies the API to a FastAPI backend running
alongside it under supervisord). Data lives in two host paths — `/data` and
`/photos` — so it survives container rebuilds/updates and is easy to back up.

---

## What's in here

- **Grows** — a growing cycle. Each grow has one or more *groups* (the
  comparison axis).
- **Plants** — individual plants linked to a seed, a grow, and a group.
- **Check-ins** — dated observations with optional height, notes, and photos.
  Photos are auto-rotated and resized on upload so phone uploads stay sane.
- **Fertilizer events** — every feeding logged with product, amount, stage.
- **Harvests** — per-plant yield records (wet/dry weight, quality notes).
- **Strains** — your library, with parent A / parent B links for lineage.
- **Seeds** — every seed batch with an origin (purchased, gifted, produced).
- **Seed production events** — log when a plant throws seeds (intentional
  cross, accidental pollination, hermie). If you name the cross, it auto-
  creates a new strain with both parents linked and adds a seed batch with
  `origin=produced` pointing back to the event — closing the lineage loop.

A fresh install seeds one example grow (two strains, two comparison groups,
four plants) so the UI isn't empty on first boot. Edit or delete it once
you're logging your own.

---

## Quick start (Docker Compose)

```bash
cp .env.example .env        # then edit the password + port
docker compose up -d --build
```

Open **http://localhost:8080** (or whatever `SEEDBREED_PORT` you set).

## Quick start (Unraid)

Install **SeedBreed** from Community Applications, or add
`https://raw.githubusercontent.com/vulcanwork/Unraid_Community_VulcanWork/main/templates/seedbreed.xml`
as a template repo and install it from there. Set the WebUI port and the
`/data` / `/photos` appdata paths, set a real `SEEDBREED_AUTH_PASSWORD`, and
apply.

---

## Logging in / making changes

The whole site is **readable by anyone** — every page, every record, every
photo. **Making changes requires logging in.** Adding, editing, or deleting
anything (and uploading photos) is blocked until you log in with the operator
credential; the backend enforces this on every write, not just the UI.

Default credential (**change before exposing the site**):

```
username: admin
password: changeme
```

Set `SEEDBREED_AUTH_USERNAME` / `SEEDBREED_AUTH_PASSWORD` (env vars, `.env`,
or the Unraid template fields) and restart.

How it works: a successful login mints a signed token (valid 30 days, tunable
via `SEEDBREED_TOKEN_TTL`) that the browser stores and sends with each write.
Tokens are signed with a key kept at `/data/.secret_key` (auto-generated on
first boot, or set `SEEDBREED_SECRET_KEY` yourself). Deleting that file logs
everyone out. There's no separate user database — it's a single shared
operator login, which is the right fit for a personal grow journal.

---

## Backing up

Everything that matters lives in the two mounted paths:

- `/data/seedbreed.db` — the SQLite database
- `/photos/*` — uploaded images

Copy those two folders anywhere safe. To restore on a new host, drop them
in place before bringing the container up for the first time.

## Resetting / reseeding

The seed script is idempotent — it only adds what isn't there. To do a full
reset, stop the container and delete `/data/seedbreed.db`. Clear `/photos/`
too if you want a clean slate, then start the container again.

---

## Layout

```
seedbreed/
├── Dockerfile           multi-stage build: React -> static, + FastAPI, one image
├── nginx.conf            serves the frontend, proxies /api and /photos
├── supervisord.conf       runs nginx + uvicorn together in the container
├── docker-compose.yml     for local/non-Unraid use
├── .env.example
├── backend/               FastAPI app
│   └── app/
│       ├── main.py            all API routes + auth middleware
│       ├── models.py          database tables
│       ├── schemas.py         API input/output shapes
│       ├── database.py        SQLite connection + tiny migrations
│       ├── auth.py            single shared-login, signed tokens
│       └── seed_data.py       example grow seeded on first boot
└── frontend/               React + Vite
    └── src/
        ├── App.jsx
        ├── api.js
        ├── styles.css
        └── pages/
```

---

## Working on it locally (without Docker)

Backend:
```bash
cd backend
pip install -r requirements.txt
SEEDBREED_DATA_DIR=./data SEEDBREED_PHOTOS_DIR=./photos python -m app.seed_data
SEEDBREED_DATA_DIR=./data SEEDBREED_PHOTOS_DIR=./photos uvicorn app.main:app --reload --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api` and `/photos` to `localhost:8000`, so go to
`http://localhost:5173`.
