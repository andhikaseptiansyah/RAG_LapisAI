import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from api.storage_paths import QUERY_LOG_FILE

LOG_FILE = QUERY_LOG_FILE
LEGACY_ADMIN_USER_ID = "dev-admin"
LOG_LOCK = threading.RLock()
VALID_QUERY_LOG_STATUSES = {
    "ANSWERED",
    "NO_REFERENCE",
    "NOT_FOUND",
}

NO_REFERENCE_PREFIXES = (
    "informasi tersebut tidak ditemukan",
    "informasi tidak ditemukan",
    "tidak ditemukan dengan bukti",
    "belum ditemukan di dokumen",
    "belum ketemu di dokumen",
    "tidak ada informasi yang cukup",
    "konteks tidak cukup",
    "the requested information was not found",
    "the information was not found",
    "i could not find",
    "could not find the requested information",
    "no sufficient information was found",
    "insufficient context",
    "insufficient evidence",
)

NO_REFERENCE_MARKERS = (
    "tidak disebutkan dalam konteks dokumen",
    "tidak disebutkan dalam dokumen",
    "tidak tercantum dalam dokumen",
    "tidak tersedia pada dokumen",
    "not specified in the document",
    "not specified in the provided context",
    "not stated in the document",
    "not available in the document",
)


def _is_no_reference_answer(answer: str | None) -> bool:
    normalized = " ".join(str(answer or "").casefold().split())
    return normalized.startswith(NO_REFERENCE_PREFIXES) or any(
        marker in normalized for marker in NO_REFERENCE_MARKERS
    )


def resolve_query_log_status(
    answer: str | None,
    sources: list[dict[str, Any]] | None,
    status: str | None = None,
) -> str:
    """Resolve the dashboard status from the actual chat outcome.

    ANSWERED: a non-empty answer is backed by at least one document source.
    NO_REFERENCE: a non-empty answer exists, but no document source supports it.
    NOT_FOUND: no answer was produced, the request failed, or the user stopped it.
    """
    explicit_status = str(status or "").strip().upper()
    if explicit_status in VALID_QUERY_LOG_STATUSES:
        return explicit_status

    if not str(answer or "").strip():
        return "NOT_FOUND"

    if _is_no_reference_answer(answer):
        return "NO_REFERENCE"

    if sources:
        return "ANSWERED"

    return "NO_REFERENCE"


