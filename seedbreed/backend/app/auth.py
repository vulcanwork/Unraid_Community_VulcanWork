"""Authentication — single shared credential, signed bearer tokens.

The whole site is readable without authentication. Any write (POST/PATCH/PUT/
DELETE) requires a valid token, enforced by a middleware in main.py.

There is exactly one operator credential (username + password), set via env.
Tokens are HMAC-signed with the stdlib so there are no extra dependencies and
nothing to store server-side — the signature proves the token was minted here.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional

# Operator credential. Override these in the environment (docker-compose / .env).
USERNAME = os.environ.get("SEEDBREED_AUTH_USERNAME", "admin")
PASSWORD = os.environ.get("SEEDBREED_AUTH_PASSWORD", "changeme")

# How long a login lasts before the token expires (seconds). Default 30 days.
TOKEN_TTL = int(os.environ.get("SEEDBREED_TOKEN_TTL", str(60 * 60 * 24 * 30)))

DATA_DIR = os.environ.get("SEEDBREED_DATA_DIR", "/data")


def _load_secret_key() -> bytes:
    """The HMAC signing key.

    Prefer SEEDBREED_SECRET_KEY from the env. Otherwise generate one and
    persist it next to the database so existing logins survive a restart.
    """
    env = os.environ.get("SEEDBREED_SECRET_KEY")
    if env:
        return env.encode()
    path = os.path.join(DATA_DIR, ".secret_key")
    try:
        with open(path) as f:
            existing = f.read().strip()
            if existing:
                return existing.encode()
    except OSError:
        pass
    key = secrets.token_hex(32)
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(path, "w") as f:
            f.write(key)
        os.chmod(path, 0o600)
    except OSError:
        # Read-only data dir — fall back to an in-memory key. Tokens then
        # invalidate on restart, which only means re-logging in.
        pass
    return key.encode()


SECRET_KEY = _load_secret_key()


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(body: str) -> str:
    return _b64e(hmac.new(SECRET_KEY, body.encode(), hashlib.sha256).digest())


def check_credentials(username: str, password: str) -> bool:
    """Constant-time comparison against the configured operator credential."""
    user_ok = hmac.compare_digest(username or "", USERNAME)
    pass_ok = hmac.compare_digest(password or "", PASSWORD)
    return user_ok and pass_ok


def create_token(username: str) -> str:
    payload = {"sub": username, "exp": int(time.time()) + TOKEN_TTL}
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body}.{_sign(body)}"


def verify_token(token: Optional[str]) -> Optional[str]:
    """Return the username if the token is valid and unexpired, else None."""
    if not token or "." not in token:
        return None
    body, _, sig = token.partition(".")
    if not hmac.compare_digest(sig, _sign(body)):
        return None
    try:
        payload = json.loads(_b64d(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload.get("sub")


def bearer_from_header(authorization: Optional[str]) -> Optional[str]:
    """Pull the token out of an `Authorization: Bearer <token>` header."""
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None
