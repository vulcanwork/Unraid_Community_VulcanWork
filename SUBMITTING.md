# Getting SeedBreed into Unraid Community Applications

Everything in this folder is ready to drop into your
`vulcanwork/Unraid_Community_VulcanWork` repo. Here's the path from here to
a working CA listing.

## 1. Copy these files into your repo

Copy the contents of this folder (`seedbreed/`, `templates/`, `icons/`,
`.github/workflows/`) into the root of `Unraid_Community_VulcanWork`. If any
of those top-level folders already exist in the repo (e.g. from a previous
app), merge rather than overwrite.

```
Unraid_Community_VulcanWork/
├── seedbreed/                          <- app source + Dockerfile (build context)
├── templates/seedbreed.xml             <- the Unraid CA template
├── icons/seedbreed.png                 <- template icon
└── .github/workflows/
    └── docker-publish-seedbreed.yml    <- builds & pushes the image on push
```

Commit and push to `main`.

## 2. Let GitHub Actions build the image

The workflow triggers automatically on a push to `main` that touches
`seedbreed/**`, and pushes `ghcr.io/vulcanwork/seedbreed:latest`. Watch it
run under the repo's **Actions** tab. It needs no secrets — it uses the
built-in `GITHUB_TOKEN`.

**Make the package public** (one-time, after the first successful run):
GitHub → your profile → **Packages** → `seedbreed` → **Package settings** →
**Change visibility** → Public. GHCR packages default to private even when
the repo is public, and Unraid can't pull a private image without extra
registry auth wired into every user's install.

## 3. Test the image yourself before anyone else does

```bash
docker run -d --name seedbreed-check -p 18080:80 \
  -e SEEDBREED_AUTH_PASSWORD=testpass \
  ghcr.io/vulcanwork/seedbreed:latest
curl http://localhost:18080/api/health
# open http://localhost:18080 in a browser, log in, add a check-in with a photo
docker rm -f seedbreed-check
```

(I already built and smoke-tested this exact Dockerfile locally — health
check, login, dashboard, and static assets all worked — but that was against
the source, not the pushed GHCR image, so it's worth a second pass once the
image is public.)

## 4. Test the template in Unraid itself

On your Unraid box: **Docker** tab → **Add Container** → toggle
**Template repositories** (or Community Applications → gear icon →
**Template Repositories**) → add:

```
https://github.com/vulcanwork/Unraid_Community_VulcanWork
```

Then in **Add Container**, pick **SeedBreed** from the dropdown of templates
from that repo (or browse to it directly via
`https://raw.githubusercontent.com/vulcanwork/Unraid_Community_VulcanWork/main/templates/seedbreed.xml`
using CA's "Request template" / manual-add-by-URL option). Fill in the port,
appdata paths, and a real password, apply, and confirm it comes up the same
way the local test did.

This step alone — adding your repo URL as a template repository — already
makes SeedBreed installable by anyone who adds that same URL, without
needing to be in the default CA search results.

## 5. Get listed in default Community Applications search

To show up when someone searches Community Applications without adding your
repo manually, the template needs to be picked up into CA's default feed.
The current mechanism (double-check this is still accurate, since Squid/CA
tweak the process occasionally):

- Post in the **Community Applications** feedback/support thread on the
  [Unraid forums](https://forums.unraid.net/) (search "Community
  Applications" under Plugin Support), linking your repo and template, and
  ask for it to be added to the default list.
- Make sure the template passes CA's own validator first — install
  **Template Repositories** in CA settings, add your repo, install
  SeedBreed from it, and confirm CA doesn't flag any schema issues (it
  validates `Config` entries, required fields like `Repository`/`Registry`,
  and icon reachability).

Until that request is picked up, the template is fully usable via the
manual template-repository route from step 4.

## Notes on what's already handled

- **Single container.** Community Apps templates point at one image, so
  the FastAPI backend and the nginx-served React frontend are combined into
  one image (`seedbreed/Dockerfile`), run together via `supervisord`. Locally
  you still get a `docker-compose.yml` for convenience, but it's one service.
- **No secrets baked in.** Default auth is `admin` / `changeme`, called out
  in both the template (`Auth Password` field, masked) and the README —
  same pattern Unraid CA uses for things like Nextcloud/Portainer.
- **Seed data is generic.** The one demo grow that ships on first boot uses
  placeholder strain names — nothing from the original personal instance
  made it into this copy.
- **Branding kept.** The VulcanWork logo/sidebar credit stayed as-is per
  your call — only the personal grow data and real credentials were
  stripped.
