"""Capture one ranked retrieval result set for a fair three-model comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:
        return False

try:
    from .dataset_utils import dataset_summary, load_ground_truth_files
    from .build_generation_dataset import post_json, preflight
except ImportError:
    from dataset_utils import dataset_summary, load_ground_truth_files
    from build_generation_dataset import post_json, preflight

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
EVALUATION_DIR = PROJECT_ROOT / "evaluation"
DEFAULT_DATASETS = [
    EVALUATION_DIR / "datasets" / "qna_english_user.csv",
    EVALUATION_DIR / "datasets" / "qna_indonesia_user.csv",
]
RETRIEVAL_DEBUG_URL = os.getenv(
    "LAPISAI_RETRIEVAL_DEBUG_URL",
    "http://localhost:8000/api/admin/retrieval-debug",
)
EVALUATION_READINESS_URL = os.getenv(
    "LAPISAI_EVALUATION_READINESS_URL",
    "http://localhost:8000/api/admin/evaluation/readiness",
)
SNAPSHOT_SCHEMA_VERSION = 4
LATENCY_MEASUREMENT_MODE = "single_strict_retrieval_without_debug_baseline"


def load_existing(
    path: Path,
    *,
    top_k: int,
) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    try:
        existing_top_k = (
            int(payload.get("top_k") or 0)
            if isinstance(payload, dict)
            else 0
        )
    except (TypeError, ValueError):
        existing_top_k = 0
    if (
        not isinstance(payload, dict)
        or payload.get("snapshot_schema_version") != SNAPSHOT_SCHEMA_VERSION
        or payload.get("latency_measurement_mode") != LATENCY_MEASUREMENT_MODE
        or existing_top_k != top_k
    ):
        print(
            "[SNAPSHOT] Existing snapshot uses an older contract; "
            "all retrieval rows will be recaptured."
        )
        return {}
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {}
    return {
        str(item.get("id") or ""): item
        for item in items
        if isinstance(item, dict) and item.get("id")
    }


def snapshot_item_matches_question(
    item: dict[str, Any],
    question: dict[str, Any],
    *,
    top_k: int,
) -> bool:
    question_text = str(question.get("question") or "")
    try:
        item_top_k = int(item.get("top_k") or 0)
    except (TypeError, ValueError):
        return False
    return bool(
        item.get("question") == question_text
        and item.get("question_sha256")
        == hashlib.sha256(question_text.encode("utf-8")).hexdigest()
        and str(item.get("language") or "").upper()
        == str(question.get("language") or "").upper()
        and bool(item.get("answerable")) == bool(question.get("answerable"))
        and item_top_k == top_k
        and item.get("latency_measurement_mode") == LATENCY_MEASUREMENT_MODE
    )


def compact_candidate(candidate: Any, rank: int) -> dict[str, Any]:
    item = candidate if isinstance(candidate, dict) else {}
    return {
        "rank": rank,
        "chunk_id": item.get("chunkId"),
        "document": item.get("documentName"),
        "page": item.get("page"),
        "content_sha256": item.get("contentSha256"),
        "score": item.get("score"),
        "base_score": item.get("baseScore"),
        "semantic_score": item.get("semanticScore"),
        "keyword_score": item.get("keywordScore"),
        "exact_token_coverage": item.get("exactTokenCoverage"),
        "inventory_field_score": item.get("inventoryFieldScore"),
        "reranker_applied": item.get("rerankerApplied"),
        "reranker_score": item.get("rerankerScore"),
        "reranker_raw_score": item.get("rerankerRawScore"),
        "reranker_rank": item.get("rerankerRank"),
        "semantic_query_variant": item.get("semanticQueryVariant"),
        "keyword_query_variant": item.get("keywordQueryVariant"),
        "reranker_query_variant": item.get("rerankerQueryVariant"),
        "reranker_query_variant_count": item.get("rerankerQueryVariantCount"),
        "evidence_supported": item.get("evidenceSupported"),
        "evidence_score": item.get("evidenceScore"),
        "evidence_hard_failures": item.get("evidenceHardFailures") or [],
        "evidence_hard_contradictions": item.get("evidenceHardContradictions") or [],
        "evidence_contradictions": item.get("evidenceContradictions") or [],
        "evidence_missing_requirements": item.get("evidenceMissingRequirements") or [],
        "answerability_accepted": item.get("answerabilityAccepted"),
        "answerability_strictly_supported": item.get("answerabilityStrictlySupported"),
        "answerability_evidence_selected": item.get("answerabilityEvidenceSelected"),
        "answerability_score": item.get("answerabilityScore"),
        "answerability_score_margin": item.get("answerabilityScoreMargin"),
        "answerability_requirement_coverage": item.get(
            "answerabilityRequirementCoverage"
        ),
        "answerability_concept_coverage": item.get("answerabilityConceptCoverage"),
        "answerability_requires_coherent_evidence": item.get(
            "answerabilityRequiresCoherentEvidence"
        ),
        "answerability_coherent_evidence": item.get(
            "answerabilityCoherentEvidence"
        ),
        "answerability_diagnostics": item.get("answerabilityDiagnostics") or {},
    }


def expected_document_names(questions: list[dict[str, Any]]) -> list[str]:
    """Return the unique source filenames required by answerable rows."""
    names: dict[str, str] = {}
    for question in questions:
        for reference in question.get("references") or []:
            if isinstance(reference, dict):
                document = str(reference.get("document") or "").strip()
            else:
                document = str(reference or "").strip()
            if document:
                names.setdefault(document.casefold(), document)
    return sorted(names.values(), key=str.casefold)


def assert_corpus_ready(questions: list[dict[str, Any]]) -> dict[str, Any]:
    expected_documents = expected_document_names(questions)
    status = post_json(
        EVALUATION_READINESS_URL,
        {"expectedDocuments": expected_documents},
    )
    if not status.get("ready"):
        missing = [
            str(document)
            for document in status.get("missingDocuments") or []
        ]
        missing_preview = ", ".join(missing[:10]) or "unknown"
        suffix = f" (+{len(missing) - 10} others)" if len(missing) > 10 else ""
        raise RuntimeError(
            "Corpus evaluasi belum siap pada collection Chroma aktif. "
            f"Indexed chunks={status.get('chunkCount', 0)}, "
            f"missing documents={missing_preview}{suffix}. "
            "Upload dan Index All seluruh corpus, lalu jalankan evaluasi lagi."
        )
    print(
        "[READINESS] PASS: "
        f"{status.get('expectedDocumentCount', len(expected_documents))} dokumen wajib, "
        f"{status.get('chunkCount', 0)} chunk terindeks."
    )
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", type=Path, action="append", dest="ground_truth_files")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    datasets = args.ground_truth_files or DEFAULT_DATASETS
    questions = load_ground_truth_files(datasets)
    top_k = max(1, min(int(args.top_k), 20))
    output = args.output.resolve()
    previous = load_existing(output, top_k=top_k) if args.resume else {}

    preflight()
    assert_corpus_ready(questions)
    items: list[dict[str, Any]] = []
    for index, question in enumerate(questions, start=1):
        qid = str(question["id"])
        if qid in previous and snapshot_item_matches_question(
            previous[qid],
            question,
            top_k=top_k,
        ):
            print(f"[{index}/{len(questions)}] {qid} resume")
            items.append(previous[qid])
            continue
        if qid in previous:
            print(f"[{index}/{len(questions)}] {qid} stale snapshot row; recapture")

        print(f"[{index}/{len(questions)}] {qid} retrieval")
        started = time.perf_counter()
        response = post_json(
            RETRIEVAL_DEBUG_URL,
            {
                "question": question["question"],
                "topK": top_k,
                # The strict production retrieval path already performs its
                # own pre-rerank answerability check. Repeating the standalone
                # debug baseline would run semantic/BM25 retrieval twice and
                # inflate the benchmark latency measurement.
                "includeBaselineDiagnostics": False,
            },
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        final_candidates = [
            compact_candidate(item, rank)
            for rank, item in enumerate(response.get("finalCandidates") or [], start=1)
        ]
        items.append({
            "id": qid,
            "question": question["question"],
            "question_sha256": hashlib.sha256(
                str(question["question"]).encode("utf-8")
            ).hexdigest(),
            "language": question.get("language"),
            "answerable": question.get("answerable"),
            "expected_sources": question.get("references") or [],
            "top_k": top_k,
            "ranked_candidates": final_candidates,
            "query_variants": response.get("queryVariants") or {},
            "baseline_decision": response.get("baselineDecision") or {},
            "baseline_diagnostics_included": bool(
                response.get("baselineDiagnosticsIncluded")
            ),
            "latency_measurement_mode": LATENCY_MEASUREMENT_MODE,
            "retrieval_mode": response.get("retrievalMode") or "original",
            "retrieval_query": response.get("retrievalQuery") or question["question"],
            "retrieval_time_ms": elapsed_ms,
            "build_version": response.get("buildVersion"),
        })
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
                    "latency_measurement_mode": LATENCY_MEASUREMENT_MODE,
                    "dataset": dataset_summary(questions),
                    "top_k": top_k,
                    "items": items,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
                "latency_measurement_mode": LATENCY_MEASUREMENT_MODE,
                "dataset": dataset_summary(questions),
                "top_k": top_k,
                "items": items,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Retrieval snapshot: {output}")


if __name__ == "__main__":
    main()
