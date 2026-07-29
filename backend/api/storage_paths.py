"""Canonical backend storage paths and one-time legacy-data migration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

USER_STORE_FILE = BACKEND_DIR / "users_store.json"
DOCUMENT_STORE_FILE = BACKEND_DIR / "documents_store.json"
CONVERSATION_STORE_FILE = BACKEND_DIR / "conversations_store.json"
QUERY_LOG_FILE = BACKEND_DIR / "query_logs.json"
AUTH_SECRET_FILE = BACKEND_DIR / ".auth_secret"

LEGACY_CONVERSATION_STORE_FILE = PROJECT_ROOT / "conversations_store.json"
LEGACY_QUERY_LOG_FILE = PROJECT_ROOT / "query_logs.json"


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _write_json_list(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(items, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.chmod(temporary_path, 0o600)
    os.replace(temporary_path, path)


def _merge_by_id(
    canonical_items: list[dict[str, Any]],
    legacy_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge list stores without duplicating records that share an ID."""
    merged = list(canonical_items)
    known_ids = {
        str(item.get("id") or "").strip()
        for item in canonical_items
        if str(item.get("id") or "").strip()
    }

    for item in legacy_items:
        item_id = str(item.get("id") or "").strip()
        if item_id and item_id in known_ids:
            continue
        merged.append(item)
        if item_id:
            known_ids.add(item_id)

    return merged


def migrate_legacy_storage() -> dict[str, int]:
    """Move root-level JSON stores into the canonical backend directory.

    Existing canonical records are retained. Legacy records with a different ID
    are appended. A legacy file is removed only after the canonical write
    succeeds.
    """
    migrated_counts: dict[str, int] = {}
    migrations = (
        ("conversations", CONVERSATION_STORE_FILE, LEGACY_CONVERSATION_STORE_FILE),
        ("query_logs", QUERY_LOG_FILE, LEGACY_QUERY_LOG_FILE),
    )

    for label, canonical_path, legacy_path in migrations:
        if canonical_path.resolve() == legacy_path.resolve() or not legacy_path.exists():
            continue

        canonical_items = _read_json_list(canonical_path)
        legacy_items = _read_json_list(legacy_path)
        merged_items = _merge_by_id(canonical_items, legacy_items)
        _write_json_list(canonical_path, merged_items)
        legacy_path.unlink(missing_ok=True)
        migrated_counts[label] = max(0, len(merged_items) - len(canonical_items))

    return migrated_counts
