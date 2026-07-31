import hashlib
from unittest.mock import patch

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


def test_snapshot_replay_recomputes_lexical_signals_and_preserves_reranker_flag():
    content = "The probation period is three months."
    locked = [
        {
            "chunkId": "chunk-1",
            "contentSha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "score": 0.82,
            "baseScore": 0.72,
            "rerankerApplied": False,
            "snapshotRetrievalMode": "english_corpus_bridge",
            "snapshotRetrievalQuery": "What is the probation period?",
        }
    ]

    validation = {}

    def accept_all(question, candidates, **kwargs):
        validation["question"] = question
        validation["bridge_query"] = kwargs.get("bridge_query")
        return candidates

    with (
        patch.object(
            chat_service,
            "get_collection",
            return_value=FakeCollection(content),
        ),
        patch.object(
            chat_service,
            "_validate_for_original_question",
            side_effect=accept_all,
        ),
    ):
        candidates = chat_service._materialize_locked_candidates(
            "Berapa lama masa probation?",
            locked,
            requested_k=5,
        )

    assert len(candidates) == 1
    assert candidates[0]["exactTokenCoverage"] == 1.0
    assert candidates[0]["rerankerApplied"] is False
    assert validation["question"] == "Berapa lama masa probation?"
    assert validation["bridge_query"] == "What is the probation period?"


def test_snapshot_replay_rejects_content_drift():
    content = "The indexed content has changed."
    locked = [
        {
            "chunkId": "chunk-1",
            "contentSha256": hashlib.sha256(b"old content").hexdigest(),
            "score": 0.82,
        }
    ]

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
            "What changed?",
            locked,
            requested_k=5,
        )

    assert candidates == []
    validate.assert_not_called()
