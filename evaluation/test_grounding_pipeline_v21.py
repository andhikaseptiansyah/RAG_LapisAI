"""Evaluation-contract regression tests for deterministic grounded repair."""

from __future__ import annotations

import unittest

from evaluation.generation.build_generation_dataset import (
    ALLOWED_EVALUATION_GENERATION_MODES,
    CONTEXT_MODE,
)


class GroundingPipelineV21Tests(unittest.TestCase):
    def test_verified_scalar_fallback_is_auditable_evaluation_output(self) -> None:
        self.assertIn(
            "verified_scalar_fallback",
            ALLOWED_EVALUATION_GENERATION_MODES,
        )

    def test_unsafe_free_form_fallback_is_not_allowed(self) -> None:
        self.assertNotIn("extractive_fallback", ALLOWED_EVALUATION_GENERATION_MODES)
        self.assertNotIn("language_repair_retry", ALLOWED_EVALUATION_GENERATION_MODES)

    def test_context_mode_changes_when_evaluation_semantics_change(self) -> None:
        self.assertEqual(CONTEXT_MODE, "source_locked_snapshot_grounded_repair_v9")


if __name__ == "__main__":
    unittest.main()
