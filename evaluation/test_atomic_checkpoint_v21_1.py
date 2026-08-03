"""Regression tests for Windows-safe atomic evaluation checkpoints."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evaluation.generation import atomic_io


class AtomicCheckpointTests(unittest.TestCase):
    def test_transient_file_lock_is_retried_without_losing_checkpoint(self) -> None:
        calls = 0
        delays: list[float] = []
        original_replace = atomic_io.os.replace
        original_sleep = atomic_io.time.sleep

        def flaky_replace(source: Path, destination: Path) -> None:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise PermissionError("temporary Windows lock")
            original_replace(source, destination)

        try:
            atomic_io.os.replace = flaky_replace
            atomic_io.time.sleep = delays.append
            with tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "checkpoint.json"
                temporary = Path(directory) / "checkpoint.json.tmp"
                destination.write_text("old", encoding="utf-8")
                temporary.write_text("new", encoding="utf-8")

                atomic_io.replace_file_with_retry(
                    temporary,
                    destination,
                    max_retries=2,
                    initial_delay_seconds=0.1,
                    max_delay_seconds=2.0,
                )

                self.assertEqual(destination.read_text(encoding="utf-8"), "new")
                self.assertFalse(temporary.exists())
        finally:
            atomic_io.os.replace = original_replace
            atomic_io.time.sleep = original_sleep

        self.assertEqual(calls, 3)
        self.assertEqual(delays, [0.1, 0.2])

    def test_permanent_lock_preserves_tmp_and_explains_resume(self) -> None:
        original_replace = atomic_io.os.replace
        original_sleep = atomic_io.time.sleep

        def locked_replace(_source: Path, _destination: Path) -> None:
            raise PermissionError("still locked")

        try:
            atomic_io.os.replace = locked_replace
            atomic_io.time.sleep = lambda _seconds: None
            with tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "checkpoint.json"
                temporary = Path(directory) / "checkpoint.json.tmp"
                destination.write_text("old", encoding="utf-8")
                temporary.write_text("new", encoding="utf-8")

                with self.assertRaisesRegex(PermissionError, r"--resume"):
                    atomic_io.replace_file_with_retry(
                        temporary,
                        destination,
                        max_retries=1,
                    )

                self.assertEqual(destination.read_text(encoding="utf-8"), "old")
                self.assertEqual(temporary.read_text(encoding="utf-8"), "new")
        finally:
            atomic_io.os.replace = original_replace
            atomic_io.time.sleep = original_sleep


if __name__ == "__main__":
    unittest.main()
