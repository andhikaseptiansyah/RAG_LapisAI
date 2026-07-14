from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_cross_encoder_is_blended_not_absolute() -> None:
    from retrieval import reranker

    class FakeCrossEncoder:
        def predict(self, pairs, show_progress_bar=False):
            assert show_progress_bar is False
            assert len(pairs) == 3
            # b is the strongest cross-encoder match, c is medium, a is weakest.
            return [-2.0, 4.0, 0.5]

    original_get_reranker = reranker.get_reranker
    original_enabled = reranker.ENABLE_RERANKER
    try:
        reranker.get_reranker = lambda: FakeCrossEncoder()
        reranker.ENABLE_RERANKER = True
        results = reranker.rerank_candidates(
            "password reset processing time",
            [
                {"chunkId": "a", "content": "Unrelated laptop request.", "score": 0.90},
                {"chunkId": "b", "content": "Password resets take 1x24 hours.", "score": 0.70},
                {"chunkId": "c", "content": "General IT support information.", "score": 0.80},
            ],
            weight=0.25,
        )
    finally:
        reranker.get_reranker = original_get_reranker
        reranker.ENABLE_RERANKER = original_enabled

    # b is promoted to first, but ranking is based on the blended score rather
    # than raw logits alone. c remains above a because its combined evidence is
    # stronger than a's base-only advantage.
    assert [item["chunkId"] for item in results] == ["b", "c", "a"]
    assert [item["rerankerRank"] for item in results] == [1, 2, 3]
    assert all(item["rerankerApplied"] is True for item in results)
    assert all(item["rerankerWeight"] == 0.25 for item in results)


def test_low_weight_prevents_confident_reranker_takeover() -> None:
    from retrieval import reranker

    class FakeCrossEncoder:
        def predict(self, pairs, show_progress_bar=False):
            return [-5.0, 5.0]

    original_get_reranker = reranker.get_reranker
    original_enabled = reranker.ENABLE_RERANKER
    try:
        reranker.get_reranker = lambda: FakeCrossEncoder()
        reranker.ENABLE_RERANKER = True
        results = reranker.rerank_candidates(
            "test query",
            [
                {"chunkId": "strong-hybrid", "content": "A", "score": 0.95},
                {"chunkId": "weak-hybrid", "content": "B", "score": 0.20},
            ],
            weight=0.25,
        )
    finally:
        reranker.get_reranker = original_get_reranker
        reranker.ENABLE_RERANKER = original_enabled

    assert [item["chunkId"] for item in results] == ["strong-hybrid", "weak-hybrid"]
    assert results[0]["rerankerRawRank"] == 2
    assert results[1]["rerankerRawRank"] == 1


def test_full_union_is_sent_to_reranker() -> None:
    # hybrid_search imports ingestion.indexer, which normally loads ChromaDB and
    # sentence-transformers. A tiny stub keeps this unit test dependency-free.
    fake_indexer = types.ModuleType("ingestion.indexer")
    fake_indexer.embed_query = lambda _: [0.0]
    fake_indexer.get_collection = lambda: None
    sys.modules["ingestion.indexer"] = fake_indexer

    module_name = "retrieval.hybrid_search"
    sys.modules.pop(module_name, None)
    hybrid = importlib.import_module(module_name)

    semantic_rows = [
        {
            "chunkId": f"semantic-{index}",
            "content": f"semantic passage {index}",
            "metadata": {"filename": f"semantic-{index}.pdf", "page": 1},
            "semanticScore": 1.0 - index / 100,
            "semanticRank": index,
        }
        for index in range(20)
    ]
    keyword_rows = [
        {
            "chunkId": f"keyword-{index}",
            "content": f"keyword passage {index}",
            "metadata": {"filename": f"keyword-{index}.txt", "page": 1},
            "keywordScore": 1.0 - index / 100,
            "keywordRank": index,
        }
        for index in range(20)
    ]

    observed = {"candidate_count": 0, "query": ""}

    def fake_rerank(query, candidates):
        observed["candidate_count"] = len(candidates)
        observed["query"] = query
        return [
            {
                **candidate,
                "rerankerApplied": True,
                "rerankerRawScore": float(len(candidates) - index),
                "rerankerScore": 0.9,
                "score": 0.9,
                "rerankerRank": index + 1,
            }
            for index, candidate in enumerate(candidates)
        ]

    hybrid.semantic_search = lambda query, top_k=20: semantic_rows[:top_k]
    hybrid.bm25_search = lambda query, top_k=20: keyword_rows[:top_k]
    hybrid.rerank_candidates = fake_rerank

    original_query = "Bagaimana cara reset password?"
    results = hybrid.hybrid_search(
        original_query,
        top_k=5,
        candidate_k=20,
        min_score=0.0,
        use_reranker=True,
        verify_evidence=False,
    )

    assert observed["candidate_count"] == 40, (
        "The union of semantic top 20 and BM25 top 20 must be reranked before truncation."
    )
    assert observed["query"] == original_query
    assert len(results) == 5



