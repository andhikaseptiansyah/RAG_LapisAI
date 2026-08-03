"""Regression tests for the strict private-holdout workflow."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


EVALUATION_DIR = Path(__file__).resolve().parent
GENERATION_DIR = EVALUATION_DIR / "generation"
for import_dir in (EVALUATION_DIR, GENERATION_DIR):
    if str(import_dir) not in sys.path:
        sys.path.insert(0, str(import_dir))

from evaluate_generation import (  # noqa: E402
    bilingual_pairing_diagnostics,
    build_evaluation_status,
)
from private_holdout import (  # noqa: E402
    corpus_fingerprint,
    package_manifest,
    refresh_manifest_file_hashes,
    require_distinct_models,
    validate_private_holdout,
    write_holdout_csvs,
    write_json_atomic,
)
from create_private_holdout import (  # noqa: E402
    candidate_collides,
    unanswerable_review_chunks,
)


def sample_records() -> list[dict]:
    common = {
        "author_model": "author-family:2026-08-02",
        "reviewer_model": "reviewer-family:2026-08-02",
        "reviewer_approved": True,
        "reviewer_reason": "Ground truth checks passed.",
        "human_approved": False,
        "human_reviewer": None,
        "human_reviewed_at_utc": None,
    }
    return [
        {
            **common,
            "pair_id": "P001",
            "answerable": True,
            "source_document": "policy.pdf",
            "topic_document": "policy.pdf",
            "question_en": "What is the documented retention period?",
            "answer_en": "The retention period is seven years.",
            "keywords_en": ["retention", "seven years"],
            "question_id": "Berapa lama periode retensi yang didokumentasikan?",
            "answer_id": "Periode retensinya adalah tujuh tahun.",
            "keywords_id": ["retensi", "tujuh tahun"],
            "evidence_quote": "Records are retained for seven years.",
            "evidence_chunk_id": "chunk-1",
            "evidence_sha256": "a" * 64,
            "reviewed_evidence": [],
        },
        {
            **common,
            "pair_id": "P002",
            "answerable": False,
            "source_document": "",
            "topic_document": "policy.pdf",
            "question_en": "Which vendor designed the retention policy logo?",
            "answer_en": "The requested information is not available in the indexed documents.",
            "keywords_en": ["vendor", "logo"],
            "question_id": "Vendor mana yang merancang logo kebijakan retensi?",
            "answer_id": "Informasi yang diminta tidak tersedia dalam dokumen yang diindeks.",
            "keywords_id": ["vendor", "logo"],
            "evidence_quote": "",
            "evidence_chunk_id": "chunk-2",
            "evidence_sha256": "b" * 64,
            "reviewed_evidence": [
                {
                    "chunk_id": "chunk-2",
                    "filename": "policy.pdf",
                    "text_sha256": "b" * 64,
                    "excerpt": "The policy defines retention periods.",
                }
            ],
        },
    ]


class PrivateHoldoutTests(unittest.TestCase):
    def create_package(self, root: Path) -> list[dict]:
        records = sample_records()
        write_holdout_csvs(root, records)
        write_json_atomic(
            root / "holdout_review.json",
            {
                "schema_version": 1,
                "corpus_sha256": "corpus-hash",
                "author_model": "author-family:2026-08-02",
                "reviewer_model": "reviewer-family:2026-08-02",
                "records": records,
            },
        )
        manifest = package_manifest(
            output_dir=root,
            records=records,
            corpus_sha256="corpus-hash",
            author_model="author-family:2026-08-02",
            reviewer_model="reviewer-family:2026-08-02",
            seed=42,
        )
        write_json_atomic(root / "holdout_manifest.json", manifest)
        return records

    def test_model_roles_must_be_distinct_and_pinned(self) -> None:
        with self.assertRaisesRegex(ValueError, "distinct"):
            require_distinct_models(
                author="model-a:v1",
                reviewer="model-b:v1",
                judge="model-c:v1",
                evaluated=["model-a:v1"],
            )
        with self.assertRaisesRegex(ValueError, "immutable"):
            require_distinct_models(
                author="model-a:latest",
                reviewer="model-b:v1",
            )
        with self.assertRaisesRegex(ValueError, "immutable"):
            require_distinct_models(
                author="unnumbered-alias",
                reviewer="model-b:v1",
            )

    def test_canonical_unanswerable_answers_do_not_collide(self) -> None:
        candidate = {
            "question_en": "Which supplier designed the policy logo?",
            "question_id": "Pemasok mana yang merancang logo kebijakan?",
            "answer_en": "The requested information is not available in the indexed documents.",
            "answer_id": "Informasi yang diminta tidak tersedia dalam dokumen yang diindeks.",
            "evidence_quote": "",
        }
        used = {
            candidate["answer_en"].casefold(),
            candidate["answer_id"].casefold(),
        }
        self.assertFalse(candidate_collides(candidate, used))

    def test_unanswerable_review_always_includes_topic_and_relevant_chunks(self) -> None:
        topic = {
            "chunk_id": "topic-1",
            "filename": "policy.pdf",
            "text": "This section describes the retention policy.",
            "text_sha256": "1" * 64,
        }
        relevant = {
            "chunk_id": "other-1",
            "filename": "vendor.pdf",
            "text": "The logo supplier and design vendor are listed here.",
            "text_sha256": "2" * 64,
        }
        selected = unanswerable_review_chunks(
            {
                "question_en": "Which vendor designed the policy logo?",
                "question_id": "Vendor mana yang merancang logo kebijakan?",
                "missing_detail": "logo design vendor",
                "keywords_en": ["vendor", "logo"],
                "keywords_id": ["vendor", "logo"],
            },
            topic,
            [relevant, topic],
            limit=2,
        )
        self.assertEqual(selected[0]["chunk_id"], "topic-1")
        self.assertIn("other-1", {item["chunk_id"] for item in selected})

    def test_corpus_fingerprint_is_order_independent(self) -> None:
        chunks = [
            {"chunk_id": "2", "filename": "B.pdf", "text": "beta"},
            {"chunk_id": "1", "filename": "a.pdf", "text": "alpha"},
        ]
        self.assertEqual(corpus_fingerprint(chunks), corpus_fingerprint(chunks[::-1]))

    def test_human_approval_and_tamper_gates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = self.create_package(root)
            validate_private_holdout(root, require_human_approval=False)
            with self.assertRaisesRegex(ValueError, "Human review"):
                validate_private_holdout(root, require_human_approval=True)

            for record in records:
                record["human_approved"] = True
                record["human_reviewer"] = "QA Reviewer"
                record["human_reviewed_at_utc"] = "2026-08-02T00:00:00+00:00"
            review_path = root / "holdout_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["records"] = records
            write_json_atomic(review_path, review)
            manifest = json.loads(
                (root / "holdout_manifest.json").read_text(encoding="utf-8")
            )
            refresh_manifest_file_hashes(root, manifest)
            validate_private_holdout(root, require_human_approval=True)

            english_path = root / "qna_english_holdout.csv"
            english_path.write_text(
                english_path.read_text(encoding="utf-8-sig") + "tampered",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "changed after freezing"):
                validate_private_holdout(root, require_human_approval=True)

    def test_unanswerable_pairs_count_as_equivalent_targets(self) -> None:
        items = [
            {
                "id": "EN-001",
                "language": "EN",
                "answerable": False,
                "references": [],
            },
            {
                "id": "ID-001",
                "language": "ID",
                "answerable": False,
                "references": [],
            },
        ]
        diagnostics = bilingual_pairing_diagnostics(items)
        self.assertTrue(diagnostics["direct_language_gap_interpretation_supported"])
        self.assertEqual(diagnostics["same_expected_source_pair_count"], 1)

    def test_final_status_requires_private_manifest(self) -> None:
        kwargs = {
            "benchmark_role": "holdout",
            "overall": {
                "judge_coverage": 1.0,
                "retrieval_latency_coverage": 1.0,
                "client_latency_coverage": 1.0,
                "estimated_e2e_latency_coverage": 1.0,
            },
            "model_name": "evaluated-family:2026-08-02",
            "judge_model": "judge-family:2026-08-02",
            "judge_independent": True,
            "pairing": {"direct_language_gap_interpretation_supported": True},
        }
        with patch.dict(os.environ, {}, clear=True):
            status = build_evaluation_status(**kwargs)
            self.assertFalse(status["final_eligible"])
            self.assertTrue(any("manifest" in item for item in status["blockers"]))
        with patch.dict(
            os.environ,
            {"LAPISAI_HOLDOUT_MANIFEST": "/private/holdout_manifest.json"},
            clear=True,
        ):
            status = build_evaluation_status(**kwargs)
            self.assertTrue(status["final_eligible"])


if __name__ == "__main__":
    unittest.main()
