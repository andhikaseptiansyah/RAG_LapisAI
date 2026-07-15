from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from ingestion.indexer import embed_query, get_collection
from retrieval.answerability import apply_answerability_gate, assess_answerability
from retrieval.evidence_verifier import verify_chunks
from retrieval.query_expansion import expand_query
from retrieval.reranker import rerank_candidates, warmup_reranker
from uploads.config import (
    ANSWERABILITY_PRE_RERANK_VETO,
    ENABLE_ANSWERABILITY_GATE,
    ENABLE_EVIDENCE_VERIFICATION,
    ENABLE_RERANKER,
    EVIDENCE_WEIGHT,
    MIN_EVIDENCE_SCORE,
    MIN_RESULT_SCORE,
    RERANKER_CANDIDATES,
    RETRIEVAL_WARMUP_QUERY,
)

try:
    from rank_bm25 import BM25Okapi
except Exception:  # pragma: no cover - fallback if dependency is unavailable.
    BM25Okapi = None

STOPWORDS = {
    "apa", "apakah", "itu", "adalah", "jelaskan", "tentang", "dokumen", "file",
    "yang", "dan", "atau", "di", "ke", "dari", "untuk", "dengan", "pada",
    "sebutkan", "saja", "sebagai", "bahan", "subjek", "bagaimana", "berapa",
    "what", "is", "are", "the", "a", "an", "of", "to", "in", "on", "for",
    "how", "which", "when", "where", "who",
}

INVENTORY_FIELD_TERMS = [
    "kode aset", "nama barang", "merk", "merek", "tipe", "lokasi barang",
    "owner", "pemilik alat", "jumlah barang", "barang masuk", "barang keluar",
    "stok", "persediaan",
]


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9]+", str(text or "").lower())
    return [token for token in tokens if len(token) > 2 and token not in STOPWORDS]


def _important_tokens(query: str) -> list[str]:
    return _tokenize(query)


def _is_inventory_query(query: str) -> bool:
    text = str(query or "").lower()
    tokens = set(_tokenize(text))
    hints = {
        "data", "barang", "gudang", "inventori", "inventory", "pencatatan",
        "persediaan", "aset", "stok", "warehouse",
    }
    return (
        bool(tokens.intersection(hints))
        or "pencatatan barang" in text
        or "barang di gudang" in text
    )


def _inventory_field_score(text: str) -> float:
    lower = str(text or "").lower()
    hits = sum(
        1
        for term in INVENTORY_FIELD_TERMS
        if re.search(rf"\b{re.escape(term)}\b", lower, flags=re.I)
    )
    if hits >= 7:
        return 0.88
    if hits >= 5:
        return 0.84
    if hits >= 3:
        return 0.78
    return 0.0


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank + 1)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: Any) -> float:
    score = _safe_float(value, 0.0)
    return max(0.0, min(score, 1.0))


def _exact_token_coverage(query: str, text: str) -> float:
    query_tokens = _important_tokens(query)
    if not query_tokens:
        return 0.0
    text_lower = str(text or "").lower()
    matched = 0
    for token in query_tokens:
        if re.search(rf"\b{re.escape(token)}\b", text_lower, flags=re.I):
            matched += 1
    return matched / max(len(query_tokens), 1)


def _get_all_records() -> dict:
    collection = get_collection()
    return collection.get(include=["documents", "metadatas"])


def semantic_search(query: str, top_k: int = 20) -> list[dict]:
    collection = get_collection()

    try:
        total_records = collection.count()
    except Exception:
        total_records = 0

    if total_records <= 0:
        return []

    search_query = expand_query(query)
    query_embedding = embed_query(search_query)
    if not query_embedding:
        return []

    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, total_records),
        include=["documents", "metadatas", "distances"],
    )

    ids = result.get("ids", [[]])[0] or []
    documents = result.get("documents", [[]])[0] or []
    metadatas = result.get("metadatas", [[]])[0] or []
    distances = result.get("distances", [[]])[0] or []

    rows: list[dict] = []
    for index, chunk_id in enumerate(ids):
        distance = _safe_float(
            distances[index] if index < len(distances) else 1.0,
            1.0,
        )
        score = _clamp(1.0 - distance)
        metadata = metadatas[index] if index < len(metadatas) else {}
        rows.append(
            {
                "chunkId": chunk_id,
                "content": documents[index] if index < len(documents) else "",
                "metadata": metadata or {},
                "semanticScore": score,
                "semanticRank": index,
                "expandedQuery": search_query,
            }
        )

    return rows


