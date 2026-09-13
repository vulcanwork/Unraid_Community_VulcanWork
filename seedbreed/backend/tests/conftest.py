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
