from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


class ChatCancelled(RuntimeError):
    """Raised when a user or disconnected client cancels a chat request."""


@dataclass
class _ActiveQuery:
    user_id: str
    event: threading.Event
    created_at: float


_LOCK = threading.RLock()
_ACTIVE: dict[str, _ActiveQuery] = {}
_PENDING: dict[str, tuple[str, float]] = {}
_LOCAL = threading.local()
_PENDING_TTL_SECONDS = 120.0


def _clean(value: object) -> str:
    return str(value or "").strip()


def _purge_pending() -> None:
    cutoff = time.monotonic() - _PENDING_TTL_SECONDS
    stale = [key for key, (_, created_at) in _PENDING.items() if created_at < cutoff]
    for key in stale:
        _PENDING.pop(key, None)


def register_query(query_id: str, user_id: str) -> threading.Event:
    query_key = _clean(query_id)
    owner = _clean(user_id)
    if not query_key:
        raise ValueError("query_id wajib diisi")

    with _LOCK:
        _purge_pending()
        existing = _ACTIVE.get(query_key)
        if existing and existing.user_id == owner:
            return existing.event

        event = threading.Event()
        pending = _PENDING.pop(query_key, None)
        if pending and pending[0] == owner:
            event.set()

        _ACTIVE[query_key] = _ActiveQuery(
            user_id=owner,
            event=event,
            created_at=time.monotonic(),
        )
        return event


def cancel_query(query_id: str, user_id: str) -> bool:
    query_key = _clean(query_id)
    owner = _clean(user_id)
    if not query_key:
        return False

    with _LOCK:
        _purge_pending()
        active = _ACTIVE.get(query_key)
        if active is not None:
            if active.user_id != owner:
                return False
            active.event.set()
            return True

        # Menangani klik stop yang sangat cepat, sebelum route /chat selesai
        # mendaftarkan query ke registry.
        _PENDING[query_key] = (owner, time.monotonic())
        return False


def unregister_query(
    query_id: str,
    user_id: str,
    event: threading.Event | None = None,
) -> None:
    query_key = _clean(query_id)
    owner = _clean(user_id)
    with _LOCK:
        active = _ACTIVE.get(query_key)
        if active is None or active.user_id != owner:
            return
        if event is not None and active.event is not event:
            return
        _ACTIVE.pop(query_key, None)


def current_cancel_event() -> threading.Event | None:
    return getattr(_LOCAL, "event", None)


def raise_if_cancelled(event: threading.Event | None = None) -> None:
    selected = event or current_cancel_event()
    if selected is not None and selected.is_set():
        raise ChatCancelled("Chat request was cancelled")


@contextmanager
def cancellation_scope(event: threading.Event | None) -> Iterator[None]:
    previous = current_cancel_event()
    _LOCAL.event = event
    try:
        raise_if_cancelled(event)
        yield
    finally:
        _LOCAL.event = previous