def bm25_search(query: str, top_k: int = 20) -> list[dict]:
    records = _get_all_records()
    ids = records.get("ids") or []
    documents = records.get("documents") or []
    metadatas = records.get("metadatas") or []

    if not ids or not documents:
        return []

    search_query = expand_query(query)
    query_tokens = _tokenize(search_query)

    searchable_documents = []
    for doc, meta in zip(documents, metadatas):
        meta = meta or {}
        searchable_documents.append(
            f"{meta.get('filename', '')} page {meta.get('page', '')} {doc}"
        )

    corpus_tokens = [_tokenize(doc) for doc in searchable_documents]

    if BM25Okapi is not None and query_tokens:
        bm25 = BM25Okapi(corpus_tokens)
        raw_scores = bm25.get_scores(query_tokens)
        max_score = max(raw_scores) if len(raw_scores) else 0
        normalized_scores = [
            float(score) / float(max_score) if max_score else 0.0
            for score in raw_scores
        ]
    else:
        query_set = set(query_tokens)
        normalized_scores = []
        for tokens in corpus_tokens:
            token_set = set(tokens)
            overlap = len(query_set.intersection(token_set))
            normalized_scores.append(overlap / max(len(query_set), 1))

    ranked_indexes = sorted(
        range(len(ids)),
        key=lambda idx: normalized_scores[idx],
        reverse=True,
    )[:top_k]

    rows: list[dict] = []
    for rank, idx in enumerate(ranked_indexes):
        rows.append(
            {
                "chunkId": ids[idx],
                "content": documents[idx],
                "metadata": metadatas[idx] or {},
                "keywordScore": _clamp(normalized_scores[idx]),
                "keywordRank": rank,
                "expandedQuery": search_query,
            }
        )

    return rows