def get_logs(user_id: str | None = None, include_all: bool = False) -> list[dict[str, Any]]:
    with LOG_LOCK:
        if not LOG_FILE.exists():
            return []

        try:
            with LOG_FILE.open("r", encoding="utf-8") as f:
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
    with LOG_LOCK:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = LOG_FILE.with_suffix(".tmp")
        with temporary_file.open("w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
        os.chmod(temporary_file, 0o600)
        os.replace(temporary_file, LOG_FILE)


def save_log(
    question: str,
    answer: str,
    sources: list[dict[str, Any]],
    latency_ms: float,
    confidence: float | None = None,
    user_id: str | None = None,
    user_name: str | None = None,
    user_role: str | None = None,
    status: str | None = None,
    query_id: str | None = None,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    resolved_status = resolve_query_log_status(answer, sources, status)
    resolved_query_id = str(query_id or uuid.uuid4())

    with LOG_LOCK:
        logs = get_logs(include_all=True)
        existing_index = next(
            (
                index
                for index, item in enumerate(logs)
                if str(item.get("id") or "") == resolved_query_id
            ),
            None,
        )
        existing = logs[existing_index] if existing_index is not None else {}

        if existing and user_id:
            existing_owner = str(existing.get("user_id") or LEGACY_ADMIN_USER_ID)
            if existing_owner != user_id:
                resolved_query_id = str(uuid.uuid4())
                existing_index = None
                existing = {}

        # A user-stopped request is terminal. A late backend completion must not
        # silently turn it back into ANSWERED or NO_REFERENCE.
        if (
            existing
            and existing.get("status") == "NOT_FOUND"
            and existing.get("failure_reason") == "USER_STOPPED"
            and resolved_status != "NOT_FOUND"
        ):
            return existing

        log_item = {
            **existing,
            "id": resolved_query_id,
            "user_id": user_id or existing.get("user_id") or LEGACY_ADMIN_USER_ID,
            "user_name": user_name or existing.get("user_name") or "User",
            "user_role": user_role or existing.get("user_role") or "staff",
            "question": question,
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
            "latency_ms": round(latency_ms, 2),
            "status": resolved_status,
            "timestamp": existing.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        }

        if failure_reason:
            log_item["failure_reason"] = str(failure_reason).strip().upper()
        else:
            log_item.pop("failure_reason", None)

        if existing_index is None:
            logs.append(log_item)
        else:
            logs[existing_index] = log_item

        write_logs(logs)
        return log_item


def delete_log(log_id: str, user_id: str | None = None, include_all: bool = False) -> bool:
    with LOG_LOCK:
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


def _normalize_question(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _parse_timestamp(value: Any) -> datetime | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None

    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _message_query_id(message: dict[str, Any]) -> str:
    metadata = message.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    return str(
        message.get("query_id")
        or message.get("queryId")
        or metadata.get("query_id")
        or metadata.get("queryId")
        or ""
    ).strip()


def delete_logs_for_conversations(
    conversations: list[dict[str, Any]],
    *,
    user_id: str | None = None,
    include_all: bool = False,
) -> list[str]:
    """Delete query logs belonging to deleted conversation turns.

    New conversation messages carry their query-log ID explicitly. Older
    records are linked by owner, normalized question, and the closest
    timestamp so deleting a history entry also updates dashboard totals
    without deleting another user's similarly worded query.
    """
    explicit_query_ids: set[str] = set()
    legacy_turns: list[tuple[str, str, datetime | None]] = []

    for conversation in conversations:
        owner_id = str(conversation.get("user_id") or LEGACY_ADMIN_USER_ID)
        if not include_all and (not user_id or owner_id != user_id):
            continue

        for raw_message in conversation.get("messages") or []:
            if not isinstance(raw_message, dict):
                continue

            query_id = _message_query_id(raw_message)
            if query_id:
                explicit_query_ids.add(query_id)

            if raw_message.get("role") != "user" or query_id:
                continue

            question = _normalize_question(raw_message.get("content"))
            if question:
                legacy_turns.append(
                    (
                        owner_id,
                        question,
                        _parse_timestamp(raw_message.get("created_at")),
                    )
                )

    with LOG_LOCK:
        logs = get_logs(include_all=True)
        deleted_ids: set[str] = set()

        def can_delete(log: dict[str, Any]) -> bool:
            owner_id = str(log.get("user_id") or LEGACY_ADMIN_USER_ID)
            return include_all or (user_id is not None and owner_id == user_id)

        for log in logs:
            log_id = str(log.get("id") or "")
            if log_id in explicit_query_ids and can_delete(log):
                deleted_ids.add(log_id)

        # Backward-compatible cleanup for conversations created before query IDs
        # were stored in message metadata. Match at most one log per user turn.
        for owner_id, question, message_time in legacy_turns:
            candidates: list[tuple[float, str]] = []
            for log in logs:
                log_id = str(log.get("id") or "")
                log_owner_id = str(log.get("user_id") or LEGACY_ADMIN_USER_ID)
                if (
                    log_id in deleted_ids
                    or log_owner_id != owner_id
                    or not can_delete(log)
                    or _normalize_question(log.get("question")) != question
                ):
                    continue

                log_time = _parse_timestamp(log.get("timestamp"))
                if message_time is not None and log_time is not None:
                    delta_seconds = abs((log_time - message_time).total_seconds())
                    if delta_seconds > 300:
                        continue
                else:
                    delta_seconds = float("inf")

                candidates.append((delta_seconds, log_id))

            if candidates:
                candidates.sort(key=lambda item: item[0])
                deleted_ids.add(candidates[0][1])

        if not deleted_ids:
            return []

        remaining = [
            log
            for log in logs
            if str(log.get("id") or "") not in deleted_ids
        ]
        write_logs(remaining)
        return sorted(deleted_ids)
