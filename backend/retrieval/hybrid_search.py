from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from ingestion.indexer import embed_query, get_collection

try:
    from ingestion.indexer import embed_texts as _native_embed_texts
except ImportError:  # pragma: no cover - dependency-free unit-test stubs.
    _native_embed_texts = None
from api.progress import emit_progress
from retrieval.answerability import apply_answerability_gate, assess_answerability
from retrieval.evidence_verifier import verify_chunks
from retrieval.query_expansion import build_query_variants, expand_query
from retrieval.reranker import rerank_candidates, warmup_reranker
from retrieval.scoring import hybrid_base_score
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
    meaningful_short_tokens = {"it", "ti", "ai", "hr", "qa", "id", "en"}
    return [
        token
        for token in tokens
        if token not in STOPWORDS
        and (
            len(token) > 2
            or token in meaningful_short_tokens
            or re.fullmatch(r"[a-z]+\d+", token) is not None
        )
    ]


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


def embed_query_batch(queries: list[str]) -> list[list[float]]:
    """Embed query variants in one model call when the runtime supports it."""
    if not queries:
        return []
    if _native_embed_texts is not None:
        return _native_embed_texts(queries)
    return [embed_query(query) for query in queries]


def _query_result_group(payload: dict, field: str, index: int) -> list[Any]:
    values = payload.get(field) or []
    if not isinstance(values, list) or not values:
        return []
    if isinstance(values[0], list):
        return values[index] if index < len(values) else []
    return values if index == 0 else []


def semantic_search(query: str, top_k: int = 20) -> list[dict]:
    """Search every independent language variant and merge by best cosine score."""
    collection = get_collection()

    try:
        total_records = collection.count()
    except Exception:
        total_records = 0

    if total_records <= 0:
        return []

    variants = build_query_variants(query) or [str(query or "").strip()]
    embeddings = embed_query_batch(variants)
    valid_pairs = [
        (variant, embedding)
        for variant, embedding in zip(variants, embeddings)
        if embedding
    ]
    if not valid_pairs:
        return []

    result = collection.query(
        query_embeddings=[embedding for _, embedding in valid_pairs],
        n_results=min(top_k, total_records),
        include=["documents", "metadatas", "distances"],
    )
    merged: dict[str, dict[str, Any]] = {}
    per_variant_scores: dict[str, dict[str, float]] = defaultdict(dict)

    for variant_index, (search_query, _) in enumerate(valid_pairs):
        ids = _query_result_group(result, "ids", variant_index)
        documents = _query_result_group(result, "documents", variant_index)
        metadatas = _query_result_group(result, "metadatas", variant_index)
        distances = _query_result_group(result, "distances", variant_index)

        for rank, chunk_id in enumerate(ids):
            distance = _safe_float(
                distances[rank] if rank < len(distances) else 1.0,
                1.0,
            )
            score = _clamp(1.0 - distance)
            per_variant_scores[str(chunk_id)][search_query] = round(score, 6)
            existing = merged.get(str(chunk_id))
            if existing is not None and score <= _safe_float(existing.get("semanticScore")):
                continue

            metadata = metadatas[rank] if rank < len(metadatas) else {}
            merged[str(chunk_id)] = {
                "chunkId": chunk_id,
                "content": documents[rank] if rank < len(documents) else "",
                "metadata": metadata or {},
                "semanticScore": score,
                "semanticRank": rank,
                "semanticVariantIndex": variant_index,
                "semanticQueryVariant": search_query,
                "expandedQuery": expand_query(query),
            }

    rows = list(merged.values())
    rows.sort(
        key=lambda row: (
            _safe_float(row.get("semanticScore")),
            -int(row.get("semanticRank") or 0),
        ),
        reverse=True,
    )
    for rank, row in enumerate(rows):
        row["semanticRank"] = rank
        row["semanticVariantScores"] = per_variant_scores.get(str(row.get("chunkId")), {})
    return rows[:top_k]

