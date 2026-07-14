import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

LOG_FILE = "./query_logs.json"
LEGACY_ADMIN_USER_ID = "dev-admin"


def get_logs(user_id: str | None = None, include_all: bool = False) -> list[dict[str, Any]]:
    if not os.path.exists(LOG_FILE):
        return []

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            logs = data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []

    if include_all:
        return logs

    if not user_id:
        return []

    # Log lama yang belum punya user_id dianggap milik admin/legacy.
    return [log for log in logs if str(log.get("user_id") or LEGACY_ADMIN_USER_ID) == user_id]


def write_logs(logs: list[dict[str, Any]]) -> None:
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)


def save_log(
    question: str,
    answer: str,
    sources: list[dict[str, Any]],
    latency_ms: float,
    confidence: float | None = None,
    user_id: str | None = None,
    user_name: str | None = None,
    user_role: str | None = None,
) -> dict[str, Any]:
    logs = get_logs(include_all=True)

    log_item = {
        "id": str(uuid.uuid4()),
        "user_id": user_id or LEGACY_ADMIN_USER_ID,
        "user_name": user_name or "User",
        "user_role": user_role or "staff",
        "question": question,
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "latency_ms": round(latency_ms, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    logs.append(log_item)
    write_logs(logs)
    return log_item


def delete_log(log_id: str, user_id: str | None = None, include_all: bool = False) -> bool:
    logs = get_logs(include_all=True)
    remaining = []
    deleted = False

    for log in logs:
        owner_id = str(log.get("user_id") or LEGACY_ADMIN_USER_ID)
        can_delete = include_all or (user_id is not None and owner_id == user_id)
        if log.get("id") == log_id and can_delete:
            deleted = True
            continue
        remaining.append(log)

    if not deleted:
        return False

    write_logs(remaining)
    return True
