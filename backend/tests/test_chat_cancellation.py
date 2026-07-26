from __future__ import annotations

import threading

import pytest

from api.cancellation import (
    ChatCancelled,
    cancel_query,
    cancellation_scope,
    raise_if_cancelled,
    register_query,
    unregister_query,
)


def test_registered_query_can_be_cancelled() -> None:
    event = register_query("cancel-test-1", "user-1")
    assert not event.is_set()
    assert cancel_query("cancel-test-1", "user-1") is True
    assert event.is_set()
    with pytest.raises(ChatCancelled):
        raise_if_cancelled(event)
    unregister_query("cancel-test-1", "user-1", event)


def test_other_user_cannot_cancel_query() -> None:
    event = register_query("cancel-test-2", "user-a")
    assert cancel_query("cancel-test-2", "user-b") is False
    assert not event.is_set()
    unregister_query("cancel-test-2", "user-a", event)


def test_early_cancel_is_applied_when_query_registers() -> None:
    assert cancel_query("cancel-test-3", "user-1") is False
    event = register_query("cancel-test-3", "user-1")
    assert event.is_set()
    unregister_query("cancel-test-3", "user-1", event)


def test_thread_local_cancellation_scope() -> None:
    event = threading.Event()
    with cancellation_scope(event):
        raise_if_cancelled()
        event.set()
        with pytest.raises(ChatCancelled):
            raise_if_cancelled()
