"""Regression tests for the v20 full-answer grounding guard."""

from __future__ import annotations

import unittest

from api.answer_formatter import build_sources
from api.grounding_validator import prune_unsupported_claims, validate_grounded_answer


def strict_chunk(content: str, name: str = "SOP_Data_Backup.pdf") -> dict:
    return {
        "chunkId": "guard-v20-1",
        "documentName": name,
        "page": 1,
        "content": content,
        "metadata": {"filename": name, "content": content},
        "score": 0.95,
        "baseScore": 0.90,
        "semanticScore": 0.90,
        "evidenceSupported": True,
        "evidenceScore": 0.95,
        "evidenceHardFailures": [],
        "evidenceHardContradictions": [],
        "answerabilityAccepted": True,
        "answerabilityEvidenceSelected": True,
        "answerabilityStrictlySupported": True,
        "answerabilityCoherentEvidence": True,
        "answerabilityRequiresCoherentEvidence": False,
        "contextSelected": True,
    }


class GroundingGuardV20Tests(unittest.TestCase):
    def test_full_backup_cannot_inherit_incremental_cadence(self) -> None:
        question = "How often are full database backups taken?"
        evidence = (
            "Production databases are backed up every 6 hours. "
            "Full backups run nightly at 01:00 WIB."
        )
        wrong = (
            "Full database backups are taken nightly at 01:00 WIB. "
            "Additionally, full backups are run every 6 hours."
        )
        decision = validate_grounded_answer(
            question,
            wrong,
            [strict_chunk(evidence)],
        )
        self.assertFalse(decision.supported)
        self.assertIn("full backups are run every 6 hours", decision.unsupported_claims)

        pruned = prune_unsupported_claims(
            question,
            wrong,
            [strict_chunk(evidence)],
        )
        self.assertEqual(
            pruned,
            "Full database backups are taken nightly at 01:00 WIB.",
        )

    def test_partial_support_never_produces_a_trusted_citation(self) -> None:
        question = "How often are full database backups taken?"
        evidence = (
            "Production databases are backed up every 6 hours. "
            "Full backups run nightly at 01:00 WIB."
        )
        wrong = (
            "Full backups run nightly at 01:00 WIB. "
            "Full backups also run every 6 hours."
        )
        self.assertEqual(
            build_sources(
                [strict_chunk(evidence)],
                question=question,
                answer=wrong,
            ),
            [],
        )

        supported = "Full backups run nightly at 01:00 WIB."
        sources = build_sources(
            [strict_chunk(evidence)],
            question=question,
            answer=supported,
        )
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["document_name"], "SOP_Data_Backup.pdf")

    def test_unsupported_explanatory_tail_is_blocked(self) -> None:
        question = "How often must passwords be changed?"
        evidence = "Passwords must be changed every 90 days."
        answer = (
            "Passwords must be changed every 90 days. "
            "This policy prevents every possible security breach."
        )
        chunks = [strict_chunk(evidence, "Policy_Password.docx")]
        decision = validate_grounded_answer(question, answer, chunks)
        self.assertFalse(decision.supported)
        self.assertEqual(build_sources(chunks, question=question, answer=answer), [])

    def test_wrong_duration_translation_is_blocked(self) -> None:
        question = "Bagaimana cara mereset kata sandi dan berapa lama prosesnya?"
        evidence = (
            "Raise a ticket to the IT Helpdesk via the portal; "
            "resets are processed within 1x24 hours."
        )
        answer = (
            "Ajukan tiket ke IT Helpdesk melalui portal. "
            "Prosesnya memakan waktu maksimal 1 hari kerja."
        )
        decision = validate_grounded_answer(
            question,
            answer,
            [strict_chunk(evidence, "FAQ_IT_Support.txt")],
        )
        self.assertFalse(decision.supported)
        self.assertTrue(decision.unsupported_facts)


if __name__ == "__main__":
    unittest.main()
