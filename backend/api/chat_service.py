from __future__ import annotations

import hashlib
import re
import time
from typing import Any

from api.answer_formatter import (
    answer_text_only,
    build_evidence_excerpt,
    build_generation_evidence,
    build_refusal_answer,
    build_safe_extractive_answer,
    build_small_talk_answer,
    build_sources,
    build_verified_scalar_answer,
    has_answerable_evidence,
    is_refusal_answer,
    is_small_talk,
    top_confidence,
)
from api.build_info import BUILD_VERSION
from api.cancellation import raise_if_cancelled
from api.follow_up_service import build_dataset_follow_up_question
from api.grounding_validator import validate_grounded_answer
from api.language import answer_matches_requested_language, resolve_response_language
from api.model_router import build_grounded_answer, resolve_provider
from api.progress import emit_progress, progress_scope
from ingestion.indexer import get_collection
from retrieval.answerability import apply_answerability_gate
from retrieval.context_selector import select_context_bundle
from retrieval.hybrid_search import (
    _apply_evidence_verification,
    _base_hybrid_candidates,
    hybrid_search,
)
from retrieval.query_expansion import (
    build_bridge_query,
    build_natural_bridge_query,
    normalize_text,
    requires_language_bridge,
)
from uploads.config import (
    CONTEXT_REDUNDANCY_THRESHOLD,
    CONTEXT_SECONDARY_SCORE_RATIO,
    MAX_GENERATION_CONTEXTS,
    MAX_SOURCE_CITATIONS,
    MIN_RESULT_SCORE,
)


class EvaluationSnapshotContractError(RuntimeError):
    """Raised when a locked evaluation snapshot cannot be replayed safely."""

def _sanitize_verified_scalar_answer(answer: str) -> str:
    """Clean malformed or duplicated deterministic scalar fallbacks.

    Some formatter patches may accidentally wrap an already formatted answer
    inside another template, producing text such as:

        "... dalam waktu Berdasarkan ketentuan pada dokumen, ... 4 jam."

    The chat service treats ``build_verified_scalar_answer`` as the final
    formatter. This guard keeps the innermost complete answer, removes repeated
    sentences, and limits deterministic fallbacks to two concise sentences.
    It does not invent or change any fact extracted from the evidence.
    """
    clean = re.sub(r"\s+", " ", str(answer or "")).strip()
    if not clean:
        return ""

    # Locate repeated answer-opening markers. If a formatter wrapped an answer
    # that was already complete, the later marker begins the valid inner answer.
    markers = (
        "Berdasarkan ketentuan pada dokumen,",
        "Berdasarkan dokumen sumber,",
        "Berdasarkan dokumen yang telah diindeks,",
        "According to the source document,",
        "According to the indexed document,",
        "According to the document,",
    )
    marker_positions: list[int] = []
    lowered = clean.casefold()

    for marker in markers:
        marker_lower = marker.casefold()
        start = 0
        while True:
            position = lowered.find(marker_lower, start)
            if position < 0:
                break
            marker_positions.append(position)
            start = position + len(marker_lower)

    marker_positions = sorted(set(marker_positions))
    if len(marker_positions) >= 2:
        clean = clean[marker_positions[-1]:].strip()

    # Remove exact and near-duplicate explanatory sentences while preserving
    # the factual sentence and one short explanation.
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", clean)
        if sentence.strip()
    ]

    kept: list[str] = []
    normalized_kept: list[str] = []
    for sentence in sentences:
        normalized = re.sub(r"[^a-z0-9]+", " ", sentence.casefold()).strip()
        if not normalized:
            continue

        duplicate = False
        for existing in normalized_kept:
            # Treat sentences as duplicates when one largely contains the
            # other. This catches repeated "Jangka waktu tersebut..." clauses.
            shorter, longer = sorted((normalized, existing), key=len)
            if shorter == longer or (
                len(shorter) >= 35
                and shorter in longer
            ):
                duplicate = True
                break

            sentence_tokens = set(normalized.split())
            existing_tokens = set(existing.split())
            overlap = len(sentence_tokens & existing_tokens)
            union = len(sentence_tokens | existing_tokens)
            if union and overlap / union >= 0.72:
                duplicate = True
                break

        if duplicate:
            continue

        kept.append(sentence)
        normalized_kept.append(normalized)

        if len(kept) >= 2:
            break

    return " ".join(kept).strip() if kept else clean



def _strict_chunk(chunk: dict[str, Any]) -> bool:
    return bool(
        chunk.get("answerabilityAccepted") is True
        and chunk.get("answerabilityEvidenceSelected", True)
        and chunk.get(
            "answerabilityStrictlySupported",
            chunk.get("evidenceSupported") is True
            or chunk.get("answerabilityCoherentEvidence") is True,
        )
        and not chunk.get("evidenceHardFailures")
        and not chunk.get("evidenceHardContradictions")
        and (
            not chunk.get("answerabilityRequiresCoherentEvidence")
            or chunk.get("answerabilityCoherentEvidence") is True
        )
    )