def bm25_search(query: str, top_k: int = 20) -> list[dict]:
    """Run BM25 per language variant and keep each chunk's strongest score."""
    records = _get_all_records()
    ids = records.get("ids") or []
    documents = records.get("documents") or []
    metadatas = records.get("metadatas") or []

    if not ids or not documents:
        return []

    searchable_documents = []
    for doc, meta in zip(documents, metadatas):
        meta = meta or {}
        searchable_documents.append(
            f"{meta.get('filename', '')} page {meta.get('page', '')} {doc}"
        )
    corpus_tokens = [_tokenize(doc) for doc in searchable_documents]

    variants = build_query_variants(query) or [str(query or "").strip()]
    best_scores = [0.0 for _ in ids]
    best_variants = ["" for _ in ids]
    variant_scores: list[dict[str, float]] = [dict() for _ in ids]

    bm25 = BM25Okapi(corpus_tokens) if BM25Okapi is not None else None
    for search_query in variants:
        query_tokens = _tokenize(search_query)
        if bm25 is not None and query_tokens:
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

        for idx, raw_score in enumerate(normalized_scores):
            score = _clamp(raw_score)
            variant_scores[idx][search_query] = round(score, 6)
            if score > best_scores[idx]:
                best_scores[idx] = score
                best_variants[idx] = search_query

    ranked_indexes = sorted(
        range(len(ids)),
        key=lambda idx: best_scores[idx],
        reverse=True,
    )[:top_k]

    rows: list[dict] = []
    for rank, idx in enumerate(ranked_indexes):
        rows.append(
            {
                "chunkId": ids[idx],
                "content": documents[idx],
                "metadata": metadatas[idx] or {},
                "keywordScore": _clamp(best_scores[idx]),
                "keywordRank": rank,
                "keywordQueryVariant": best_variants[idx],
                "keywordVariantScores": variant_scores[idx],
                "expandedQuery": expand_query(query),
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
    emit_progress(
        "semantic_search",
        "active",
        "Menjalankan semantic search",
        detail=f"Memeriksa hingga {candidate_k} kandidat per varian kueri.",
    )
    semantic_rows = semantic_search(query, top_k=candidate_k)
    emit_progress(
        "semantic_search",
        "completed",
        "Semantic search selesai",
        detail=f"Ditemukan {len(semantic_rows)} kandidat semantik.",
        metadata={"candidateCount": len(semantic_rows)},
    )

    emit_progress(
        "bm25_search",
        "active",
        "Menjalankan BM25 keyword search",
        detail=f"Memeriksa hingga {candidate_k} kandidat berbasis kata kunci.",
    )
    keyword_rows = bm25_search(query, top_k=candidate_k)
    emit_progress(
        "bm25_search",
        "completed",
        "BM25 keyword search selesai",
        detail=f"Ditemukan {len(keyword_rows)} kandidat kata kunci.",
        metadata={"candidateCount": len(keyword_rows)},
    )

    merged: dict[str, dict] = {}
    weighted_scores: dict[str, float] = defaultdict(float)
    tie_breakers: dict[str, float] = defaultdict(float)

    for row in semantic_rows:
        chunk_id = row["chunkId"]
        merged[chunk_id] = {**merged.get(chunk_id, {}), **row}
        tie_breakers[chunk_id] += _rrf_score(row.get("semanticRank", candidate_k))

    for row in keyword_rows:
        chunk_id = row["chunkId"]
        merged[chunk_id] = {**merged.get(chunk_id, {}), **row}
        tie_breakers[chunk_id] += _rrf_score(row.get("keywordRank", candidate_k))

    for chunk_id, row in merged.items():
        # Normalize over active signals. For a cross-language query, BM25 can be
        # exactly zero while the multilingual embedding is strongly relevant.
        # The old fixed weighted sum multiplied that semantic score by 0.68 and
        # could trigger a false pre-rerank refusal. When both signals exist, this
        # remains mathematically identical to the original 68/32 blend.
        weighted_scores[chunk_id] = hybrid_base_score(
            row.get("semanticScore", 0.0),
            row.get("keywordScore", 0.0),
        )
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

    emit_progress(
        "hybrid_search",
        "completed",
        "Pencarian hybrid selesai",
        detail=f"Gabungan semantic search dan BM25 menghasilkan {len(results)} kandidat unik.",
        metadata={
            "candidateCount": len(results),
            "semanticCount": len(semantic_rows),
            "keywordCount": len(keyword_rows),
        },
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




def _pre_rerank_may_defer(decision) -> bool:
    """Defer only soft chunking/bundle failures to the final gate.

    Missing concepts, values, years, contradictions, and weak base retrieval
    remain hard rejections. The final post-rerank answerability gate is still
    authoritative.
    """
    failed = set(getattr(decision, "failed_checks", ()) or ())
    soft_failures = {
        "supported_evidence",
        "no_coherent_single_chunk_evidence",
        "ambiguous_top_margin",
    }
    return bool(failed) and failed.issubset(soft_failures)


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
        emit_progress(
            "answerability_precheck",
            "active",
            "Memeriksa answerability awal",
            detail=f"Memvalidasi {len(candidates)} kandidat sebelum reranking.",
            metadata={"candidateCount": len(candidates)},
        )
        baseline_verified = _apply_evidence_verification(
            clean_query,
            [dict(candidate) for candidate in candidates],
            min_score=min_score,
        )
        pre_rerank_decision = assess_answerability(
            clean_query,
            baseline_verified,
        )
        pre_rerank_deferred = (
            not pre_rerank_decision.answerable
            and _pre_rerank_may_defer(pre_rerank_decision)
        )
        emit_progress(
            "answerability_precheck",
            "completed"
            if pre_rerank_decision.answerable or pre_rerank_deferred
            else "failed",
            "Answerability awal selesai",
            detail=(
                f"{len(baseline_verified)} kandidat lolos pemeriksaan awal."
                if pre_rerank_decision.answerable
                else (
                    "Pemeriksaan awal bersifat lunak dan diteruskan ke reranking."
                    if pre_rerank_deferred
                    else f"Pemeriksaan awal menolak kandidat: {pre_rerank_decision.reason}"
                )
            ),
            metadata={
                "candidateCount": len(baseline_verified),
                "answerable": bool(pre_rerank_decision.answerable),
                "deferred": pre_rerank_deferred,
            },
        )
        if not pre_rerank_decision.answerable:
            if pre_rerank_deferred:
                print(
                    "[ANSWERABILITY] Pre-rerank soft failure deferred to final gate: "
                    f"{pre_rerank_decision.reason}"
                )
            else:
                print(
                    "[ANSWERABILITY] Pre-rerank veto rejected query: "
                    f"{pre_rerank_decision.reason}"
                )
                return []

    if use_reranker:
        # The configured MMARCO cross-encoder is multilingual, so score the
        # original user question. Semantic/BM25 retrieval still uses expansion,
        # while reranking avoids extra expansion terms that can dilute intent.
        emit_progress(
            "reranking",
            "active",
            "Melakukan reranking",
            detail=f"Memeriksa {len(candidates)} kandidat dokumen.",
            metadata={"candidateCount": len(candidates)},
        )
        candidates = rerank_candidates(
            clean_query,
            candidates,
        )
        emit_progress(
            "reranking",
            "completed",
            "Reranking selesai",
            detail=f"{len(candidates)} kandidat telah diurutkan ulang berdasarkan relevansi.",
            metadata={"candidateCount": len(candidates)},
        )

    if verify_evidence:
        emit_progress(
            "evidence_validation",
            "active",
            "Memvalidasi bukti",
            detail=f"Memeriksa kesesuaian konsep, tanggal, angka, dan istilah pada {len(candidates)} kandidat.",
            metadata={"candidateCount": len(candidates)},
        )
        candidates = _apply_evidence_verification(
            clean_query,
            candidates,
            min_score=min_score,
        )
        emit_progress(
            "evidence_validation",
            "completed",
            "Validasi bukti selesai",
            detail=f"{len(candidates)} kandidat lolos pemeriksaan bukti.",
            metadata={"candidateCount": len(candidates)},
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
        emit_progress(
            "answerability",
            "active",
            "Memeriksa answerability",
            detail=f"Menilai apakah {len(candidates)} bukti cukup untuk menjawab pertanyaan.",
            metadata={"candidateCount": len(candidates)},
        )
        candidates = apply_answerability_gate(clean_query, candidates)
        emit_progress(
            "answerability",
            "completed" if candidates else "failed",
            "Pemeriksaan answerability selesai",
            detail=(
                f"{len(candidates)} kandidat memenuhi syarat jawaban."
                if candidates
                else "Tidak ada kandidat yang memenuhi syarat jawaban."
            ),
            metadata={"candidateCount": len(candidates), "answerable": bool(candidates)},
        )

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
