"""Regression tests for v21 false-refusal and deterministic repair fixes."""

from __future__ import annotations

import unittest

from api.answer_formatter import build_sources, build_verified_scalar_answer
from api.build_info import BUILD_VERSION
from api.grounding_validator import prune_unsupported_claims, validate_grounded_answer


def strict_chunk(content: str, name: str) -> dict:
    return {
        "chunkId": f"guard-v21-{name}",
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


class GroundingGuardV21Tests(unittest.TestCase):
    def test_third_person_approval_is_supported_and_citable(self) -> None:
        question = "Who approves an employee request for access to a software tool?"
        evidence = "Request it via the IT Service Desk; the system owner approves."
        answer = (
            "The system owner approves an employee request for access to a "
            "software tool. The request must be submitted via the IT Service Desk."
        )
        chunks = [strict_chunk(evidence, "FAQ_Software_Access.txt")]

        decision = validate_grounded_answer(question, answer, chunks)
        self.assertTrue(decision.supported, decision.to_dict())
        self.assertEqual(len(build_sources(chunks, question=question, answer=answer)), 1)

    def test_indonesian_password_reset_fallback_is_complete_and_grounded(self) -> None:
        question = "Bagaimana cara mereset kata sandi dan berapa lama prosesnya?"
        evidence = (
            "Raise a ticket to the IT Helpdesk via the portal; "
            "resets are processed within 1x24 hours."
        )
        chunks = [strict_chunk(evidence, "FAQ_IT_Support.txt")]

        answer = build_verified_scalar_answer(question, chunks, language="ID")
        self.assertEqual(
            answer,
            "Ajukan tiket ke IT Helpdesk melalui portal; reset kata sandi "
            "diproses dalam 1x24 jam.",
        )
        decision = validate_grounded_answer(question, answer, chunks)
        self.assertTrue(decision.supported, decision.to_dict())
        self.assertEqual(len(build_sources(chunks, question=question, answer=answer)), 1)

    def test_english_password_reset_fallback_is_complete_and_grounded(self) -> None:
        question = "How do I reset my password and how long does it take?"
        evidence = (
            "Raise a ticket to the IT Helpdesk via the portal; "
            "resets are processed within 1x24 hours."
        )
        chunks = [strict_chunk(evidence, "FAQ_IT_Support.txt")]

        answer = build_verified_scalar_answer(question, chunks, language="EN")
        self.assertEqual(
            answer,
            "Raise a ticket to the IT Helpdesk via the portal; password resets "
            "are processed within 1x24 hours.",
        )
        decision = validate_grounded_answer(question, answer, chunks)
        self.assertTrue(decision.supported, decision.to_dict())

    def test_wrong_working_day_translation_remains_blocked(self) -> None:
        question = "Bagaimana cara mereset kata sandi dan berapa lama prosesnya?"
        evidence = (
            "Raise a ticket to the IT Helpdesk via the portal; "
            "resets are processed within 1x24 hours."
        )
        answer = (
            "Ajukan tiket ke IT Helpdesk melalui portal. "
            "Proses reset memakan waktu maksimal 1 hari kerja."
        )
        chunks = [strict_chunk(evidence, "FAQ_IT_Support.txt")]

        decision = validate_grounded_answer(question, answer, chunks)
        self.assertFalse(decision.supported)
        self.assertIn("1 hari kerja", decision.unsupported_facts)

    def test_backup_relation_swap_remains_blocked(self) -> None:
        question = "How often are full database backups taken?"
        evidence = (
            "Production databases are backed up every 6 hours. "
            "Full backups run nightly at 01:00 WIB."
        )
        wrong = (
            "Full database backups are taken nightly at 01:00 WIB. "
            "Additionally, full backups are run every 6 hours."
        )
        chunks = [strict_chunk(evidence, "SOP_Data_Backup.pdf")]

        decision = validate_grounded_answer(question, wrong, chunks)
        self.assertFalse(decision.supported)
        self.assertEqual(
            prune_unsupported_claims(question, wrong, chunks),
            "Full database backups are taken nightly at 01:00 WIB.",
        )

    def test_build_version_identifies_v21(self) -> None:
        self.assertEqual(BUILD_VERSION, "rag-grounding-guard-v21-20260804")


if __name__ == "__main__":
    unittest.main()