def _base_hybrid_candidates(
    query: str,
    *,
    candidate_k: int,
) -> list[dict[str, Any]]:
    """Merge semantic top-N and BM25 top-N without early score filtering.

    Early filtering can remove a passage that the cross-encoder would correctly
    promote. Final thresholding therefore happens only after reranking and
    evidence verification.
    """
    semantic_rows = semantic_search(query, top_k=candidate_k)
    keyword_rows = bm25_search(query, top_k=candidate_k)

    merged: dict[str, dict] = {}
    weighted_scores: dict[str, float] = defaultdict(float)
    tie_breakers: dict[str, float] = defaultdict(float)

    for row in semantic_rows:
        chunk_id = row["chunkId"]
        merged[chunk_id] = {**merged.get(chunk_id, {}), **row}
        weighted_scores[chunk_id] += 0.68 * _clamp(row.get("semanticScore", 0.0))
        tie_breakers[chunk_id] += _rrf_score(row.get("semanticRank", candidate_k))

    for row in keyword_rows:
        chunk_id = row["chunkId"]
        merged[chunk_id] = {**merged.get(chunk_id, {}), **row}
        weighted_scores[chunk_id] += 0.32 * _clamp(row.get("keywordScore", 0.0))
        tie_breakers[chunk_id] += _rrf_score(row.get("keywordRank", candidate_k))

    for chunk_id, row in merged.items():
        metadata = row.get("metadata", {}) or {}
        searchable_text = f"{metadata.get('filename', '')} {row.get('content', '')}"
        exact_coverage = _exact_token_coverage(query, searchable_text)
        row["exactTokenCoverage"] = round(exact_coverage, 6)

        if exact_coverage >= 1.0:
            weighted_scores[chunk_id] = max(weighted_scores[chunk_id], 0.86)
        elif exact_coverage >= 0.67:
            weighted_scores[chunk_id] = max(weighted_scores[chunk_id], 0.78)

        inventory_score = (
            _inventory_field_score(searchable_text)
            if _is_inventory_query(query)
            else 0.0
        )
        row["inventoryFieldScore"] = round(inventory_score, 6)
        if inventory_score >= 0.84:
            weighted_scores[chunk_id] = max(
                weighted_scores[chunk_id],
                inventory_score,
            )

    ranked = sorted(
        weighted_scores,
        key=lambda chunk_id: (
            weighted_scores[chunk_id],
            tie_breakers[chunk_id],
        ),
        reverse=True,
    )

    results: list[dict[str, Any]] = []
    for chunk_id in ranked:
        score = _clamp(weighted_scores[chunk_id])
        row = merged[chunk_id]
        metadata = row.get("metadata", {}) or {}
        results.append(
            {
                "chunkId": chunk_id,
                "documentName": metadata.get("filename", "-"),
                "page": metadata.get("page", "-"),
                "chunkIndex": metadata.get("chunk_index"),
                "content": row.get("content", ""),
                "score": round(score, 6),
                "baseScore": round(score, 6),
                "semanticScore": round(_clamp(row.get("semanticScore", 0.0)), 6),
                "semanticRank": row.get("semanticRank"),
                "keywordScore": round(_clamp(row.get("keywordScore", 0.0)), 6),
                "keywordRank": row.get("keywordRank"),
                "exactTokenCoverage": round(
                    _clamp(row.get("exactTokenCoverage", 0.0)),
                    6,
                ),
                "inventoryFieldScore": round(
                    _clamp(row.get("inventoryFieldScore", 0.0)),
                    6,
                ),
                "expandedQuery": row.get("expandedQuery") or expand_query(query),
                "metadata": metadata,
            }
        )

    return results


def _apply_evidence_verification(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    min_score: float,
) -> list[dict[str, Any]]:
    if not candidates:
        return candidates

    annotated = verify_chunks(
        query,
        candidates,
        minimum_score=MIN_EVIDENCE_SCORE,
    )
    safe_weight = max(0.0, min(float(EVIDENCE_WEIGHT), 1.0))
    accepted: list[dict[str, Any]] = []

    for candidate in annotated:
        score = _clamp(candidate.get("score"))
        evidence_score = _clamp(candidate.get("evidenceScore"))
        hard_failures = candidate.get("evidenceHardFailures") or []
        contradictions = candidate.get("evidenceContradictions") or []
        evidence_supported = bool(candidate.get("evidenceSupported"))

        # Missing evidence in one chunk may be supplied by another chunk. Only
        # explicit contradictions are removed before bundle-level answerability.
        if hard_failures or contradictions:
            continue

        # Evidence verifier tidak boleh menghukum kandidat bilingual hanya karena
        # lexical coverage rendah. Kandidat tanpa kontradiksi tetap dipertahankan;
        # evidence yang positif digunakan sebagai bonus, bukan penalty.
        if evidence_supported:
            blended = (
                (1.0 - safe_weight) * score
                + safe_weight * evidence_score
            )
            adjusted = max(score, _clamp(blended))
        else:
            adjusted = score
        if adjusted < min_score:
            continue

        accepted.append(
            {
                **candidate,
                "preEvidenceScore": round(score, 6),
                "score": round(adjusted, 6),
            }
        )

    return sorted(
        accepted,
        key=lambda row: (
            # Preserve the calibrated blended order. Evidence may add a bonus,
            # but a raw cross-encoder logit must never override the final score.
            _safe_float(row.get("score")),
            _safe_float(row.get("evidenceScore")),
            _safe_float(row.get("rerankerScore")),
            _safe_float(row.get("baseScore")),
            _safe_float(row.get("rerankerRawScore")),
        ),
        reverse=True,
    )


