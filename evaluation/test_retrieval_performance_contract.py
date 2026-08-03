"""Tests for evaluation latency measurement and bilingual retrieval batching."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class RetrievalPerformanceContractTests(unittest.TestCase):
    def test_reranker_uses_at_most_literal_and_natural_bridge(self) -> None:
        from retrieval.reranker import build_reranker_query_variants

        variants = build_reranker_query_variants(
            "Seberapa cepat insiden IT P1 harus diselesaikan?"
        )
        self.assertEqual(len(variants), 2)
        self.assertIn("P1 IT incident", variants[1])

    def test_reranker_warmup_still_loads_and_scores_model(self) -> None:
        from retrieval import reranker

        class FakeReranker:
            calls = 0

            def predict(self, pairs, show_progress_bar=False):
                self.calls += 1
                self.pairs = pairs
                self.show_progress_bar = show_progress_bar
                return [1.0]

        fake = FakeReranker()
        with patch.object(reranker, "ENABLE_RERANKER", True), patch.object(
            reranker, "get_reranker", return_value=fake
        ):
            self.assertTrue(reranker.warmup_reranker())

        self.assertEqual(fake.calls, 1)
        self.assertEqual(len(fake.pairs), 1)
        self.assertFalse(fake.show_progress_bar)

    def test_semantic_variants_use_one_collection_query(self) -> None:
        from retrieval import hybrid_search

        class FakeCollection:
            query_calls = 0

            def count(self) -> int:
                return 2

            def query(self, *, query_embeddings, n_results, include):
                self.query_calls += 1
                return {
                    "ids": [["a", "b"] for _ in query_embeddings],
                    "documents": [["alpha", "beta"] for _ in query_embeddings],
                    "metadatas": [
                        [
                            {"filename": "a.pdf", "page": 1},
                            {"filename": "b.pdf", "page": 1},
                        ]
                        for _ in query_embeddings
                    ],
                    "distances": [[0.1, 0.4] for _ in query_embeddings],
                }

        collection = FakeCollection()
        with patch.object(hybrid_search, "get_collection", return_value=collection), patch.object(
            hybrid_search,
            "embed_query_batch",
            side_effect=lambda queries: [[float(index + 1)] for index, _ in enumerate(queries)],
        ):
            rows = hybrid_search.semantic_search(
                "Seberapa cepat insiden IT P1 harus diselesaikan?",
                top_k=2,
            )

        self.assertEqual(collection.query_calls, 1)
        self.assertEqual(rows[0]["chunkId"], "a")

    def test_snapshot_fast_path_skips_duplicate_baseline_retrieval(self) -> None:
        # Keep this contract runnable even in a lightweight evaluator environment
        # where the backend's FastAPI runtime dependencies are not installed.
        route_source = (BACKEND_DIR / "api" / "routes_compat.py").read_text(
            encoding="utf-8"
        )
        snapshot_source = (
            PROJECT_ROOT / "evaluation" / "generation" / "build_retrieval_snapshot.py"
        ).read_text(encoding="utf-8")

        self.assertIn("includeBaselineDiagnostics: bool = True", route_source)
        self.assertIn("if include_baseline:", route_source)
        self.assertIn('"baselineDiagnosticsIncluded": include_baseline', route_source)
        self.assertIn('"includeBaselineDiagnostics": False', snapshot_source)

    def test_snapshot_producer_and_consumer_share_schema_version(self) -> None:
        from evaluation.generation import build_generation_dataset
        from evaluation.generation import build_retrieval_snapshot

        self.assertEqual(build_retrieval_snapshot.SNAPSHOT_SCHEMA_VERSION, 4)
        self.assertEqual(
            build_generation_dataset.SNAPSHOT_SCHEMA_VERSION,
            build_retrieval_snapshot.SNAPSHOT_SCHEMA_VERSION,
        )
        self.assertEqual(
            build_generation_dataset.LATENCY_MEASUREMENT_MODE,
            build_retrieval_snapshot.LATENCY_MEASUREMENT_MODE,
        )

    def test_snapshot_resume_rejects_topk_or_question_change(self) -> None:
        from evaluation.generation import build_retrieval_snapshot

        question = {
            "question": "What is the retention period?",
            "language": "EN",
            "answerable": True,
        }
        item = {
            **question,
            "question_sha256": hashlib.sha256(
                question["question"].encode("utf-8")
            ).hexdigest(),
            "top_k": 5,
            "latency_measurement_mode": (
                build_retrieval_snapshot.LATENCY_MEASUREMENT_MODE
            ),
        }
        self.assertTrue(
            build_retrieval_snapshot.snapshot_item_matches_question(
                item,
                question,
                top_k=5,
            )
        )
        self.assertFalse(
            build_retrieval_snapshot.snapshot_item_matches_question(
                item,
                question,
                top_k=10,
            )
        )
        changed_question = {**question, "question": "What is the archive period?"}
        self.assertFalse(
            build_retrieval_snapshot.snapshot_item_matches_question(
                item,
                changed_question,
                top_k=5,
            )
        )

    def test_resume_row_is_bound_to_exact_snapshot_and_model(self) -> None:
        from evaluation.generation import build_generation_dataset

        snapshot = {
            "id": "EN-001",
            "question_sha256": "abc",
            "retrieval_time_ms": 123.45,
            "build_version": "rag-bilingual-eval-v19-20260802",
            "ranked_candidates": [{"chunk_id": "chunk-1", "score": 0.9}],
        }
        previous = {
            "model_name": build_generation_dataset.resolved_model_name("ollama"),
            "retrieval_snapshot_fingerprint": (
                build_generation_dataset.retrieval_snapshot_fingerprint(snapshot)
            ),
        }
        self.assertTrue(
            build_generation_dataset.previous_result_matches_snapshot(
                previous,
                snapshot,
                model="ollama",
            )
        )

        changed = {**snapshot, "retrieval_time_ms": 999.0}
        self.assertFalse(
            build_generation_dataset.previous_result_matches_snapshot(
                previous,
                changed,
                model="ollama",
            )
        )
        self.assertFalse(
            build_generation_dataset.previous_result_matches_snapshot(
                {},
                snapshot,
                model="ollama",
            )
        )

    def test_language_latency_imbalance_is_reported_not_hidden(self) -> None:
        from evaluation.generation.evaluate_generation import (
            language_latency_diagnostics,
        )

        diagnostics = language_latency_diagnostics({
            "EN": {
                "average_retrieval_time_ms": 100.0,
                "average_response_time_ms": 200.0,
                "average_estimated_sequential_e2e_ms": 300.0,
            },
            "ID": {
                "average_retrieval_time_ms": 210.0,
                "average_response_time_ms": 220.0,
                "average_estimated_sequential_e2e_ms": 430.0,
            },
        })

        self.assertEqual(diagnostics["status"], "DESCRIPTIVE_IMBALANCE")
        self.assertEqual(
            diagnostics["metrics"]["retrieval"][
                "indonesian_over_english_ratio"
            ],
            2.1,
        )
        self.assertEqual(len(diagnostics["alerts"]), 1)


if __name__ == "__main__":
    unittest.main()
