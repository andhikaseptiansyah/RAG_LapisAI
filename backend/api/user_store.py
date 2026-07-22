import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from api.storage_paths import USER_STORE_FILE

USER_STORE_LOCK = threading.RLock()
PASSWORD_ITERATIONS = 210_000
USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{3,32}$")
MANAGEABLE_ROLES = {"user", "staff"}
VALID_ROLES = {"user", "staff", "admin"}


class UserStoreError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_username(username: str | None) -> str:
    return (username or "").strip().lower()


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, digest_hex = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def _build_user(
    *,
    user_id: str,
    username: str,
    name: str,
    role: str,
    password: str,
) -> dict[str, Any]:
    timestamp = _now_iso()
    return {
        "id": user_id,
        "username": normalize_username(username),
        "name": name.strip(),
        "role": role,
        "password_hash": _hash_password(password),
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def _default_users() -> list[dict[str, Any]]:
    """Create only the bootstrap administrator for a new installation."""
    username = normalize_username(os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin"))
    if not USERNAME_PATTERN.fullmatch(username):
        username = "admin"

    name = " ".join(os.getenv("BOOTSTRAP_ADMIN_NAME", "Administrator").split())
    if len(name) < 2 or len(name) > 80:
        name = "Administrator"

    configured_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    password = configured_password or secrets.token_urlsafe(18)

    if not configured_password:
        print(
            "[AUTH] BOOTSTRAP_ADMIN_PASSWORD is not configured. "
            f"Initial administrator password for username '{username}': {password}"
        )

    return [
        _build_user(
            user_id="dev-admin",
            username=username,
            name=name,
            role="admin",
            password=password,
        )
    ]


def _write_users_unlocked(users: list[dict[str, Any]]) -> None:
    USER_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = USER_STORE_FILE.with_suffix(".tmp")
    with temporary_file.open("w", encoding="utf-8") as file_handle:
        json.dump(users, file_handle, indent=2, ensure_ascii=False)
    os.chmod(temporary_file, 0o600)
    os.replace(temporary_file, USER_STORE_FILE)


def _ensure_store_unlocked() -> None:
    if USER_STORE_FILE.exists():
        return
    _write_users_unlocked(_default_users())


def read_users() -> list[dict[str, Any]]:
    with USER_STORE_LOCK:
        _ensure_store_unlocked()
        try:
            with USER_STORE_FILE.open("r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("The account store could not be read.") from exc

        if not isinstance(data, list):
            raise RuntimeError("The account store format is invalid.")

        return [user for user in data if isinstance(user, dict)]


def public_user(user: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(user.get("id") or ""),
        "username": str(user.get("username") or ""),
        "name": str(user.get("name") or ""),
        "role": str(user.get("role") or "user"),
    }


def get_user_by_username(username: str | None) -> dict[str, Any] | None:
    normalized = normalize_username(username)
    return next(
        (
            user
            for user in read_users()
            if normalize_username(str(user.get("username") or "")) == normalized
        ),
        None,
    )


def get_user_by_id(user_id: str | None) -> dict[str, Any] | None:
    clean_user_id = str(user_id or "").strip()
    return next(
        (
            user
            for user in read_users()
            if str(user.get("id") or "") == clean_user_id
        ),
        None,
    )


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    user = get_user_by_username(username)
    if not user:
        return None
    if not _verify_password(password, str(user.get("password_hash") or "")):
        return None
    return user


def _validate_username(username: str) -> str:
    normalized = normalize_username(username)
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise UserStoreError(
            "Username must contain 3-32 lowercase letters, numbers, periods, underscores, or hyphens."
        )
    return normalized


def _validate_name(name: str) -> str:
    clean_name = " ".join((name or "").split())
    if len(clean_name) < 2 or len(clean_name) > 80:
        raise UserStoreError("Name must contain 2-80 characters.")
    return clean_name


def _validate_password(password: str) -> str:
    clean_password = password or ""
    if len(clean_password) < 6:
        raise UserStoreError("Password must contain at least 6 characters.")
    if len(clean_password) > 128:
        raise UserStoreError("Password cannot exceed 128 characters.")
    return clean_password


def _validate_role(role: str, *, manageable_only: bool = False) -> str:
    clean_role = str(role or "").strip().lower()
    allowed = MANAGEABLE_ROLES if manageable_only else VALID_ROLES
    if clean_role not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise UserStoreError(f"Role must be one of: {allowed_text}.")
    return clean_role


def create_managed_user(
    username: str,
    name: str,
    password: str,
    role: str = "staff",
) -> dict[str, Any]:
    normalized_username = _validate_username(username)
    clean_name = _validate_name(name)
    clean_password = _validate_password(password)
    clean_role = _validate_role(role, manageable_only=True)

    with USER_STORE_LOCK:
        users = read_users()
        if any(
            normalize_username(str(user.get("username") or "")) == normalized_username
            for user in users
        ):
            raise UserStoreError("Username is already in use.")

        user = _build_user(
            user_id=f"{clean_role}-{uuid.uuid4().hex}",
            username=normalized_username,
            name=clean_name,
            role=clean_role,
            password=clean_password,
        )
        users.append(user)
        _write_users_unlocked(users)
        return user


def create_staff_user(username: str, name: str, password: str) -> dict[str, Any]:
    """Compatibility wrapper for older imports."""
    return create_managed_user(username, name, password, role="staff")


def update_user(
    user_id: str,
    *,
    username: str | None = None,
    name: str | None = None,
    role: str | None = None,
) -> dict[str, Any] | None:
    with USER_STORE_LOCK:
        users = read_users()
        target_index = next(
            (
                index
                for index, user in enumerate(users)
                if str(user.get("id") or "") == user_id
            ),
            None,
        )
        if target_index is None:
            return None

        current = users[target_index]
        updated = dict(current)

        if username is not None:
            normalized_username = _validate_username(username)
            duplicate = any(
                index != target_index
                and normalize_username(str(user.get("username") or "")) == normalized_username
                for index, user in enumerate(users)
            )
            if duplicate:
                raise UserStoreError("Username is already in use.")
            updated["username"] = normalized_username

        if name is not None:
            updated["name"] = _validate_name(name)

        if role is not None:
            updated["role"] = _validate_role(role, manageable_only=True)

        updated["updated_at"] = _now_iso()
        users[target_index] = updated
        _write_users_unlocked(users)
        return updated


def update_user_password(user_id: str, password: str) -> dict[str, Any] | None:
    clean_password = _validate_password(password)

    with USER_STORE_LOCK:
        users = read_users()
        target_index = next(
            (
                index
                for index, user in enumerate(users)
                if str(user.get("id") or "") == user_id
            ),
            None,
        )
        if target_index is None:
            return None

        updated_user = {
            **users[target_index],
            "password_hash": _hash_password(clean_password),
            "updated_at": _now_iso(),
        }
        users[target_index] = updated_user
        _write_users_unlocked(users)
        return updated_user


def delete_user(user_id: str) -> dict[str, Any] | None:
    with USER_STORE_LOCK:
        users = read_users()
        target = next(
            (
                user
                for user in users
                if str(user.get("id") or "") == user_id
            ),
            None,
        )
        if not target:
            return None

        remaining = [
            user
            for user in users
            if str(user.get("id") or "") != user_id
        ]
        _write_users_unlocked(remaining)
        return target