def hybrid_search(
    query: str,
    top_k: int = 5,
    candidate_k: int = 20,
    min_score: float = MIN_RESULT_SCORE,
    *,
    use_reranker: bool = ENABLE_RERANKER,
    verify_evidence: bool = ENABLE_EVIDENCE_VERIFICATION,
    apply_answerability: bool = ENABLE_ANSWERABILITY_GATE,
) -> list[dict]:
    """Run semantic top-N + BM25 top-N, cross-encoder reranking, then top-k.

    Default production flow:
      semantic top 20 + BM25 top 20 -> union -> cross-encoder -> evidence -> top 5
    """
    clean_query = str(query or "").strip()
    if not clean_query:
        return []

    requested_top_k = max(int(top_k), 1)
    per_retriever_k = max(
        int(candidate_k),
        requested_top_k,
        int(RERANKER_CANDIDATES if use_reranker else 0),
    )

    # Each retriever contributes top-N independently. Their union can contain up
    # to 2N unique chunks and is intentionally not truncated before reranking.
    candidates = _base_hybrid_candidates(
        clean_query,
        candidate_k=per_retriever_k,
    )

    pre_rerank_decision = None
    if (
        use_reranker
        and apply_answerability
        and verify_evidence
        and ANSWERABILITY_PRE_RERANK_VETO
    ):
        # Evaluate answerability on the original hybrid ranking before the
        # cross-encoder is allowed to change scores. If the baseline retrieval
        # cannot establish that the corpus contains an answer, reranking may not
        # resurrect the query. This guarantees that a reranker can improve order
        # but cannot introduce a new false positive on its own.
        baseline_verified = _apply_evidence_verification(
            clean_query,
            [dict(candidate) for candidate in candidates],
            min_score=min_score,
        )
        pre_rerank_decision = assess_answerability(
            clean_query,
            baseline_verified,
        )
        if not pre_rerank_decision.answerable:
            print(
                "[ANSWERABILITY] Pre-rerank veto rejected query: "
                f"{pre_rerank_decision.reason}"
            )
            return []

    if use_reranker:
        # The configured MMARCO cross-encoder is multilingual, so score the
        # original user question. Semantic/BM25 retrieval still uses expansion,
        # while reranking avoids extra expansion terms that can dilute intent.
        candidates = rerank_candidates(
            clean_query,
            candidates,
        )

    if verify_evidence:
        candidates = _apply_evidence_verification(
            clean_query,
            candidates,
            min_score=min_score,
        )
    else:
        candidates = [
            candidate
            for candidate in candidates
            if _clamp(candidate.get("score")) >= min_score
        ]

    # Ranking and answerability are separate responsibilities. The reranker may
    # improve order, but this final gate can reject the entire result set when
    # the corpus lacks an exact detail requested by the user.
    if apply_answerability and verify_evidence:
        candidates = apply_answerability_gate(clean_query, candidates)

    if candidates and pre_rerank_decision is not None:
        pre_metadata = pre_rerank_decision.to_dict()
        candidates = [
            {
                **candidate,
                "preRerankAnswerabilityAccepted": True,
                "preRerankAnswerabilityScore": pre_rerank_decision.score,
                "preRerankAnswerabilityReason": pre_rerank_decision.reason,
                "preRerankAnswerabilityDiagnostics": pre_metadata,
            }
            for candidate in candidates
        ]

    return candidates[:requested_top_k]


def warmup_retrieval() -> dict[str, bool]:
    """Load embedding and reranker models during API startup."""
    embedding_ready = False
    reranker_ready = False

    try:
        embedding_ready = bool(embed_query(RETRIEVAL_WARMUP_QUERY))
    except Exception as exc:  # pragma: no cover - depends on local model files.
        print(f"[RETRIEVAL] Embedding warm-up failed: {exc}")

    if ENABLE_RERANKER:
        reranker_ready = warmup_reranker()

    return {
        "embedding": embedding_ready,
        "reranker": reranker_ready,
    }
