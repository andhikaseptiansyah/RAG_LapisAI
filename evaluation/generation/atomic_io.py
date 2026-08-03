"""Small cross-platform helpers for interruption-safe evaluation outputs."""

from __future__ import annotations

import os
import time
from pathlib import Path


def _nonnegative_int_setting(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _nonnegative_float_setting(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


ATOMIC_REPLACE_MAX_RETRIES = _nonnegative_int_setting(
    "EVAL_ATOMIC_REPLACE_MAX_RETRIES",
    8,
)
ATOMIC_REPLACE_INITIAL_DELAY_SECONDS = _nonnegative_float_setting(
    "EVAL_ATOMIC_REPLACE_INITIAL_DELAY_SECONDS",
    0.10,
)
ATOMIC_REPLACE_MAX_DELAY_SECONDS = _nonnegative_float_setting(
    "EVAL_ATOMIC_REPLACE_MAX_DELAY_SECONDS",
    2.0,
)


def _is_retryable_file_lock(error: OSError) -> bool:
    """Recognize Windows sharing/access errors plus normal permission errors."""
    return isinstance(error, PermissionError) or getattr(error, "winerror", None) in {
        5,   # ERROR_ACCESS_DENIED
        32,  # ERROR_SHARING_VIOLATION
        33,  # ERROR_LOCK_VIOLATION
    }


def replace_file_with_retry(
    temporary: Path,
    destination: Path,
    *,
    max_retries: int | None = None,
    initial_delay_seconds: float | None = None,
    max_delay_seconds: float | None = None,
) -> None:
    """Atomically replace a file, tolerating transient Windows file locks.

    Evaluation checkpoints are updated frequently. Antivirus, sync clients,
    editor previews, and spreadsheet applications can briefly open the old
    checkpoint without Windows delete sharing and make ``os.replace`` fail.
    Retrying preserves atomicity without discarding the newly written ``.tmp``
    checkpoint.
    """
    retries = (
        ATOMIC_REPLACE_MAX_RETRIES
        if max_retries is None
        else max(0, int(max_retries))
    )
    initial_delay = (
        ATOMIC_REPLACE_INITIAL_DELAY_SECONDS
        if initial_delay_seconds is None
        else max(0.0, float(initial_delay_seconds))
    )
    maximum_delay = (
        ATOMIC_REPLACE_MAX_DELAY_SECONDS
        if max_delay_seconds is None
        else max(0.0, float(max_delay_seconds))
    )

    for attempt in range(retries + 1):
        try:
            os.replace(temporary, destination)
            return
        except OSError as error:
            if not _is_retryable_file_lock(error):
                raise
            if attempt >= retries:
                raise PermissionError(
                    "Windows kept the evaluation checkpoint locked: "
                    f"'{destination}'. Close Excel, Notepad, VS Code previews, "
                    "Explorer's preview pane, and sync/antivirus scans that are "
                    "holding the file. The newest checkpoint remains at "
                    f"'{temporary}'. Then rerun the same command with --resume."
                ) from error

            delay = min(initial_delay * (2**attempt), maximum_delay)
            print(
                "[CHECKPOINT LOCKED] "
                f"{destination.name}; retry {attempt + 1}/{retries} "
                f"in {delay:.2f}s"
            )
            time.sleep(delay)
