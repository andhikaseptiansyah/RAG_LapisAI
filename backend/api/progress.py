from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Literal

ProgressStatus = Literal["active", "completed", "skipped", "failed"]
ProgressCallback = Callable[[dict[str, Any]], None]

_LOCAL = threading.local()


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def current_progress_callback() -> ProgressCallback | None:
    return getattr(_LOCAL, "callback", None)


def emit_progress(
    step: str,
    status: ProgressStatus,
    title: str,
    *,
    detail: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a safe operational progress event for the active chat request.

    Events describe pipeline operations and aggregate results only. They must
    never contain prompts, model reasoning, embeddings, or hidden chain-of-thought.
    """
    callback = current_progress_callback()
    if callback is None:
        return

    event: dict[str, Any] = {
        "step": _clean_text(step),
        "status": status,
        "title": _clean_text(title),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    clean_detail = _clean_text(detail)
    if clean_detail:
        event["detail"] = clean_detail
    if metadata:
        event["metadata"] = metadata

    try:
        callback(event)
    except Exception as exc:  # Progress must never break the RAG pipeline.
        print(f"[CHAT_PROGRESS] callback failed: {exc}")


@contextmanager
def progress_scope(callback: ProgressCallback | None) -> Iterator[None]:
    previous = current_progress_callback()
    _LOCAL.callback = callback
    try:
        yield
    finally:
        _LOCAL.callback = previous