def test_post_rerank_gate_rejects_unsupported_resurrection() -> None:
    fake_indexer = types.ModuleType("ingestion.indexer")
    fake_indexer.embed_query = lambda _: [0.0]
    fake_indexer.get_collection = lambda: None
    sys.modules["ingestion.indexer"] = fake_indexer

    module_name = "retrieval.hybrid_search"
    sys.modules.pop(module_name, None)
    hybrid = importlib.import_module(module_name)

    weak_row = {
        "chunkId": "weak",
        "content": "Generic IT portal information with no requested exact endpoint.",
        "metadata": {"filename": "faq.txt", "page": 1},
        "semanticScore": 0.20,
        "semanticRank": 0,
    }
    hybrid.semantic_search = lambda query, top_k=20: [weak_row]
    hybrid.bm25_search = lambda query, top_k=20: []

    reranker_called = {"value": False}

    def fake_rerank(query, candidates):
        reranker_called["value"] = True
        return [
            {
                **candidate,
                "rerankerApplied": True,
                "rerankerScore": 1.0,
                "rerankerRawScore": 10.0,
                "score": 0.95,
            }
            for candidate in candidates
        ]

    hybrid.rerank_candidates = fake_rerank

    results = hybrid.hybrid_search(
        "Apa URL endpoint persis untuk self-service password reset Active Directory?",
        top_k=5,
        candidate_k=20,
        min_score=0.30,
        use_reranker=True,
        verify_evidence=True,
        apply_answerability=True,
    )

    assert results == []
    assert reranker_called["value"] is True, (
        "Reranking must run before answerability so a correct lower-ranked passage can be promoted."
    )

def test_evidence_sort_uses_final_score_not_raw_logit() -> None:
    fake_indexer = types.ModuleType("ingestion.indexer")
    fake_indexer.embed_query = lambda _: [0.0]
    fake_indexer.get_collection = lambda: None
    sys.modules["ingestion.indexer"] = fake_indexer

    module_name = "retrieval.hybrid_search"
    sys.modules.pop(module_name, None)
    hybrid = importlib.import_module(module_name)

    original_verify = hybrid.verify_chunks
    try:
        hybrid.verify_chunks = lambda query, candidates, minimum_score: [
            {
                **candidate,
                "evidenceScore": 0.5,
                "evidenceSupported": False,
                "evidenceHardFailures": [],
            }
            for candidate in candidates
        ]
        results = hybrid._apply_evidence_verification(
            "test",
            [
                {
                    "chunkId": "high-final",
                    "score": 0.80,
                    "baseScore": 0.85,
                    "rerankerApplied": True,
                    "rerankerRawScore": -2.0,
                    "rerankerScore": 0.1,
                },
                {
                    "chunkId": "high-raw",
                    "score": 0.55,
                    "baseScore": 0.30,
                    "rerankerApplied": True,
                    "rerankerRawScore": 8.0,
                    "rerankerScore": 1.0,
                },
            ],
            min_score=0.0,
        )
    finally:
        hybrid.verify_chunks = original_verify

    assert [item["chunkId"] for item in results] == ["high-final", "high-raw"]


def main() -> int:
    test_cross_encoder_is_blended_not_absolute()
    test_low_weight_prevents_confident_reranker_takeover()
    test_full_union_is_sent_to_reranker()
    test_post_rerank_gate_rejects_unsupported_resurrection()
    test_evidence_sort_uses_final_score_not_raw_logit()
    print("Reranker pipeline tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
