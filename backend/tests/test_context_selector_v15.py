from __future__ import annotations

from retrieval.context_selector import select_context_bundle


def _candidate(
    chunk_id: str,
    content: str,
    score: float,
    *,
    evidence_supported: bool,
    evidence_score: float,
    missing: list[str],
) -> dict:
    return {
        "chunkId": chunk_id,
        "documentName": "Policy.docx",
        "content": content,
        "score": score,
        "evidenceSupported": evidence_supported,
        "evidenceScore": evidence_score,
        "evidenceHardFailures": [],
        "evidenceHardContradictions": [],
        "evidenceMissingRequirements": missing,
    }


def test_heading_cannot_displace_the_supported_harassment_paragraph() -> None:
    candidates = [
        _candidate(
            "title",
            "Anti-Harassment Policy",
            0.8135,
            evidence_supported=False,
            evidence_score=0.2652,
            missing=["missing_concept:harassment_reporting"],
        ),
        _candidate(
            "body",
            (
                "The company has zero tolerance for all forms of harassment. "
                "Complaints can be raised confidentially to HR or via the "
                "whistleblower channel."
            ),
            0.7726,
            evidence_supported=True,
            evidence_score=0.8167,
            missing=[],
        ),
    ]

    selected = select_context_bundle(
        "Bagaimana sikap perusahaan terhadap tindakan pelecehan di tempat kerja?",
        candidates,
        max_contexts=4,
        minimum_contexts=2,
    )

    assert [row["chunkId"] for row in selected] == ["body"]


def test_password_complexity_and_rotation_chunks_are_selected_together() -> None:
    candidates = [
        _candidate(
            "title",
            "Password Policy",
            0.8081,
            evidence_supported=False,
            evidence_score=0.3240,
            missing=[
                "missing_concept:password_complexity",
                "missing_concept:password_rotation",
            ],
        ),
        _candidate(
            "complexity",
            (
                "Passwords must be at least 12 characters and include upper "
                "case, lower case, a number, and a symbol."
            ),
            0.8068,
            evidence_supported=False,
            evidence_score=0.5932,
            missing=["missing_concept:password_rotation"],
        ),
        _candidate(
            "rotation",
            (
                "Passwords must be changed every 90 days and the last 5 "
                "passwords cannot be reused."
            ),
            0.7491,
            evidence_supported=False,
            evidence_score=0.6102,
            missing=["missing_concept:password_complexity"],
        ),
    ]

    selected = select_context_bundle(
        "What are the password requirements?",
        candidates,
        max_contexts=4,
        minimum_contexts=2,
    )

    assert [row["chunkId"] for row in selected] == [
        "complexity",
        "rotation",
    ]
    assert "title" not in {row["chunkId"] for row in selected}


def test_wrong_document_does_not_win_only_because_it_has_more_text() -> None:
    candidates = [
        _candidate(
            "correct",
            "Salaries are paid on the 25th of each month.",
            0.91,
            evidence_supported=True,
            evidence_score=0.92,
            missing=[],
        ),
        _candidate(
            "noise",
            (
                "This long unrelated paragraph discusses office parking, "
                "visitor registration, cafeteria opening hours, and building "
                "access without mentioning salary payment."
            ),
            0.45,
            evidence_supported=False,
            evidence_score=0.10,
            missing=[],
        ),
    ]

    selected = select_context_bundle(
        "When is salary paid?",
        candidates,
        max_contexts=2,
        minimum_contexts=1,
    )

    assert selected[0]["chunkId"] == "correct"