def _build_generation_contexts(
    question: str,
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return the exact, strictly supported evidence used by generation."""
    contexts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for chunk in chunks[:MAX_GENERATION_CONTEXTS]:
        if not _strict_chunk(chunk):
            continue
        if not chunk.get("contextSelected", True):
            continue

        metadata = chunk.get("metadata") or {}
        document_name = str(
            chunk.get("documentName")
            or chunk.get("document_name")
            or metadata.get("filename")
            or ""
        ).strip()
        page = chunk.get("page", metadata.get("page"))
        raw_content = str(chunk.get("content") or metadata.get("content") or "").strip()

        excerpt = build_generation_evidence(
            question,
            raw_content,
            max_chars=1400,
        ) or raw_content
        if len(excerpt) > 1400:
            excerpt = excerpt[:1400].rsplit(" ", 1)[0].strip() + "…"
        if not excerpt:
            continue

        chunk_id = str(
            chunk.get("chunkId")
            or chunk.get("chunk_id")
            or metadata.get("chunk_id")
            or ""
        )
        key = (document_name.casefold(), str(page or ""), excerpt.casefold())
        if key in seen:
            continue
        seen.add(key)
        contexts.append(
            {
                "text": excerpt,
                "document_name": document_name,
                "page": page,
                "chunk_id": chunk_id,
            }
        )

    return contexts


def _build_language_retry_chunks(
    question: str,
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a minimal evidence bundle for a language-only generation retry.

    The first generation can fail when a local model copies the source language
    from a long chunk. Retrying with the same verified facts in a smaller bundle
    improves translation compliance without changing retrieval thresholds or
    adding any outside information.
    """
    retry_chunks: list[dict[str, Any]] = []
    for chunk in chunks[:2]:
        raw_content = str(chunk.get("content") or "").strip()
        excerpt = build_evidence_excerpt(
            question,
            raw_content,
            max_chars=700,
        ) or raw_content
        if not excerpt:
            continue

        cloned = dict(chunk)
        cloned["content"] = excerpt
        metadata = dict(chunk.get("metadata") or {})
        metadata["content"] = excerpt
        cloned["metadata"] = metadata
        retry_chunks.append(cloned)
    return retry_chunks


def _refusal_payload(
    started_at: float,
    language: str,
    *,
    failure_stage: str,
    generation_mode: str = "retrieval_refusal",
    model: str = "retrieval-refusal",
    retrieval_mode: str = "refused",
    retrieval_query: str = "",
    generation_contexts: list[dict[str, Any]] | None = None,
    preserve_generation_contexts: bool = False,
    failure_reason: str = "",
    rejected_native_answer: str = "",
    citation_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contexts = list(generation_contexts or [])
    payload = {
        "answer": build_refusal_answer(language),
        "confidence": 0.0,
        "sources": [],
        # Production refusals do not expose internal context. The dedicated
        # evaluation endpoint may preserve it so context metrics and failure
        # taxonomy remain accurate after generation or citation validation.
        "generation_contexts": contexts if preserve_generation_contexts else [],
        "context_count_before_failure": len(contexts),
        "follow_up_question": None,
        "response_time_ms": int(round((time.perf_counter() - started_at) * 1000)),
        "model": model,
        "generation_mode": generation_mode,
        "language": language,
        "buildVersion": BUILD_VERSION,
        "retrieval_mode": retrieval_mode,
        "retrieval_query": retrieval_query,
        "failure_stage": failure_stage,
    }
    if failure_reason:
        payload["failure_reason"] = failure_reason
    if preserve_generation_contexts and rejected_native_answer:
        # Evaluation-only diagnostics. Production refusals must not expose a
        # rejected answer that failed the public citation contract.
        payload["rejected_native_answer"] = answer_text_only(
            rejected_native_answer
        )
    if preserve_generation_contexts and citation_validation:
        payload["citation_validation"] = dict(citation_validation)
    return payload


def _strict_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only candidates that can safely be used for generation."""
    return [candidate for candidate in candidates if _strict_chunk(candidate)]


def _strip_retrieval_annotations(candidate: dict[str, Any]) -> dict[str, Any]:
    """Remove stale gate metadata before validating a candidate for a new query.

    Bridge candidates may already carry evidence and answerability fields created
    for the English retrieval query. Reusing those fields while checking the
    original Indonesian question can preserve a rejection that no longer applies.
    The raw retrieval scores and document metadata are retained.
    """
    cloned = dict(candidate)
    for key in list(cloned):
        if (
            key.startswith("evidence")
            or key.startswith("answerability")
            or key.startswith("minimumEvidence")
            or key.startswith("preRerankAnswerability")
        ):
            cloned.pop(key, None)
    return cloned


def _validate_for_original_question(
    question: str,
    candidates: list[dict[str, Any]],
    *,
    requested_k: int,
    bridge_query: str,
    stage: str,
) -> list[dict[str, Any]]:
    """Apply all safety gates again using the user's original question."""
    if not candidates:
        return []

    clean_candidates = [
        _strip_retrieval_annotations(candidate)
        for candidate in candidates
    ]
    reverified = _apply_evidence_verification(
        question,
        clean_candidates,
        min_score=MIN_RESULT_SCORE,
    )
    reverified = apply_answerability_gate(question, reverified)
    strict = _strict_candidates(reverified)
    if not strict:
        return []

    strict_ids = {
        str(candidate.get("chunkId") or candidate.get("chunk_id") or "")
        for candidate in strict
    }
    accepted = [
        {
            **candidate,
            "retrievalFallbackApplied": stage != "original",
            "retrievalFallbackStage": stage,
            "retrievalOriginalQuestion": question,
            "retrievalBridgeQuery": bridge_query,
        }
        for candidate in reverified
        if str(candidate.get("chunkId") or candidate.get("chunk_id") or "")
        in strict_ids
    ]
    accepted.sort(
        key=lambda candidate: (
            float(candidate.get("score") or 0.0),
            float(candidate.get("evidenceScore") or 0.0),
            float(candidate.get("baseScore") or 0.0),
        ),
        reverse=True,
    )
    return accepted[:requested_k]



def _materialize_locked_candidates(
    question: str,
    locked_candidates: list[dict[str, Any]],
    *,
    requested_k: int,
) -> list[dict[str, Any]]:
    """Hydrate candidates while preserving the captured retrieval decision.

    The benchmark records chunk identifiers and calibrated retrieval scores once,
    then every evaluated model receives the same evidence. Document text is read
    back from Chroma by ID; client-provided text is never trusted. The content
    hash and strict gate state are verified, but the evidence and answerability
    gates are deliberately not run a second time. Re-running them here made a
    supposedly locked snapshot non-deterministic, especially for bilingual
    bridge queries.
    """
    if not locked_candidates:
        return []

    normalized: list[tuple[str, dict[str, Any]]] = []
    seen_ids: set[str] = set()
    for item in locked_candidates:
        if not isinstance(item, dict):
            continue
        chunk_id = str(item.get("chunkId") or item.get("chunk_id") or "").strip()
        if not chunk_id or chunk_id in seen_ids:
            continue
        seen_ids.add(chunk_id)
        normalized.append((chunk_id, item))

    if not normalized:
        return []

    collection = get_collection()
    result = collection.get(
        ids=[chunk_id for chunk_id, _ in normalized],
        include=["documents", "metadatas"],
    )
    result_ids = list(result.get("ids") or [])
    documents = list(result.get("documents") or [])
    metadatas = list(result.get("metadatas") or [])
    hydrated_by_id: dict[str, tuple[str, dict[str, Any]]] = {}
    for index, chunk_id in enumerate(result_ids):
        hydrated_by_id[str(chunk_id)] = (
            str(documents[index] if index < len(documents) else ""),
            dict(metadatas[index] if index < len(metadatas) and metadatas[index] else {}),
        )

    hydrated: list[dict[str, Any]] = []
    for rank, (chunk_id, compact) in enumerate(normalized, start=1):
        record = hydrated_by_id.get(chunk_id)
        if record is None:
            raise EvaluationSnapshotContractError(
                f"Snapshot chunk is missing from the active Chroma index: {chunk_id}"
            )
        content, metadata = record
        if not content.strip():
            raise EvaluationSnapshotContractError(
                f"Snapshot chunk has empty indexed content: {chunk_id}"
            )
        expected_hash = str(
            compact.get("contentSha256")
            or compact.get("content_sha256")
            or ""
        ).strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise EvaluationSnapshotContractError(
                f"Snapshot chunk is missing a valid content SHA-256: {chunk_id}"
            )
        actual_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if expected_hash != actual_hash:
            raise EvaluationSnapshotContractError(
                "Snapshot chunk content changed after capture: "
                f"{chunk_id}. Rebuild the retrieval snapshot."
            )

        def number(*keys: str, default: float = 0.0) -> float:
            for key in keys:
                value = compact.get(key)
                if value is None:
                    continue
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
            return default

        def flag(*keys: str, default: bool = False) -> bool:
            for key in keys:
                if key not in compact or compact.get(key) is None:
                    continue
                value = compact.get(key)
                if isinstance(value, str):
                    return value.strip().casefold() in {"1", "true", "yes", "on"}
                return bool(value)
            return default

        def items(*keys: str) -> list[Any]:
            for key in keys:
                value = compact.get(key)
                if isinstance(value, (list, tuple)):
                    return list(value)
            return []

        def object_value(*keys: str) -> dict[str, Any]:
            for key in keys:
                value = compact.get(key)
                if isinstance(value, dict):
                    return dict(value)
            return {}

        required_gate_fields = {
            "evidenceSupported": ("evidenceSupported", "evidence_supported"),
            "evidenceHardFailures": (
                "evidenceHardFailures",
                "evidence_hard_failures",
            ),
            "evidenceHardContradictions": (
                "evidenceHardContradictions",
                "evidence_hard_contradictions",
            ),
            "answerabilityAccepted": (
                "answerabilityAccepted",
                "answerability_accepted",
            ),
            "answerabilityStrictlySupported": (
                "answerabilityStrictlySupported",
                "answerability_strictly_supported",
            ),
            "answerabilityEvidenceSelected": (
                "answerabilityEvidenceSelected",
                "answerability_evidence_selected",
            ),
            "answerabilityRequiresCoherentEvidence": (
                "answerabilityRequiresCoherentEvidence",
                "answerability_requires_coherent_evidence",
            ),
            "answerabilityCoherentEvidence": (
                "answerabilityCoherentEvidence",
                "answerability_coherent_evidence",
            ),
        }
        missing_gate_fields = [
            field
            for field, keys in required_gate_fields.items()
            if not any(key in compact and compact.get(key) is not None for key in keys)
        ]
        if missing_gate_fields:
            raise EvaluationSnapshotContractError(
                f"Snapshot candidate {chunk_id} is missing locked gate fields: "
                + ", ".join(missing_gate_fields)
                + ". Rebuild the retrieval snapshot."
            )

        score = number("score", default=0.0)
        base_score = number("baseScore", "base_score", default=score)
        semantic_score = number("semanticScore", "semantic_score", default=0.0)
        keyword_score = number("keywordScore", "keyword_score", default=0.0)
        document_name = str(
            metadata.get("filename")
            or compact.get("documentName")
            or compact.get("document")
            or "-"
        )
        coverage_query = str(
            compact.get("snapshotRetrievalQuery")
            or compact.get("snapshot_retrieval_query")
            or question
        ).strip()
        candidate = {
            "chunkId": chunk_id,
            "documentName": document_name,
            "page": metadata.get("page", compact.get("page", "-")),
            "chunkIndex": metadata.get("chunk_index"),
            "content": content,
            "score": score,
            "baseScore": base_score,
            "semanticScore": semantic_score,
            "keywordScore": keyword_score,
            "semanticRank": rank - 1,
            "keywordRank": rank - 1,
            "exactTokenCoverage": number(
                "exactTokenCoverage",
                "exact_token_coverage",
                default=0.0,
            ),
            "inventoryFieldScore": number(
                "inventoryFieldScore",
                "inventory_field_score",
                default=0.0,
            ),
            "rerankerApplied": flag(
                "rerankerApplied",
                "reranker_applied",
                default=False,
            ),
            "rerankerScore": number(
                "rerankerScore",
                "reranker_score",
                default=0.0,
            ),
            "rerankerRawScore": number(
                "rerankerRawScore",
                "reranker_raw_score",
                default=0.0,
            ),
            "rerankerRank": number(
                "rerankerRank",
                "reranker_rank",
                default=float(rank),
            ),
            "semanticQueryVariant": compact.get("semanticQueryVariant")
            or compact.get("semantic_query_variant"),
            "keywordQueryVariant": compact.get("keywordQueryVariant")
            or compact.get("keyword_query_variant"),
            "rerankerQueryVariant": compact.get("rerankerQueryVariant")
            or compact.get("reranker_query_variant"),
            "evidenceSupported": flag(
                "evidenceSupported",
                "evidence_supported",
            ),
            "evidenceScore": number(
                "evidenceScore",
                "evidence_score",
                default=0.0,
            ),
            "evidenceHardFailures": items(
                "evidenceHardFailures",
                "evidence_hard_failures",
            ),
            "evidenceHardContradictions": items(
                "evidenceHardContradictions",
                "evidence_hard_contradictions",
            ),
            "evidenceContradictions": items(
                "evidenceContradictions",
                "evidence_contradictions",
            ),
            "evidenceMissingRequirements": items(
                "evidenceMissingRequirements",
                "evidence_missing_requirements",
            ),
            "answerabilityAccepted": flag(
                "answerabilityAccepted",
                "answerability_accepted",
            ),
            "answerabilityStrictlySupported": flag(
                "answerabilityStrictlySupported",
                "answerability_strictly_supported",
            ),
            "answerabilityEvidenceSelected": flag(
                "answerabilityEvidenceSelected",
                "answerability_evidence_selected",
            ),
            "answerabilityScore": number(
                "answerabilityScore",
                "answerability_score",
                default=0.0,
            ),
            "answerabilityScoreMargin": number(
                "answerabilityScoreMargin",
                "answerability_score_margin",
                default=0.0,
            ),
            "answerabilityRequirementCoverage": number(
                "answerabilityRequirementCoverage",
                "answerability_requirement_coverage",
                default=0.0,
            ),
            "answerabilityConceptCoverage": number(
                "answerabilityConceptCoverage",
                "answerability_concept_coverage",
                default=0.0,
            ),
            "answerabilityRequiresCoherentEvidence": flag(
                "answerabilityRequiresCoherentEvidence",
                "answerability_requires_coherent_evidence",
            ),
            "answerabilityCoherentEvidence": flag(
                "answerabilityCoherentEvidence",
                "answerability_coherent_evidence",
            ),
            "answerabilityDiagnostics": object_value(
                "answerabilityDiagnostics",
                "answerability_diagnostics",
            ),
            "snapshotRetrievalMode": compact.get("snapshotRetrievalMode")
            or compact.get("snapshot_retrieval_mode"),
            "snapshotRetrievalQuery": coverage_query,
            "metadata": metadata,
            "evaluationSnapshotRank": rank,
            "evaluationSnapshotLocked": True,
        }
        if not _strict_chunk(candidate):
            raise EvaluationSnapshotContractError(
                f"Snapshot candidate was not strictly accepted at capture: {chunk_id}. "
                "Rebuild the retrieval snapshot."
            )
        hydrated.append(candidate)

    if not hydrated:
        return []
    return hydrated[:requested_k]


def _retrieve_with_language_fallback(
    question: str,
    *,
    top_k: int,
) -> tuple[list[dict[str, Any]], str, str]:
    """Retrieve normally, then replay a failing Indonesian query in English.

    The bridge pass uses the same complete pipeline as a direct English question,
    because that exact path is known to work in the application. Before the
    bridge candidates are validated against the original Indonesian question,
    all stale evidence and answerability annotations are removed.
    """
    requested_k = max(top_k, MAX_GENERATION_CONTEXTS)

    raise_if_cancelled()
    primary = hybrid_search(question, top_k=requested_k)
    primary_strict = _strict_candidates(primary)
    if primary_strict:
        return primary_strict[:requested_k], "original", question

    if not requires_language_bridge(question):
        return [], "original", question

    bridge_query = build_natural_bridge_query(question) or build_bridge_query(question)
    if not bridge_query or normalize_text(bridge_query) == normalize_text(question):
        return [], "original", question

    emit_progress(
        "bilingual_query",
        "active",
        "Menjalankan query bilingual",
        detail="Bukti ketat belum ditemukan pada kueri awal. Sistem mencoba jalur pencarian Inggris lalu memvalidasinya kembali terhadap pertanyaan asli.",
    )

    bridge_top_k = max(requested_k * 2, 10)
    bridge_candidate_k = max(bridge_top_k * 4, 40)
    print(
        "[RETRIEVAL] primary Indonesian path has no strict evidence; "
        f"replaying direct English path: {bridge_query}"
    )

    # This deliberately mirrors a successful user-entered English question,
    # including reranking, evidence verification, and English answerability.
    raise_if_cancelled()
    bridge_candidates = hybrid_search(
        bridge_query,
        top_k=bridge_top_k,
        candidate_k=bridge_candidate_k,
        apply_answerability=True,
    )
    accepted = _validate_for_original_question(
        question,
        bridge_candidates,
        requested_k=requested_k,
        bridge_query=bridge_query,
        stage="bridge_direct_english_path",
    )
    if accepted:
        emit_progress(
            "bilingual_query",
            "completed",
            "Query bilingual selesai",
            detail=f"{len(accepted)} kandidat diterima setelah validasi ulang terhadap pertanyaan asli.",
            metadata={"candidateCount": len(accepted)},
        )
        return accepted, "natural_language_bridge", bridge_query

    print(
        "[RETRIEVAL] direct English path was not accepted after Indonesian "
        "revalidation; checking raw English semantic+BM25 union"
    )
    raw_candidate_k = max(bridge_candidate_k * 2, 80)
    raise_if_cancelled()
    raw_candidates = _base_hybrid_candidates(
        bridge_query,
        candidate_k=raw_candidate_k,
    )
    accepted = _validate_for_original_question(
        question,
        raw_candidates,
        requested_k=requested_k,
        bridge_query=bridge_query,
        stage="bridge_raw_union",
    )
    if accepted:
        emit_progress(
            "bilingual_query",
            "completed",
            "Query bilingual selesai",
            detail=f"{len(accepted)} kandidat diterima dari gabungan semantic search dan BM25 bilingual.",
            metadata={"candidateCount": len(accepted)},
        )
        return accepted, "natural_language_bridge_raw", bridge_query

    emit_progress(
        "bilingual_query",
        "failed",
        "Query bilingual selesai tanpa bukti",
        detail="Tidak ada kandidat bilingual yang lolos validasi terhadap pertanyaan asli.",
        metadata={"candidateCount": 0},
    )
    return [], "natural_language_bridge_raw", bridge_query


def retrieve_verified_chunks(
    question: str,
    *,
    top_k: int = 5,
) -> tuple[list[dict[str, Any]], str, str]:
    """Public retrieval entry point shared by chat and evaluation diagnostics."""
    return _retrieve_with_language_fallback(question, top_k=top_k)


def _progress_source_metadata(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        document_name = str(
            chunk.get("documentName")
            or chunk.get("document_name")
            or metadata.get("filename")
            or "-"
        ).strip()
        page = chunk.get("page", metadata.get("page"))
        paragraph_start = chunk.get("paragraphStart", metadata.get("paragraph_start"))
        paragraph_end = chunk.get("paragraphEnd", metadata.get("paragraph_end"))
        key = (document_name.casefold(), str(page or ""), str(paragraph_start or ""))
        if key in seen:
            continue
        seen.add(key)
        try:
            confidence = round(max(0.0, min(float(chunk.get("score") or 0.0), 1.0)), 4)
        except (TypeError, ValueError):
            confidence = 0.0
        sources.append({
            "documentName": document_name,
            "page": page,
            "paragraphStart": paragraph_start,
            "paragraphEnd": paragraph_end,
            "confidence": confidence,
        })
    return sources


def _format_progress_sources(sources: list[dict[str, Any]]) -> str:
    labels: list[str] = []
    for source in sources[:3]:
        location: list[str] = []
        if source.get("page") not in (None, "", "-"):
            location.append(f"halaman {source['page']}")
        start = source.get("paragraphStart")
        end = source.get("paragraphEnd")
        if start not in (None, ""):
            location.append(
                f"paragraf {start}"
                if end in (None, "", start)
                else f"paragraf {start}-{end}"
            )
        confidence = source.get("confidence")
        if isinstance(confidence, (int, float)) and confidence > 0:
            location.append(f"confidence {round(float(confidence) * 100)}%")
        suffix = f", {', '.join(location)}" if location else ""
        labels.append(f"{source['documentName']}{suffix}")
    return "; ".join(labels)


def _run_chat_impl(
    question: str,
    *,
    top_k: int = 5,
    language: str = "AUTO",
    model: str | None = None,
    evaluation_mode: bool = False,
    locked_candidates: list[dict[str, Any]] | None = None,
    cancel_event: Any | None = None,
) -> dict[str, Any]:
    """Run one grounded chat turn using a strict evidence-first pipeline."""
    started_at = time.perf_counter()
    raise_if_cancelled(cancel_event)
    requested_language = str(language or "AUTO").upper()
    normalized_language = resolve_response_language(question, requested_language)
    selected_provider = resolve_provider(model)
    language_label = "Indonesia" if normalized_language == "ID" else "Inggris"
    emit_progress(
        "analyze",
        "completed",
        "Pertanyaan berhasil dianalisis",
        detail=f"Bahasa: {language_label}. Model yang dipilih: {selected_provider.title()}.",
        metadata={
            "language": normalized_language,
            "provider": selected_provider,
        },
    )

    if is_small_talk(question):
        emit_progress(
            "generate",
            "active",
            "Menyiapkan jawaban langsung",
            detail="Pertanyaan dikenali sebagai percakapan ringan sehingga retrieval dokumen tidak dijalankan.",
        )
        answer = answer_text_only(build_small_talk_answer(question, language=normalized_language))
        emit_progress(
            "generate",
            "completed",
            "Jawaban langsung selesai",
            detail="Jawaban sistem telah disiapkan tanpa pencarian dokumen.",
        )
        return {
            "answer": answer,
            "confidence": 1.0,
            "sources": [],
            "generation_contexts": [],
            "follow_up_question": None,
            "response_time_ms": int(round((time.perf_counter() - started_at) * 1000)),
            "model": "system-small-talk",
            "generation_mode": "system_small_talk",
            "language": normalized_language,
            "buildVersion": BUILD_VERSION,
        }

    raise_if_cancelled(cancel_event)
    emit_progress(
        "retrieval",
        "active",
        "Mencari dokumen relevan",
        detail="Menjalankan pencarian hybrid pada indeks dokumen yang sudah tersedia.",
    )
    if locked_candidates is not None:
        requested_k = max(top_k, MAX_GENERATION_CONTEXTS)
        retrieval_mode = "evaluation_snapshot"
        retrieval_query = str(
            next(
                (
                    candidate.get("snapshotRetrievalQuery")
                    or candidate.get("snapshot_retrieval_query")
                    for candidate in locked_candidates
                    if isinstance(candidate, dict)
                    and (
                        candidate.get("snapshotRetrievalQuery")
                        or candidate.get("snapshot_retrieval_query")
                    )
                ),
                question,
            )
        )
        try:
            retrieved_chunks = _materialize_locked_candidates(
                question,
                locked_candidates,
                requested_k=requested_k,
            )
        except EvaluationSnapshotContractError as error:
            payload = _refusal_payload(
                started_at,
                normalized_language,
                failure_stage="evaluation_snapshot_contract",
                generation_mode="evaluation_snapshot_contract_failure",
                model="evaluation-snapshot-contract",
                retrieval_mode=retrieval_mode,
                retrieval_query=retrieval_query,
                failure_reason="snapshot_contract_rejected",
            )
            payload["pipeline_error"] = str(error)
            return payload
    else:
        retrieved_chunks, retrieval_mode, retrieval_query = _retrieve_with_language_fallback(
            question,
            top_k=top_k,
        )

    # Context selection must never reintroduce candidates that the final
    # answerability gate marked as non-evidence. The previous implementation
    # selected from all accepted rows, so a high-scoring but non-strict row
    # could displace the only valid evidence and create a false refusal.
    strict_retrieved_chunks = _strict_candidates(retrieved_chunks)

    raise_if_cancelled(cancel_event)
    emit_progress(
        "retrieval",
        "completed" if strict_retrieved_chunks else "failed",
        "Pencarian dokumen selesai",
        detail=(
            f"Pencarian menghasilkan {len(strict_retrieved_chunks)} kandidat terverifikasi."
            if strict_retrieved_chunks
            else "Pencarian selesai tanpa kandidat yang lolos seluruh pemeriksaan."
        ),
        metadata={
            "candidateCount": len(strict_retrieved_chunks),
            "retrievalMode": retrieval_mode,
        },
    )
    emit_progress(
        "context_selection",
        "active",
        "Memilih konteks",
        detail=f"Menyeleksi konteks dari {len(strict_retrieved_chunks)} kandidat terverifikasi.",
        metadata={"candidateCount": len(strict_retrieved_chunks)},
    )
    chunks = select_context_bundle(
        question,
        strict_retrieved_chunks,
        max_contexts=MAX_GENERATION_CONTEXTS,
        minimum_contexts=min(2, MAX_GENERATION_CONTEXTS),
        redundancy_threshold=CONTEXT_REDUNDANCY_THRESHOLD,
        secondary_score_ratio=CONTEXT_SECONDARY_SCORE_RATIO,
    )

    selected_source_metadata = _progress_source_metadata(chunks)
    selected_source_label = _format_progress_sources(selected_source_metadata)
    emit_progress(
        "context_selection",
        "completed" if chunks else "failed",
        "Pemilihan konteks selesai",
        detail=(
            f"Ditemukan {len(selected_source_metadata)} sumber relevan: {selected_source_label}."
            if selected_source_metadata
            else "Tidak ada konteks yang memenuhi kriteria pemilihan."
        ),
        metadata={
            "sourceCount": len(selected_source_metadata),
            "sources": selected_source_metadata,
        },
    )

    bundle_answerable = has_answerable_evidence(chunks)
    if not chunks or not bundle_answerable:
        payload = _refusal_payload(
            started_at,
            normalized_language,
            failure_stage="context_or_answerability",
            retrieval_mode=retrieval_mode,
            retrieval_query=retrieval_query,
            failure_reason="no_strict_answerable_context",
        )
        return payload

    confidence = round(top_confidence(chunks, question=question), 4)
    generation_contexts = _build_generation_contexts(question, chunks)
    if confidence <= 0.0 or not generation_contexts:
        payload = _refusal_payload(
            started_at,
            normalized_language,
            failure_stage="confidence_or_generation_context",
            retrieval_mode=retrieval_mode,
            retrieval_query=retrieval_query,
            generation_contexts=generation_contexts,
            preserve_generation_contexts=evaluation_mode,
            failure_reason=(
                "non_positive_confidence"
                if confidence <= 0.0
                else "empty_generation_context"
            ),
        )
        return payload

    print(
        f"[CHAT] provider={selected_provider} language={normalized_language} "
        f"contexts={len(generation_contexts)} confidence={confidence:.3f}"
    )

    verified_scalar_answer = ""
    if not evaluation_mode:
        raw_verified_scalar_answer = answer_text_only(
            build_verified_scalar_answer(
                question,
                chunks,
                language=normalized_language,
            )
        )
        verified_scalar_answer = _sanitize_verified_scalar_answer(
            raw_verified_scalar_answer
        )
        if (
            raw_verified_scalar_answer
            and verified_scalar_answer != raw_verified_scalar_answer
        ):
            print(
                "[CHAT] cleaned duplicated verified scalar fallback: "
                f"{verified_scalar_answer}"
            )

    used_extractive_fallback = False
    used_language_retry = False
    used_verified_scalar_fallback = False

    raise_if_cancelled(cancel_event)
    emit_progress(
        "generate",
        "active",
        "Menyusun jawaban",
        detail=f"{selected_provider.title()} sedang menyusun jawaban dari {len(generation_contexts)} bukti terpilih.",
        metadata={
            "provider": selected_provider,
            "contextCount": len(generation_contexts),
        },
    )
    native_answer = answer_text_only(
        build_grounded_answer(
            question,
            chunks,
            language=normalized_language,
            model=selected_provider,
            evaluation_mode=evaluation_mode,
        )
    )

    raise_if_cancelled(cancel_event)
    answer = native_answer
    native_language_ok = bool(
        answer and answer_matches_requested_language(answer, normalized_language)
    )
    if evaluation_mode:
        if not answer:
            raise RuntimeError("Native model generation returned an empty answer")
        if not native_language_ok:
            raise RuntimeError("Native model generation used the wrong output language")
    elif not answer or is_refusal_answer(answer) or not native_language_ok:
        retry_chunks = _build_language_retry_chunks(question, chunks)
        if retry_chunks:
            retry_answer = answer_text_only(
                build_grounded_answer(
                    question,
                    retry_chunks,
                    language=normalized_language,
                    model=selected_provider,
                    evaluation_mode=False,
                )
            )
            if (
                retry_answer
                and not is_refusal_answer(retry_answer)
                and answer_matches_requested_language(
                    retry_answer,
                    normalized_language,
                )
            ):
                answer = retry_answer
                used_language_retry = True

        if not used_language_retry:
            if verified_scalar_answer:
                answer = verified_scalar_answer
                used_verified_scalar_fallback = True
                print(
                    "[CHAT] native expansion unavailable; using the verified "
                    f"scalar fallback: {answer}"
                )
            else:
                extractive_answer = answer_text_only(
                    build_safe_extractive_answer(
                        question,
                        chunks,
                        language=normalized_language,
                    )
                )
                answer = extractive_answer
                used_extractive_fallback = bool(
                    extractive_answer
                    and not is_refusal_answer(extractive_answer)
                    and answer_matches_requested_language(
                        extractive_answer,
                        normalized_language,
                    )
                )

    if answer and not answer_matches_requested_language(answer, normalized_language):
        print(
            "[CHAT] fallback answer rejected because it does not match "
            f"requested language={normalized_language}"
        )
        answer = ""
        used_extractive_fallback = False
        used_verified_scalar_fallback = False

    if used_language_retry:
        generation_mode = "language_repair_retry"
    elif used_extractive_fallback:
        generation_mode = "extractive_fallback"
    elif used_verified_scalar_fallback:
        generation_mode = "verified_scalar_fallback"
    else:
        generation_mode = "native_model"

    if used_extractive_fallback or used_verified_scalar_fallback:
        emit_progress(
            "grounding",
            "completed",
            "Grounding deterministik selesai",
            detail=(
                "Jawaban dibentuk langsung dari bukti terpilih tanpa menambahkan klaim bebas dari model."
            ),
            metadata={
                "supported": True,
                "mode": generation_mode,
            },
        )

    emit_progress(
        "generate",
        "completed" if answer and not is_refusal_answer(answer) else "failed",
        "Penyusunan jawaban selesai",
        detail=f"Mode jawaban: {generation_mode.replace('_', ' ')}.",
        metadata={
            "provider": selected_provider,
            "generationMode": generation_mode,
        },
    )

    raise_if_cancelled(cancel_event)
    emit_progress(
        "citations",
        "active",
        "Menyiapkan sitasi",
        detail="Menyusun nama dokumen, halaman, paragraf, dan confidence dari bukti terpilih.",
    )
    sources = build_sources(
        chunks,
        question=question,
        limit=MAX_SOURCE_CITATIONS,
        answer=answer,
    )

    citation_metadata = [
        {
            "documentName": source.get("document_name") or source.get("documentName") or "-",
            "page": source.get("page"),
            "paragraphStart": source.get("paragraph_start") or source.get("paragraphStart"),
            "paragraphEnd": source.get("paragraph_end") or source.get("paragraphEnd"),
            "confidence": source.get("score") or source.get("relevance_score") or source.get("relevanceScore"),
        }
        for source in sources
    ]
    citation_labels: list[str] = []
    for source in citation_metadata[:3]:
        location: list[str] = []
        if source.get("page") not in (None, "", "-"):
            location.append(f"halaman {source['page']}")
        paragraph_start = source.get("paragraphStart")
        paragraph_end = source.get("paragraphEnd")
        if paragraph_start not in (None, ""):
            location.append(
                f"paragraf {paragraph_start}"
                if paragraph_end in (None, "", paragraph_start)
                else f"paragraf {paragraph_start}-{paragraph_end}"
            )
        confidence_value = source.get("confidence")
        try:
            confidence_percent = round(float(confidence_value) * 100)
        except (TypeError, ValueError):
            confidence_percent = 0
        if confidence_percent > 0:
            location.append(f"confidence {confidence_percent}%")
        citation_labels.append(
            f"{source['documentName']}{', ' + ', '.join(location) if location else ''}"
        )

    emit_progress(
        "citations",
        "completed" if sources else "failed",
        "Sitasi selesai disiapkan",
        detail=(
            f"{len(sources)} sitasi: {'; '.join(citation_labels)}."
            if sources
            else "Tidak ada sitasi valid yang dapat ditampilkan."
        ),
        metadata={
            "sourceCount": len(sources),
            "sources": citation_metadata,
        },
    )

    answer_is_refusal = bool(answer and is_refusal_answer(answer))
    if not answer or answer_is_refusal or not sources:
        citation_validation: dict[str, Any] | None = None
        if not answer:
            failure_stage = "native_answer_empty"
            failure_reason = "native_model_returned_empty_answer"
            failure_generation_mode = "native_answer_empty"
        elif answer_is_refusal:
            failure_stage = "native_model_refusal"
            failure_reason = "native_model_returned_refusal"
            failure_generation_mode = "native_model_refusal"
        else:
            failure_stage = "citation_validation_failed"
            failure_reason = "generated_answer_has_no_valid_supporting_citation"
            failure_generation_mode = "citation_validation_failed"
            citation_validation = validate_grounded_answer(
                question,
                answer,
                chunks,
            ).to_dict()
        payload = _refusal_payload(
            started_at,
            normalized_language,
            failure_stage=failure_stage,
            generation_mode=failure_generation_mode,
            model=f"{selected_provider}-rag",
            retrieval_mode=retrieval_mode,
            retrieval_query=retrieval_query,
            generation_contexts=generation_contexts,
            preserve_generation_contexts=evaluation_mode,
            failure_reason=failure_reason,
            rejected_native_answer=(
                answer
                if failure_stage == "citation_validation_failed"
                else ""
            ),
            citation_validation=citation_validation,
        )
        return payload

    raise_if_cancelled(cancel_event)
    follow_up_question = build_dataset_follow_up_question(
        question=question,
        answer=answer,
        sources=sources,
        language=normalized_language,
    )

    return {
        "answer": answer,
        "confidence": confidence,
        "sources": sources,
        "generation_contexts": generation_contexts,
        "follow_up_question": follow_up_question,
        "response_time_ms": int(round((time.perf_counter() - started_at) * 1000)),
        "model": f"{selected_provider}-rag",
        "generation_mode": generation_mode,
        "language": normalized_language,
        "buildVersion": BUILD_VERSION,
        "retrieval_mode": retrieval_mode,
        "retrieval_query": retrieval_query,
        "failure_stage": None,
    }


def run_chat(
    question: str,
    *,
    top_k: int = 5,
    language: str = "AUTO",
    model: str | None = None,
    evaluation_mode: bool = False,
    locked_candidates: list[dict[str, Any]] | None = None,
    cancel_event: Any | None = None,
    progress_callback: Any | None = None,
) -> dict[str, Any]:
    """Run one chat turn and optionally stream safe operational progress."""
    with progress_scope(progress_callback):
        return _run_chat_impl(
            question,
            top_k=top_k,
            language=language,
            model=model,
            evaluation_mode=evaluation_mode,
            locked_candidates=locked_candidates,
            cancel_event=cancel_event,
        )
