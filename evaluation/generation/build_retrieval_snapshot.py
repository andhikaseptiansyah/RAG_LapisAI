"""Capture one ranked retrieval result set for a fair three-model comparison."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

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


def load_existing(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {}
    return {
        str(item.get("id") or ""): item
        for item in items
        if isinstance(item, dict) and item.get("id")
    }


def compact_candidate(candidate: Any, rank: int) -> dict[str, Any]:
    item = candidate if isinstance(candidate, dict) else {}
    return {
        "rank": rank,
        "chunk_id": item.get("chunkId"),
        "document": item.get("documentName"),
        "page": item.get("page"),
        "score": item.get("score"),
        "base_score": item.get("baseScore"),
        "semantic_score": item.get("semanticScore"),
        "keyword_score": item.get("keywordScore"),
        "evidence_supported": item.get("evidenceSupported"),
        "evidence_score": item.get("evidenceScore"),
        "answerability_accepted": item.get("answerabilityAccepted"),
        "answerability_strictly_supported": item.get("answerabilityStrictlySupported"),
        "answerability_evidence_selected": item.get("answerabilityEvidenceSelected"),
    }


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
    previous = load_existing(output) if args.resume else {}

    preflight()
    items: list[dict[str, Any]] = []
    for index, question in enumerate(questions, start=1):
        qid = str(question["id"])
        if qid in previous:
            print(f"[{index}/{len(questions)}] {qid} resume")
            items.append(previous[qid])
            continue

        print(f"[{index}/{len(questions)}] {qid} retrieval")
        started = time.perf_counter()
        response = post_json(
            RETRIEVAL_DEBUG_URL,
            {"question": question["question"], "topK": top_k},
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        final_candidates = [
            compact_candidate(item, rank)
            for rank, item in enumerate(response.get("finalCandidates") or [], start=1)
        ]
        items.append({
            "id": qid,
            "question": question["question"],
            "language": question.get("language"),
            "answerable": question.get("answerable"),
            "expected_sources": question.get("references") or [],
            "top_k": top_k,
            "ranked_candidates": final_candidates,
            "query_variants": response.get("queryVariants") or {},
            "baseline_decision": response.get("baselineDecision") or {},
            "retrieval_mode": response.get("retrievalMode") or "original",
            "retrieval_query": response.get("retrievalQuery") or question["question"],
            "retrieval_time_ms": elapsed_ms,
            "build_version": response.get("buildVersion"),
        })
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps({"dataset": dataset_summary(questions), "top_k": top_k, "items": items}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"dataset": dataset_summary(questions), "top_k": top_k, "items": items}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Retrieval snapshot: {output}")


if __name__ == "__main__":
    main()
