"""Regression test for the Indonesian password-reset false refusal."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.answer_formatter import (
    MIN_ANSWER_CONFIDENCE,
    build_sources,
    top_confidence,
)
from retrieval.evidence_verifier import verify_evidence
from retrieval.query_expansion import expand_query


def main() -> None:
    question = (
        "Jika saya lupa password untuk masuk ke sistem internal, apa prosedur "
        "reset yang harus dilakukan dan berapa lama maksimal prosesnya?"
    )
    content = (
        "Nusantara Dynamics IT Support FAQ. Password Reset. "
        "How do I reset my password? Raise a ticket to the IT Helpdesk via "
        "the portal; resets are processed within 1x24 hours."
    )

    expanded = expand_query(question).lower()
    assert "password reset" in expanded
    assert "it helpdesk" in expanded
    assert "processed within" in expanded

    evidence = verify_evidence(question, content, minimum_score=0.45)
    assert evidence.supported, evidence

    chunk = {
        "chunkId": "FAQ_IT_Support.txt_p1_c0",
        "documentName": "FAQ_IT_Support.txt",
        "page": 1,
        "content": content,
        "score": 0.648,
        "baseScore": 0.5786,
        "semanticScore": 0.55,
        "keywordScore": 0.62,
        "rerankerScore": 0.62,
        "evidenceSupported": evidence.supported,
        "evidenceScore": evidence.score,
        "evidenceHardFailures": list(evidence.hard_failures),
        "metadata": {
            "filename": "FAQ_IT_Support.txt",
            "page": 1,
            "location_type": "page",
        },
    }

    confidence = top_confidence([chunk], question=question)
    sources = build_sources([chunk], question=question)

    assert confidence >= MIN_ANSWER_CONFIDENCE, (confidence, MIN_ANSWER_CONFIDENCE)
    assert sources, "Correct Indonesian retrieval must expose its citation."
    assert sources[0]["document_name"] == "FAQ_IT_Support.txt"

    print(
        "Indonesian password-reset answer gate passed: "
        f"confidence={confidence:.4f}, source={sources[0]['document_name']}"
    )


if __name__ == "__main__":
    main()
