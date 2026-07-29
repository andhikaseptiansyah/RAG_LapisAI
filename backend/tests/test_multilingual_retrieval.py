from __future__ import annotations

import unittest

from api.answer_formatter import build_evidence_excerpt
from retrieval.answerability import assess_answerability
from retrieval.evidence_verifier import verify_chunks, verify_evidence
from retrieval.scoring import hybrid_base_score


class MultilingualRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.indonesian_question = (
            "Berapa hari per minggu karyawan dapat bekerja dari rumah?"
        )
        self.english_evidence = (
            "Employees may work remotely for up to two days per week with "
            "their manager's approval."
        )

    def test_missing_bm25_signal_does_not_dilute_multilingual_semantic_score(self) -> None:
        self.assertAlmostEqual(hybrid_base_score(0.68, 0.0), 0.68)
        self.assertAlmostEqual(
            hybrid_base_score(0.68, 0.50),
            (0.68 * 0.68) + (0.32 * 0.50),
        )

    def test_indonesian_question_accepts_english_evidence_from_multilingual_embedding(self) -> None:
        decision = verify_evidence(
            self.indonesian_question,
            self.english_evidence,
            semantic_score=0.68,
        )

        self.assertTrue(decision.supported, decision)
        self.assertGreaterEqual(decision.score, 0.58)
        self.assertEqual(decision.semantic_support, 0.68)

    def test_weak_semantic_match_still_fails_at_the_same_threshold(self) -> None:
        decision = verify_evidence(
            self.indonesian_question,
            "The office cafeteria is open from Monday to Friday.",
            semantic_score=0.40,
        )

        self.assertFalse(decision.supported)
        self.assertLess(decision.score, 0.58)

    def test_semantic_score_cannot_override_a_subject_conflict(self) -> None:
        decision = verify_evidence(
            "Berapa batas ukuran unggahan file pada portal pelanggan?",
            "The mailbox storage quota is 50 GB.",
            semantic_score=0.95,
        )

        self.assertFalse(decision.supported)
        self.assertTrue(
            any(
                failure.startswith("missing_concept:file_upload")
                or failure.startswith("conflicting_concept:mailbox_quota")
                for failure in decision.hard_failures
            )
        )

    def test_verify_chunks_uses_existing_multilingual_semantic_score(self) -> None:
        rows = verify_chunks(
            self.indonesian_question,
            [
                {
                    "chunkId": "remote-work",
                    "content": self.english_evidence,
                    "semanticScore": 0.68,
                }
            ],
        )

        self.assertTrue(rows[0]["evidenceSupported"])
        self.assertEqual(rows[0]["evidenceSemanticSupport"], 0.68)

    def test_cross_language_candidate_passes_the_existing_answerability_gate(self) -> None:
        rows = verify_chunks(
            self.indonesian_question,
            [
                {
                    "chunkId": "remote-work",
                    "content": self.english_evidence,
                    "score": 0.68,
                    "baseScore": 0.68,
                    "semanticScore": 0.68,
                    "keywordScore": 0.0,
                    "exactTokenCoverage": 0.0,
                    "metadata": {"filename": "employee-policy.txt", "page": 1},
                }
            ],
        )

        decision = assess_answerability(self.indonesian_question, rows)
        self.assertTrue(decision.answerable, decision)
        self.assertGreaterEqual(decision.top_score, 0.50)
        self.assertGreaterEqual(decision.top_evidence_score, 0.58)

    def test_cross_language_excerpt_keeps_the_compact_verified_chunk(self) -> None:
        content = (
            "Remote Work Policy: Eligibility is reviewed by Human Resources. "
            + self.english_evidence
        )
        excerpt = build_evidence_excerpt(
            self.indonesian_question,
            content,
            max_chars=500,
        )

        self.assertIn("Employees may work remotely", excerpt)
        self.assertIn("Human Resources", excerpt)


if __name__ == "__main__":
    unittest.main()
