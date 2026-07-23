from __future__ import annotations

from unittest.mock import patch

from api.build_info import BUILD_VERSION
from retrieval.query_expansion import build_bridge_query, build_query_variants


QUESTION_ID = "Seberapa cepat insiden IT P1 harus diselesaikan?"
P1_TEXT = "P1 incidents must be acknowledged within 15 minutes and resolved within 4 hours."
P2_TEXT = "P2 incidents must be acknowledged within 1 hour and resolved within 8 business hours."


def test_bridge_query_is_independent_english_variant() -> None:
    bridge = build_bridge_query(QUESTION_ID)
    variants = build_query_variants(QUESTION_ID)

    assert bridge
    assert "P1 IT incident" in bridge
    assert "resolution time" in bridge
    assert "seberapa" not in bridge.casefold()
    assert variants[0] == QUESTION_ID
    assert bridge in variants
    assert BUILD_VERSION == "rag-multilingual-v8-20260723"


class _FakeCollection:
    def count(self) -> int:
        return 2

    def get(self, include=None):
        return {
            "ids": ["p2", "p1"],
            "documents": [P2_TEXT, P1_TEXT],
            "metadatas": [
                {"filename": "SOP_IT_Incident_Handling.pdf", "page": 1},
                {"filename": "SOP_IT_Incident_Handling.pdf", "page": 1},
            ],
        }

    def query(self, *, query_embeddings, n_results, include):
        marker = query_embeddings[0][0]
        if marker == 2.0:  # English bridge query
            return {
                "ids": [["p1", "p2"]],
                "documents": [[P1_TEXT, P2_TEXT]],
                "metadatas": [[
                    {"filename": "SOP_IT_Incident_Handling.pdf", "page": 1},
                    {"filename": "SOP_IT_Incident_Handling.pdf", "page": 1},
                ]],
                "distances": [[0.13, 0.42]],
            }
        return {
            "ids": [["p2", "p1"]],
            "documents": [[P2_TEXT, P1_TEXT]],
            "metadatas": [[
                {"filename": "SOP_IT_Incident_Handling.pdf", "page": 1},
                {"filename": "SOP_IT_Incident_Handling.pdf", "page": 1},
            ]],
            "distances": [[0.55, 0.72]],
        }


def test_semantic_search_keeps_best_score_across_language_variants() -> None:
    bridge = build_bridge_query(QUESTION_ID)

    def fake_embed(text: str):
        return [2.0] if text == bridge else [1.0]

    from retrieval import hybrid_search as hybrid_module

    with patch.object(hybrid_module, "get_collection", return_value=_FakeCollection()), patch.object(
        hybrid_module, "embed_query", side_effect=fake_embed
    ):
        rows = hybrid_module.semantic_search(QUESTION_ID, top_k=2)

    assert rows[0]["chunkId"] == "p1"
    assert rows[0]["semanticScore"] == 0.87
    assert rows[0]["semanticQueryVariant"] == bridge
    assert rows[0]["semanticVariantScores"][bridge] == 0.87


def test_bm25_uses_english_bridge_without_lowering_threshold() -> None:
    records = {
        "ids": ["p2", "p1"],
        "documents": [P2_TEXT, P1_TEXT],
        "metadatas": [
            {"filename": "SOP_IT_Incident_Handling.pdf", "page": 1},
            {"filename": "SOP_IT_Incident_Handling.pdf", "page": 1},
        ],
    }
    from retrieval import hybrid_search as hybrid_module

    with patch.object(hybrid_module, "_get_all_records", return_value=records):
        rows = hybrid_module.bm25_search(QUESTION_ID, top_k=2)

    assert rows[0]["chunkId"] == "p1"
    assert rows[0]["keywordScore"] > 0
    assert "P1" in rows[0]["keywordQueryVariant"]


class _FakeReranker:
    def predict(self, pairs, show_progress_bar=False):
        scores = []
        for query, content in pairs:
            is_bridge = "P1 IT incident" in query
            is_p1 = content.startswith("P1 incidents")
            if is_bridge and is_p1:
                scores.append(8.0)
            elif is_p1:
                scores.append(2.0)
            else:
                scores.append(-2.0)
        return scores


def test_reranker_uses_strongest_query_variant() -> None:
    candidates = [
        {"chunkId": "p2", "content": P2_TEXT, "score": 0.60, "baseScore": 0.60},
        {"chunkId": "p1", "content": P1_TEXT, "score": 0.60, "baseScore": 0.60},
    ]
    from retrieval import reranker as reranker_module

    with patch.object(reranker_module, "get_reranker", return_value=_FakeReranker()):
        rows = reranker_module.rerank_candidates(QUESTION_ID, candidates, weight=0.25)

    assert rows[0]["chunkId"] == "p1"
    assert "P1 IT incident" in rows[0]["rerankerQueryVariant"]


def test_full_strict_pipeline_accepts_p1_bridge_and_rejects_p2() -> None:
    from retrieval import hybrid_search as hybrid_module
    from uploads.config import (
        ANSWERABILITY_MIN_BASE_SCORE,
        ANSWERABILITY_MIN_TOP_SCORE,
        MIN_EVIDENCE_SCORE,
        MIN_RESULT_SCORE,
    )

    bridge = build_bridge_query(QUESTION_ID)

    def fake_embed(text: str):
        return [2.0] if text == bridge else [1.0]

    def identity_reranker(query, candidates, **kwargs):
        return [{**candidate, "rerankerApplied": False} for candidate in candidates]

    with patch.object(hybrid_module, "get_collection", return_value=_FakeCollection()), patch.object(
        hybrid_module, "embed_query", side_effect=fake_embed
    ), patch.object(hybrid_module, "rerank_candidates", side_effect=identity_reranker):
        rows = hybrid_module.hybrid_search(
            QUESTION_ID,
            top_k=5,
            use_reranker=True,
            verify_evidence=True,
            apply_answerability=True,
        )

    assert MIN_RESULT_SCORE == 0.24
    assert MIN_EVIDENCE_SCORE == 0.58
    assert ANSWERABILITY_MIN_TOP_SCORE == 0.50
    assert ANSWERABILITY_MIN_BASE_SCORE == 0.30
    assert rows
    assert rows[0]["chunkId"] == "p1"
    assert rows[0]["answerabilityAccepted"] is True
    assert all(row["chunkId"] != "p2" for row in rows)
