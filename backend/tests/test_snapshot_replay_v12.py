import hashlib
import time
from unittest.mock import patch

import pytest

from api import chat_service


class FakeCollection:
    def __init__(self, content: str):
        self.content = content

    def get(self, *, ids, include):
        assert include == ["documents", "metadatas"]
        return {
            "ids": ids,
            "documents": [self.content for _ in ids],
            "metadatas": [
                {
                    "filename": "Policy.pdf",
                    "page": 2,
                    "chunk_index": 4,
                }
                for _ in ids
            ],
        }


def _locked_candidate(content: str, **overrides):
    candidate = {
        "chunkId": "chunk-1",
        "contentSha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "score": 0.82,
        "baseScore": 0.72,
        "exactTokenCoverage": 0.25,
        "inventoryFieldScore": 0.0,
        "rerankerApplied": False,
        "evidenceSupported": False,
        "evidenceScore": 0.71,
        "evidenceHardFailures": [],
        "evidenceHardContradictions": [],
        "answerabilityAccepted": True,
        "answerabilityStrictlySupported": True,
        "answerabilityEvidenceSelected": True,
        "answerabilityRequiresCoherentEvidence": True,
        "answerabilityCoherentEvidence": True,
        "snapshotRetrievalMode": "english_corpus_bridge",
        "snapshotRetrievalQuery": "What is the probation period?",
    }
    candidate.update(overrides)
    return candidate


def test_snapshot_replay_preserves_locked_gate_state_without_revalidation():
    content = "The probation period is three months."
    locked = [_locked_candidate(content)]

    with (
        patch.object(
            chat_service,
            "get_collection",
            return_value=FakeCollection(content),
        ),
        patch.object(
            chat_service,
            "_validate_for_original_question",
        ) as validate,
    ):
        candidates = chat_service._materialize_locked_candidates(
            "Berapa lama masa probation?",
            locked,
            requested_k=5,
        )

    assert len(candidates) == 1
    assert candidates[0]["exactTokenCoverage"] == 0.25
    assert candidates[0]["rerankerApplied"] is False
    assert candidates[0]["answerabilityStrictlySupported"] is True
    assert candidates[0]["answerabilityCoherentEvidence"] is True
    assert candidates[0]["evidenceSupported"] is False
    assert candidates[0]["evaluationSnapshotLocked"] is True
    validate.assert_not_called()


def test_snapshot_replay_rejects_content_drift():
    content = "The indexed content has changed."
    locked = [
        _locked_candidate(
            content,
            contentSha256=hashlib.sha256(b"old content").hexdigest(),
        )
    ]

    with (
        patch.object(
            chat_service,
            "get_collection",
            return_value=FakeCollection(content),
        ),
    ):
        with pytest.raises(
            chat_service.EvaluationSnapshotContractError,
            match="content changed",
        ):
            chat_service._materialize_locked_candidates(
                "What changed?",
                locked,
                requested_k=5,
            )


def test_snapshot_replay_rejects_missing_gate_state():
    content = "The probation period is three months."
    locked = [
        {
            "chunkId": "chunk-1",
            "contentSha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "score": 0.82,
        }
    ]

    with patch.object(
        chat_service,
        "get_collection",
        return_value=FakeCollection(content),
    ):
        with pytest.raises(
            chat_service.EvaluationSnapshotContractError,
            match="missing locked gate fields",
        ):
            chat_service._materialize_locked_candidates(
                "What is the probation period?",
                locked,
                requested_k=5,
            )


def test_evaluation_late_failure_preserves_context_and_precise_diagnostics():
    contexts = [{"chunkId": "chunk-1", "content": "Grounded evidence."}]
    payload = chat_service._refusal_payload(
        time.perf_counter(),
        "ID",
        failure_stage="citation_validation_failed",
        generation_mode="native_model",
        model="llama3.2:3b",
        retrieval_mode="natural_language_bridge",
        retrieval_query="What is the policy?",
        generation_contexts=contexts,
        preserve_generation_contexts=True,
        failure_reason="citation_validation_failed",
        rejected_native_answer="Jawaban model yang ditolak.",
        citation_validation={
            "supported": False,
            "reasons": ["unsupported_claims"],
        },
    )

    assert payload["generation_contexts"] == contexts
    assert payload["context_count_before_failure"] == 1
    assert payload["failure_stage"] == "citation_validation_failed"
    assert payload["failure_reason"] == "citation_validation_failed"
    assert payload["generation_mode"] == "native_model"
    assert payload["model"] == "llama3.2:3b"
    assert payload["retrieval_mode"] == "natural_language_bridge"
    assert payload["rejected_native_answer"] == "Jawaban model yang ditolak."
    assert payload["citation_validation"]["supported"] is False

    hidden = chat_service._refusal_payload(
        time.perf_counter(),
        "ID",
        failure_stage="citation_validation_failed",
        generation_contexts=contexts,
        rejected_native_answer="Must stay private.",
        citation_validation={"supported": False},
    )
    assert hidden["generation_contexts"] == []
    assert hidden["context_count_before_failure"] == 1
    assert "rejected_native_answer" not in hidden
    assert "citation_validation" not in hidden
