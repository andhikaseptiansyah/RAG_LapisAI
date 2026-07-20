import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from api.user_store import get_user_by_id, normalize_username

TOKEN_PREFIX = "lapisai-v1"
TOKEN_TTL_SECONDS = int(os.getenv("LAPISAI_AUTH_TOKEN_TTL_SECONDS", "43200"))
AUTH_SECRET_FILE = Path(__file__).resolve().parent.parent / ".auth_secret"
SECRET_LOCK = threading.RLock()


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _load_secret() -> bytes:
    configured_secret = os.getenv("LAPISAI_AUTH_SECRET", "").strip()
    if configured_secret:
        return configured_secret.encode("utf-8")

    with SECRET_LOCK:
        if AUTH_SECRET_FILE.exists():
            secret_text = AUTH_SECRET_FILE.read_text(encoding="utf-8").strip()
            if secret_text:
                return bytes.fromhex(secret_text)

        secret = secrets.token_bytes(32)
        AUTH_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = AUTH_SECRET_FILE.with_suffix(".tmp")
        temporary_file.write_text(secret.hex(), encoding="utf-8")
        os.chmod(temporary_file, 0o600)
        os.replace(temporary_file, AUTH_SECRET_FILE)
        return secret


def create_auth_token(user: dict[str, Any]) -> str:
    issued_at = int(time.time())
    payload = {
        "uid": str(user.get("id") or ""),
        "usr": normalize_username(str(user.get("username") or "")),
        "ver": str(user.get("updated_at") or ""),
        "iat": issued_at,
        "exp": issued_at + TOKEN_TTL_SECONDS,
    }
    payload_segment = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    unsigned_token = f"{TOKEN_PREFIX}.{payload_segment}"
    signature = hmac.new(
        _load_secret(),
        unsigned_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{unsigned_token}.{_base64url_encode(signature)}"


def resolve_auth_token(token: str | None) -> dict[str, Any] | None:
    clean_token = (token or "").strip()
    try:
        prefix, payload_segment, signature_segment = clean_token.split(".", 2)
    except ValueError:
        return None

    if prefix != TOKEN_PREFIX:
        return None

    unsigned_token = f"{prefix}.{payload_segment}"
    expected_signature = hmac.new(
        _load_secret(),
        unsigned_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    try:
        provided_signature = _base64url_decode(signature_segment)
    except (ValueError, TypeError):
        return None

    if not hmac.compare_digest(expected_signature, provided_signature):
        return None

    try:
        payload = json.loads(_base64url_decode(payload_segment).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    try:
        expires_at = int(payload.get("exp") or 0)
    except (TypeError, ValueError):
        return None

    if expires_at <= int(time.time()):
        return None

    user = get_user_by_id(str(payload.get("uid") or ""))
    if not user:
        return None

    if normalize_username(str(user.get("username") or "")) != normalize_username(
        str(payload.get("usr") or "")
    ):
        return None

    # Password resets update this version and immediately invalidate older sessions.
    if str(user.get("updated_at") or "") != str(payload.get("ver") or ""):
        return None

    return user
