from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
DEFAULT_GROUND_TRUTH = PROJECT_ROOT / "evaluation" / "ground_truth_qa.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "results"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Evaluation imports the exact same values used by the running application.
# There is no separate threshold, collection, embedding model, or path default here.
from uploads.config import (  # noqa: E402
    ANSWERABILITY_MIN_EVIDENCE_SCORE,
    ANSWERABILITY_MIN_SCORE_MARGIN,
    ANSWERABILITY_MIN_TOP_SCORE,
    ANSWERABILITY_REQUIRE_SUPPORTED_EVIDENCE,
    CHROMA_PATH,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    ENABLE_ANSWERABILITY_GATE,
    MIN_RESULT_SCORE,
    RERANKER_CANDIDATES,
    RERANKER_MODEL,
    RERANKER_WEIGHT,
    UPLOAD_DIR,
)

DEFAULT_CHROMA_PATH = Path(CHROMA_PATH)
DEFAULT_UPLOAD_DIR = Path(UPLOAD_DIR)
DEFAULT_MIN_SCORE = MIN_RESULT_SCORE

@dataclass(frozen=True)
class Reference:
    document: str
    page: str

    @property
    def document_key(self) -> str:
        return normalize_document(self.document)

    @property
    def page_key(self) -> tuple[str, str]:
        return self.document_key, normalize_page(self.page)

def normalize_document(value: Any) -> str:
    return Path(str(value or "").strip()).name.casefold()

def normalize_page(value: Any) -> str:
    text = str(value if value is not None else "").strip()
    try:
        number = float(text)
        if number.is_integer():
            return str(int(number))
    except (TypeError, ValueError):
        pass
    return text.casefold()

def parse_k_values(raw: str) -> list[int]:
    values: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid k value: {part!r}") from exc
        if value <= 0:
            raise argparse.ArgumentTypeError("Every k value must be greater than zero.")
        values.add(value)
    if not values:
        raise argparse.ArgumentTypeError("Provide at least one k value, for example 1,3,5.")
    return sorted(values)

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def detect_language(text: str) -> str:
    """Return a lightweight language label for report grouping.

    The official CSV does not include a language column. Its current questions are
    English, while this heuristic also keeps Indonesian additions reportable without
    requiring a schema change.
    """
    tokens = set(re.findall(r"[a-zA-ZÀ-ÿ]+", str(text or "").casefold()))
    indonesian_markers = {
        "apa", "apakah", "berapa", "bagaimana", "kapan", "siapa", "dimana",
        "berapa", "harus", "dalam", "dengan", "untuk", "karyawan", "hari",
    }
    return "id" if len(tokens.intersection(indonesian_markers)) >= 2 else "en"


def _default_csv_corpus_directory() -> str:
    if (PROJECT_ROOT / "documents").exists():
        return "documents"
    return "backend/uploads/files"


def load_csv_ground_truth(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    required = {"question", "expected_answer", "source_document"}
    fieldnames = set(rows[0].keys()) if rows else set()
    missing = required - fieldnames
    if missing:
        raise ValueError(
            "ground_truth_qa.csv is missing required column(s): "
            + ", ".join(sorted(missing))
        )
    if not rows:
        raise ValueError("The ground-truth CSV contains no questions.")

    items: list[dict[str, Any]] = []
    seen_questions: set[str] = set()
    for index, row in enumerate(rows, start=1):
        question = str(row.get("question") or "").strip()
        expected_answer = str(row.get("expected_answer") or "").strip()
        source_document = str(row.get("source_document") or "").strip()
        if not question or not expected_answer or not source_document:
            raise ValueError(
                f"CSV row {index + 1} must contain question, expected_answer, and source_document."
            )
        question_key = question.casefold()
        if question_key in seen_questions:
            raise ValueError(f"Duplicate question in CSV row {index + 1}: {question}")
        seen_questions.add(question_key)
        items.append(
            {
                "id": f"QA-{index:03d}",
                "split": "all",
                "category": Path(source_document).stem.split("_", 1)[0].casefold(),
                "language": detect_language(question),
                "difficulty": "unspecified",
                "question_type": "factual",
                "question": question,
                "answerable": True,
                "expected_answer": expected_answer,
                "expected_answer_keywords": [],
                "references": [{"document": source_document, "page": ""}],
            }
        )

    payload: dict[str, Any] = {
        "dataset_name": "Nusantara Dynamics Official Ground Truth Q&A",
        "version": "csv-official-30",
        "source_format": "csv",
        "evaluation_level": "document",
        "has_page_references": False,
        "has_unanswerable_questions": False,
        "corpus": {
            "document_directory": _default_csv_corpus_directory(),
            "included_prefixes": ["SOP_", "Report_", "Policy_", "TECH_", "FAQ_"],
        },
        "items": items,
    }
    return payload, items


def load_ground_truth(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not path.exists():
        raise FileNotFoundError(f"Ground-truth file not found: {path}")

    if path.suffix.casefold() == ".csv":
        return load_csv_ground_truth(path)

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("Ground-truth JSON must be an object containing an 'items' array.")

    items = payload["items"]
    if not items:
        raise ValueError("The ground-truth dataset contains no questions.")

    seen_ids: set[str] = set()
    has_page_references = False
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Ground-truth item #{index} is not an object.")
        question_id = str(item.get("id", "")).strip()
        question = str(item.get("question", "")).strip()
        if not question_id or not question:
            raise ValueError(f"Ground-truth item #{index} is missing id or question.")
        if question_id in seen_ids:
            raise ValueError(f"Duplicate ground-truth id: {question_id}")
        seen_ids.add(question_id)

        answerable = bool(item.get("answerable"))
        references = item.get("references") or []
        if answerable and not references:
            raise ValueError(f"Answerable item {question_id} has no references.")
        if not answerable and references:
            raise ValueError(f"Unanswerable item {question_id} must not have references.")
        has_page_references = has_page_references or any(
            str(reference.get("page") or "").strip() for reference in references
        )

    payload.setdefault("source_format", "json")
    payload.setdefault("has_page_references", has_page_references)
    payload.setdefault(
        "has_unanswerable_questions",
        any(not bool(item.get("answerable")) for item in items),
    )
    payload.setdefault("evaluation_level", "page" if has_page_references else "document")
    return payload, items

def filter_items(
    items: list[dict[str, Any]],
    split: str,
    limit: int | None,
) -> list[dict[str, Any]]:
    if split == "all":
        selected = list(items)
    else:
        selected = [item for item in items if item.get("split") == split]

    if limit is not None:
        selected = selected[:limit]

    if not selected:
        raise ValueError(f"No ground-truth questions found for split={split!r}.")
    return selected

def get_corpus_files(dataset: dict[str, Any]) -> list[Path]:
    corpus = dataset.get("corpus") or {}
    raw_directory = corpus.get("document_directory") or "backend/uploads/files"
    directory = Path(raw_directory)
    if not directory.is_absolute():
        directory = PROJECT_ROOT / directory

    prefixes = tuple(str(prefix) for prefix in (corpus.get("included_prefixes") or []))
    supported_extensions = {".pdf", ".docx", ".txt"}

    if not directory.exists():
        raise FileNotFoundError(f"Corpus directory not found: {directory}")

    files = [
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.casefold() in supported_extensions
        and (not prefixes or path.name.startswith(prefixes))
    ]
    return sorted(files, key=lambda path: path.name.casefold())

def import_backend_modules():
    try:
        from ingestion.indexer import get_collection  # type: ignore
        from retrieval.hybrid_search import hybrid_search  # type: ignore
        from uploads.ingest import ingest  # type: ignore
    except ModuleNotFoundError as exc:
        missing = exc.name or "a required package"
        raise RuntimeError(
            "Retrieval dependencies are not installed. Run this from the project root:\n"
            "  python -m pip install -r .\\backend\\requirements.txt\n"
            f"Missing module: {missing}"
        ) from exc
    return get_collection, hybrid_search, ingest

def indexed_document_names(collection: Any) -> set[str]:
    try:
        payload = collection.get(include=["metadatas"])
    except Exception as exc:
        raise RuntimeError(f"Unable to read the ChromaDB collection: {exc}") from exc

    names: set[str] = set()
    for metadata in payload.get("metadatas") or []:
        if metadata and metadata.get("filename"):
            names.add(normalize_document(metadata["filename"]))
    return names

def ensure_index(
    dataset: dict[str, Any],
    collection: Any,
    ingest: Any,
    index_missing: bool,
) -> dict[str, Any]:
    corpus_files = get_corpus_files(dataset)
    expected_names = {normalize_document(path.name) for path in corpus_files}
    indexed_names = indexed_document_names(collection)
    missing_files = [path for path in corpus_files if normalize_document(path.name) not in indexed_names]

    if missing_files and index_missing:
        print(f"Indexing {len(missing_files)} missing corpus document(s)...")
        for number, path in enumerate(missing_files, start=1):
            print(f"  [{number:02d}/{len(missing_files):02d}] {path.name}")
            ingest(str(path))
        indexed_names = indexed_document_names(collection)
        missing_files = [path for path in corpus_files if normalize_document(path.name) not in indexed_names]

    if not indexed_names:
        raise RuntimeError(
            "The ChromaDB collection is empty. Index the company documents first, or run:\n"
            "  python .\\evaluation\\evaluate_retrieval.py --split development --index-missing"
        )

    if missing_files:
        preview = ", ".join(path.name for path in missing_files[:5])
        suffix = "..." if len(missing_files) > 5 else ""
        print(
            f"WARNING: {len(missing_files)} of {len(corpus_files)} corpus documents are not indexed: "
            f"{preview}{suffix}"
        )

    return {
        "corpus_files": len(corpus_files),
        "indexed_corpus_files": len(expected_names.intersection(indexed_names)),
        "missing_corpus_files": len(missing_files),
        "indexed_document_names": indexed_names,
    }

def references_for(item: dict[str, Any]) -> list[Reference]:
    references: list[Reference] = []
    for raw in item.get("references") or []:
        references.append(
            Reference(
                document=str(raw.get("document", "")),
                page=str(raw.get("page", "")),
            )
        )
    return references

def dedupe_ranked_results(results: list[dict[str, Any]], level: str) -> list[dict[str, Any]]:
    seen: set[Any] = set()
    unique: list[dict[str, Any]] = []

    for result in results:
        document = normalize_document(result.get("documentName"))
        page = normalize_page(result.get("page"))
        key: Any = document if level == "document" else (document, page)
        if not document or key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return unique

def relevance_key(result: dict[str, Any], level: str) -> Any:
    document = normalize_document(result.get("documentName"))
    if level == "document":
        return document
    return document, normalize_page(result.get("page"))

def expected_keys(references: Iterable[Reference], level: str) -> set[Any]:
    if level == "document":
        return {reference.document_key for reference in references}
    return {reference.page_key for reference in references}

def rank_of_first_relevant(ranked_results: list[dict[str, Any]], relevant: set[Any], level: str) -> int | None:
    for rank, result in enumerate(ranked_results, start=1):
        if relevance_key(result, level) in relevant:
            return rank
    return None

def metrics_at_k(
    ranked_results: list[dict[str, Any]],
    relevant: set[Any],
    k_values: list[int],
    level: str,
) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for k in k_values:
        top_k = ranked_results[:k]
        retrieved_relevant = {
            relevance_key(result, level)
            for result in top_k
            if relevance_key(result, level) in relevant
        }
        count = len(retrieved_relevant)
        metrics[f"hit@{k}"] = 1.0 if count > 0 else 0.0
        metrics[f"precision@{k}"] = count / k
        metrics[f"recall@{k}"] = count / len(relevant) if relevant else 0.0
    return metrics

def serialize_retrieved(results: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, result in enumerate(results[:limit], start=1):
        rows.append(
            {
                "rank": rank,
                "document": result.get("documentName"),
                "page": result.get("page"),
                "chunk_index": result.get("chunkIndex"),
                "score": result.get("score"),
                "semantic_score": result.get("semanticScore"),
                "keyword_score": result.get("keywordScore"),
                "base_score": result.get("baseScore"),
                "reranker_applied": result.get("rerankerApplied"),
                "reranker_rank": result.get("rerankerRank"),
                "reranker_raw_score": result.get("rerankerRawScore"),
                "reranker_score": result.get("rerankerScore"),
                "evidence_score": result.get("evidenceScore"),
                "evidence_supported": result.get("evidenceSupported"),
                "evidence_missing_concepts": result.get("evidenceMissingConcepts") or [],
                "evidence_hard_failures": result.get("evidenceHardFailures") or [],
            }
        )
    return rows

def evaluate_item(
    item: dict[str, Any],
    hybrid_search: Any,
    k_values: list[int],
    candidate_k: int,
    min_score: float,
    use_reranker: bool,
    verify_evidence: bool,
) -> dict[str, Any]:
    max_k = max(k_values)
    retrieval_limit = max_k 
    
    # 1. Gunakan query_variants jika tersedia untuk menguji cross-language
    variants = item.get("query_variants")
    if not variants or not isinstance(variants, list):
        variants = [item["question"]]

    best_eval = None

    for variant in variants:
        started = time.perf_counter()
        results = hybrid_search(
            variant,
            top_k=retrieval_limit,
            candidate_k=max(candidate_k, retrieval_limit),
            min_score=min_score,
            use_reranker=use_reranker,
            verify_evidence=verify_evidence,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000

        top_result = results[0] if results else {}
        top_score = float(top_result.get("score", 0.0)) if results else 0.0
        
        base: dict[str, Any] = {
            "id": item["id"],
            "split": item.get("split"),
            "category": item.get("category"),
            "language": item.get("language"),
            "difficulty": item.get("difficulty"),
            "question_type": item.get("question_type"),
            "question": item["question"],
            "expected_answer": item.get("expected_answer", ""),
            "used_query": variant,  # 5. Rekam query yang aktual digunakan
            "answerable": bool(item.get("answerable")),
            "latency_ms": round(elapsed_ms, 3),
            "retrieved_chunk_count": len(results),
            "top_score": round(top_score, 6),
            "top_base_score": top_result.get("baseScore"),
            "top_reranker_score": top_result.get("rerankerScore"),
            "top_evidence_score": top_result.get("evidenceScore"),
            "top_evidence_supported": top_result.get("evidenceSupported"),
            "top_evidence_missing_concepts": top_result.get("evidenceMissingConcepts") or [],
            "top_evidence_hard_failures": top_result.get("evidenceHardFailures") or [],
            "top_answerability_score": top_result.get("answerabilityScore"),
            "top_answerability_reason": top_result.get("answerabilityReason"),
            "top_answerability_score_margin": top_result.get("answerabilityScoreMargin"),
            "top_answerability_supporting_candidates": top_result.get("answerabilitySupportingCandidates"),
            "retrieved": serialize_retrieved(results, retrieval_limit),
        }

        if not item.get("answerable"):
            # 3. False-positive berdasarkan confidence score, bukan kemunculan hasil
            base.update(
                {
                    "expected_documents": [],
                    "expected_pages": [],
                    "returned_no_result": len(results) == 0,
                    "retrieval_false_positive": len(results) > 0,
                    "document_mrr": 0.0,
                    "page_mrr": 0.0,
                }
            )
        else:
            references = references_for(item)
            document_relevant = expected_keys(references, "document")
            page_relevant = {
                reference.page_key
                for reference in references
                if str(reference.page or "").strip()
            }
            document_results = dedupe_ranked_results(results, "document")[:max_k]
            page_results = dedupe_ranked_results(results, "page")[:max_k]

            document_rank = rank_of_first_relevant(document_results, document_relevant, "document")
            page_rank = (
                rank_of_first_relevant(page_results, page_relevant, "page")
                if page_relevant else None
            )

            base.update(
                {
                    "expected_documents": sorted(document_relevant),
                    "expected_pages": [f"{document}#p{page}" for document, page in sorted(page_relevant)],
                    "first_relevant_document_rank": document_rank,
                    "first_relevant_page_rank": page_rank,
                    "document_mrr": 1.0 / document_rank if document_rank else 0.0,
                    "page_mrr": (1.0 / page_rank if page_rank else 0.0) if page_relevant else None,
                    "document_metrics": metrics_at_k(document_results, document_relevant, k_values, "document"),
                    "page_metrics": (
                        metrics_at_k(page_results, page_relevant, k_values, "page")
                        if page_relevant else {}
                    ),
                }
            )

        # Logika pemilihan hasil terbaik dari varian
        if best_eval is None:
            best_eval = base
        else:
            if item.get("answerable"):
                # Prefer page MRR when page labels exist, otherwise document MRR.
                base_metric = base.get("page_mrr")
                best_metric = best_eval.get("page_mrr")
                if base_metric is None or best_metric is None:
                    base_metric = base.get("document_mrr", 0.0)
                    best_metric = best_eval.get("document_mrr", 0.0)
                if base_metric > best_metric:
                    best_eval = base
                elif base_metric == best_metric and base["top_score"] > best_eval["top_score"]:
                    best_eval = base
            else:
                # Untuk pertanyaan tak terjawab, skor terendah adalah yang terbaik (paling minim false-positive)
                if base["top_score"] < best_eval["top_score"]:
                    best_eval = base

    return best_eval

def mean(values: Iterable[float]) -> float:
    values_list = list(values)
    return statistics.fmean(values_list) if values_list else 0.0

def summarize_answerable(rows: list[dict[str, Any]], k_values: list[int]) -> dict[str, Any]:
    if not rows:
        return {"count": 0}

    document: dict[str, float] = {"mrr": mean(row["document_mrr"] for row in rows)}
    page_rows = [row for row in rows if row.get("page_mrr") is not None]
    page: dict[str, float] = {"mrr": mean(row["page_mrr"] for row in page_rows)} if page_rows else {}

    for k in k_values:
        for metric in ("hit", "precision", "recall"):
            key = f"{metric}@{k}"
            document[key] = mean(row["document_metrics"][key] for row in rows)
            if page_rows:
                page[key] = mean(row["page_metrics"][key] for row in page_rows)

    return {
        "count": len(rows),
        "document_level": {key: round(value, 6) for key, value in document.items()},
        "page_level": {key: round(value, 6) for key, value in page.items()},
        "page_level_available": bool(page_rows),
        "latency_ms": {
            "mean": round(mean(row["latency_ms"] for row in rows), 3),
            "median": round(statistics.median(row["latency_ms"] for row in rows), 3),
            "min": round(min(row["latency_ms"] for row in rows), 3),
            "max": round(max(row["latency_ms"] for row in rows), 3),
        },
    }

def summarize_unanswerable(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "count": 0,
            "true_rejection_count": 0,
            "false_positive_count": 0,
        }
    true_rejections = [row for row in rows if row["returned_no_result"]]
    false_positives = [row for row in rows if row["retrieval_false_positive"]]
    no_result_rate = len(true_rejections) / len(rows)
    return {
        "count": len(rows),
        "true_rejection_count": len(true_rejections),
        "false_positive_count": len(false_positives),
        "true_rejection_ids": [row["id"] for row in true_rejections],
        "false_positive_ids": [row["id"] for row in false_positives],
        "no_result_rate": round(no_result_rate, 6),
        "retrieval_false_positive_rate": round(len(false_positives) / len(rows), 6),
        "mean_top_score": round(mean(row["top_score"] for row in rows), 6),
    }

def grouped_summaries(rows: list[dict[str, Any]], k_values: list[int]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for field in ("split", "category", "language", "difficulty"):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            groups[str(row.get(field) or "unknown")].append(row)

        output[field] = {}
        for group_name, group_rows in sorted(groups.items()):
            answerable = [row for row in group_rows if row["answerable"]]
            unanswerable = [row for row in group_rows if not row["answerable"]]
            output[field][group_name] = {
                "total_count": len(group_rows),
                "answerable": summarize_answerable(answerable, k_values),
                "unanswerable": summarize_unanswerable(unanswerable),
            }
    return output

def build_summary(
    dataset: dict[str, Any],
    rows: list[dict[str, Any]],
    args: argparse.Namespace,
    index_status: dict[str, Any],
) -> dict[str, Any]:
    answerable = [row for row in rows if row["answerable"]]
    unanswerable = [row for row in rows if not row["answerable"]]

    return {
        "evaluation_name": "LapisAI Retrieval Quality Evaluation",
        "generated_at": utc_now_iso(),
        "dataset_name": dataset.get("dataset_name"),
        "dataset_version": dataset.get("version"),
        "dataset_source_format": dataset.get("source_format"),
        "primary_level": dataset.get("evaluation_level", "page"),
        "configuration": {
            "split": args.split,
            "k_values": args.k_values,
            "candidate_k": args.candidate_k,
            "min_score": args.min_score,
            "reranker_enabled": not args.no_reranker,
            "reranker_model": RERANKER_MODEL,
            "reranker_candidates_per_retriever": RERANKER_CANDIDATES,
            "reranker_weight": RERANKER_WEIGHT,
            "evidence_verification_enabled": not args.no_evidence_verification,
            "answerability_gate_enabled": ENABLE_ANSWERABILITY_GATE,
            "answerability_min_top_score": ANSWERABILITY_MIN_TOP_SCORE,
            "answerability_min_evidence_score": ANSWERABILITY_MIN_EVIDENCE_SCORE,
            "answerability_min_score_margin": ANSWERABILITY_MIN_SCORE_MARGIN,
            "answerability_require_supported_evidence": ANSWERABILITY_REQUIRE_SUPPORTED_EVIDENCE,
            "ground_truth": str(args.ground_truth),
            "chroma_path": str(DEFAULT_CHROMA_PATH),
            "collection": COLLECTION_NAME,
            "embedding_model": EMBEDDING_MODEL,
        },
        "index_status": {
            key: value
            for key, value in index_status.items()
            if key != "indexed_document_names"
        },
        "question_counts": {
            "total": len(rows),
            "answerable": len(answerable),
            "unanswerable": len(unanswerable),
        },
        "overall": {
            "answerable": summarize_answerable(answerable, args.k_values),
            "unanswerable": summarize_unanswerable(unanswerable),
        },
        "by_group": grouped_summaries(rows, args.k_values),
        "metric_definitions": {
            "primary_level": dataset.get("evaluation_level", "page"),
            "hit@k": "1 when at least one expected page/document appears in the first k unique retrieved units; otherwise 0.",
            "precision@k": "Number of expected unique pages/documents retrieved in the first k divided by k.",
            "recall@k": "Number of expected unique pages/documents retrieved in the first k divided by all expected references.",
            "mrr": "Mean reciprocal rank of the first expected page/document.",
            "unanswerable_no_result_rate": "Share of unanswerable questions rejected by retrieval filtering. False-positive is measured using the retrieval confidence threshold.",
        },
    }

def flatten_for_csv(row: dict[str, Any], k_values: list[int]) -> dict[str, Any]:
    retrieved = row.get("retrieved") or []
    flattened: dict[str, Any] = {
        "id": row["id"],
        "split": row.get("split"),
        "category": row.get("category"),
        "language": row.get("language"),
        "difficulty": row.get("difficulty"),
        "question_type": row.get("question_type"),
        "question": row["question"],
        "expected_answer": row.get("expected_answer"),
        "used_query": row.get("used_query"),  # 5. Output di CSV
        "answerable": row["answerable"],
        "expected_documents": " | ".join(row.get("expected_documents") or []),
        "expected_pages": " | ".join(row.get("expected_pages") or []),
        "first_relevant_document_rank": row.get("first_relevant_document_rank"),
        "first_relevant_page_rank": row.get("first_relevant_page_rank"),
        "document_mrr": row.get("document_mrr"),
        "page_mrr": row.get("page_mrr"),
        "returned_no_result": row.get("returned_no_result"),
        "retrieval_false_positive": row.get("retrieval_false_positive"),
        "latency_ms": row["latency_ms"],
        "retrieved_chunk_count": row["retrieved_chunk_count"],
        "top_score": row["top_score"],
        "top_base_score": row.get("top_base_score"),
        "top_reranker_score": row.get("top_reranker_score"),
        "top_evidence_score": row.get("top_evidence_score"),
        "top_evidence_supported": row.get("top_evidence_supported"),
        "top_evidence_missing_concepts": " | ".join(row.get("top_evidence_missing_concepts") or []),
        "top_evidence_hard_failures": " | ".join(row.get("top_evidence_hard_failures") or []),
        "top_answerability_score": row.get("top_answerability_score"),
        "top_answerability_reason": row.get("top_answerability_reason"),
        "top_answerability_score_margin": row.get("top_answerability_score_margin"),
        "top_answerability_supporting_candidates": row.get("top_answerability_supporting_candidates"),
        "retrieved_documents": " | ".join(
            f"{item.get('rank')}:{item.get('document')}#p{item.get('page')}[{item.get('score')}]"
            for item in retrieved
        ),
    }

    for level in ("document", "page"):
        metrics = row.get(f"{level}_metrics") or {}
        for k in k_values:
            for metric in ("hit", "precision", "recall"):
                flattened[f"{level}_{metric}@{k}"] = metrics.get(f"{metric}@{k}")
    return flattened

def write_csv(path: Path, rows: list[dict[str, Any]], k_values: list[int]) -> None:
    flattened = [flatten_for_csv(row, k_values) for row in rows]
    fieldnames: list[str] = []
    for row in flattened:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flattened)

def percent(value: Any) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "-"

def _metric_table_lines(title: str, metrics: dict[str, Any], k_values: list[int]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| MRR | {float(metrics.get('mrr', 0)):.4f} |",
    ]
    for k in k_values:
        lines.extend(
            [
                f"| Hit Rate@{k} | {percent(metrics.get(f'hit@{k}', 0))} |",
                f"| Precision@{k} | {percent(metrics.get(f'precision@{k}', 0))} |",
                f"| Recall@{k} | {percent(metrics.get(f'recall@{k}', 0))} |",
            ]
        )
    lines.append("")
    return lines


def write_markdown_report(path: Path, summary: dict[str, Any]) -> None:
    config = summary["configuration"]
    answerable = summary["overall"]["answerable"]
    unanswerable = summary["overall"]["unanswerable"]
    page = answerable.get("page_level") or {}
    document = answerable.get("document_level") or {}
    k_values = config["k_values"]
    primary_level = summary.get("primary_level", "page")

    lines = [
        "# LapisAI Retrieval Evaluation Report",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "## Dataset",
        "",
        f"- Name: `{summary.get('dataset_name') or '-'}`",
        f"- Version: `{summary.get('dataset_version') or '-'}`",
        f"- Source format: `{summary.get('dataset_source_format') or '-'}`",
        f"- Ground truth: `{config['ground_truth']}`",
        f"- Questions: `{summary['question_counts']['total']}`",
        f"- Answerable: `{summary['question_counts']['answerable']}`",
        f"- Unanswerable: `{summary['question_counts']['unanswerable']}`",
        f"- Indexed corpus files: `{summary['index_status']['indexed_corpus_files']}/{summary['index_status']['corpus_files']}`",
        "",
        "## Configuration",
        "",
        f"- Split: `{config['split']}`",
        f"- k: `{', '.join(map(str, k_values))}`",
        f"- candidate_k per retriever: `{config['candidate_k']}`",
        f"- minimum final score: `{config['min_score']}`",
        f"- reranker enabled: `{config.get('reranker_enabled', True)}`",
        f"- reranker model: `{config.get('reranker_model', '-')}`",
        f"- reranker weight: `{config.get('reranker_weight', '-')}`",
        f"- evidence verification enabled: `{config.get('evidence_verification_enabled', True)}`",
        f"- answerability gate enabled: `{config.get('answerability_gate_enabled', True)}`",
        "",
    ]

    if primary_level == "document":
        lines.extend(_metric_table_lines("Primary results: document-level retrieval", document, k_values))
        if page:
            lines.extend(_metric_table_lines("Supporting results: page-level retrieval", page, k_values))
        else:
            lines.extend(
                [
                    "## Page-level retrieval",
                    "",
                    "Not evaluated because `ground_truth_qa.csv` provides `source_document` but no source-page labels.",
                    "",
                ]
            )
    else:
        lines.extend(_metric_table_lines("Primary results: page-level retrieval", page, k_values))
        lines.extend(_metric_table_lines("Supporting results: document-level retrieval", document, k_values))

    language_groups = summary.get("by_group", {}).get("language", {})
    available_languages = [
        (lang, data.get("answerable", {}))
        for lang, data in sorted(language_groups.items())
        if data.get("answerable", {}).get("count", 0) > 0
    ]
    if available_languages:
        lines.extend(["## Language performance", ""])
        for lang, data in available_languages:
            level_metrics = data.get(f"{primary_level}_level", {})
            lines.append(
                f"- `{lang}`: questions `{data.get('count', 0)}`, "
                f"{primary_level} MRR `{float(level_metrics.get('mrr', 0)):.4f}`"
            )
        lines.append("")

    if unanswerable.get("count", 0) > 0:
        lines.extend(
            [
                "## Unanswerable-question retrieval behaviour",
                "",
                f"- Questions: `{unanswerable.get('count', 0)}`",
                f"- Correctly rejected: `{unanswerable.get('true_rejection_count', 0)}`",
                f"- False positives: `{unanswerable.get('false_positive_count', 0)}`",
                f"- No-result rate: `{percent(unanswerable.get('no_result_rate', 0))}`",
                f"- Retrieval false-positive rate: `{percent(unanswerable.get('retrieval_false_positive_rate', 0))}`",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Unanswerable-question evaluation",
                "",
                "Not evaluated because the official CSV contains only answerable questions.",
                "",
            ]
        )

    lines.extend(
        [
            "## Interpretation note",
            "",
            "The official CSV labels one expected source document for each question. "
            "Therefore document-level MRR, Hit@k, Precision@k, and Recall@k are the valid primary retrieval metrics. "
            "Page-level and unanswerable metrics must not be inferred from missing labels.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def print_summary(summary: dict[str, Any]) -> None:
    answerable = summary["overall"]["answerable"]
    unanswerable = summary["overall"]["unanswerable"]
    page = answerable.get("page_level") or {}
    document = answerable.get("document_level") or {}
    k_values = summary["configuration"]["k_values"]
    primary_level = summary.get("primary_level", "page")
    primary = document if primary_level == "document" else page

    print("\nLapisAI retrieval evaluation")
    print("=" * 40)
    print(f"Dataset         : {summary.get('dataset_name') or '-'}")
    print(f"Questions       : {summary['question_counts']['total']}")
    print(f"Answerable      : {summary['question_counts']['answerable']}")
    if summary['question_counts']['unanswerable']:
        print(f"Unanswerable    : {summary['question_counts']['unanswerable']}")
    else:
        print("Unanswerable    : Not included")
    print(
        "Indexed corpus  : "
        f"{summary['index_status']['indexed_corpus_files']}/{summary['index_status']['corpus_files']}"
    )

    print(f"\n{primary_level.capitalize()}-level metrics (primary)")
    print(f"MRR             : {primary.get('mrr', 0):.4f}")
    for k in k_values:
        print(
            f"@{k:<2} Hit={percent(primary.get(f'hit@{k}', 0)):>8}  "
            f"Precision={percent(primary.get(f'precision@{k}', 0)):>8}  "
            f"Recall={percent(primary.get(f'recall@{k}', 0)):>8}"
        )

    if primary_level == "page":
        secondary_name, secondary = "Document", document
    else:
        secondary_name, secondary = "Page", page

    if secondary:
        print(f"\n{secondary_name}-level metrics (supporting)")
        print(f"MRR             : {secondary.get('mrr', 0):.4f}")
        for k in k_values:
            print(
                f"@{k:<2} Hit={percent(secondary.get(f'hit@{k}', 0)):>8}  "
                f"Precision={percent(secondary.get(f'precision@{k}', 0)):>8}  "
                f"Recall={percent(secondary.get(f'recall@{k}', 0)):>8}"
            )
    elif primary_level == "document":
        print("\nPage-level metrics")
        print("Not evaluated: the CSV has no page labels.")

    language_groups = summary.get("by_group", {}).get("language", {})
    available_languages = [
        (lang, data.get("answerable", {}))
        for lang, data in sorted(language_groups.items())
        if data.get("answerable", {}).get("count", 0) > 0
    ]
    if available_languages:
        print("\nLanguage Performance")
        print("-" * 20)
        for lang, data in available_languages:
            level_metrics = data.get(f"{primary_level}_level", {})
            print(f"{lang.capitalize()} Query")
            print(f"MRR : {float(level_metrics.get('mrr', 0)):.4f}\n")

    if unanswerable.get("count"):
        print("\nUnanswerable retrieval behaviour")
        print(f"No-result rate  : {percent(unanswerable.get('no_result_rate', 0))}")
        print(f"False-positive  : {percent(unanswerable.get('retrieval_false_positive_rate', 0))}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate LapisAI hybrid retrieval against the verified ground-truth Q&A dataset."
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=DEFAULT_GROUND_TRUTH,
        help="Path to official ground_truth_qa.csv or legacy ground_truth JSON.",
    )
    parser.add_argument(
        "--split",
        choices=("development", "test", "all"),
        default="all",
        help="Dataset split to evaluate. The official CSV uses split=all.",
    )
    parser.add_argument(
        "--k",
        dest="k_values",
        type=parse_k_values,
        default=parse_k_values("1,3,5"),
        help="Comma-separated k values, for example 1,3,5.",
    )
    parser.add_argument(
        "--candidate-k",
        type=int,
        default=20,
        help="Candidate count contributed independently by semantic and BM25 retrieval.",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=DEFAULT_MIN_SCORE,
        help="Minimum final retrieval score. Default follows MIN_RESULT_SCORE.",
    )
    parser.add_argument(
        "--no-reranker",
        action="store_true",
        help="Disable the cross-encoder reranker for an ablation run.",
    )
    parser.add_argument(
        "--no-evidence-verification",
        action="store_true",
        help="Disable evidence filtering for an ablation run.",
    )
    parser.add_argument(
        "--index-missing",
        action="store_true",
        help="Index corpus documents missing from ChromaDB before evaluation.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Evaluate only the first N selected questions for a quick smoke test.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON, CSV, and Markdown results.",
    )
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.candidate_k <= 0:
        parser.error("--candidate-k must be greater than zero.")
    if not 0.0 <= args.min_score <= 1.0:
        parser.error("--min-score must be between 0 and 1.")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than zero.")

    args.ground_truth = args.ground_truth.resolve()
    args.output_dir = args.output_dir.resolve()

    try:
        dataset, all_items = load_ground_truth(args.ground_truth)
        items = filter_items(all_items, args.split, args.limit)
        get_collection, hybrid_search, ingest = import_backend_modules()
        collection = get_collection()
        index_status = ensure_index(dataset, collection, ingest, args.index_missing)

        print(
            f"Evaluating {len(items)} question(s), split={args.split}, "
            f"k={args.k_values}, candidate_k={args.candidate_k}, "
            f"reranker={not args.no_reranker}, evidence={not args.no_evidence_verification}"
        )

        rows: list[dict[str, Any]] = []
        for number, item in enumerate(items, start=1):
            print(f"  [{number:02d}/{len(items):02d}] {item['id']}: {item['question'][:70]}")
            rows.append(
                evaluate_item(
                    item=item,
                    hybrid_search=hybrid_search,
                    k_values=args.k_values,
                    candidate_k=args.candidate_k,
                    min_score=args.min_score,
                    use_reranker=not args.no_reranker,
                    verify_evidence=not args.no_evidence_verification,
                )
            )

        summary = build_summary(dataset, rows, args, index_status)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"{args.split}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        summary_path = args.output_dir / f"retrieval_summary_{suffix}.json"
        details_path = args.output_dir / f"retrieval_results_{suffix}.csv"
        report_path = args.output_dir / f"retrieval_report_{suffix}.md"
        latest_summary = args.output_dir / "retrieval_summary_latest.json"
        latest_details = args.output_dir / "retrieval_results_latest.csv"
        latest_report = args.output_dir / "retrieval_report_latest.md"

        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        write_csv(details_path, rows, args.k_values)
        write_markdown_report(report_path, summary)
        latest_summary.write_text(summary_path.read_text(encoding="utf-8"), encoding="utf-8")
        latest_details.write_bytes(details_path.read_bytes())
        latest_report.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")

        print_summary(summary)
        print("\nSaved:")
        print(f"  {summary_path}")
        print(f"  {details_path}")
        print(f"  {report_path}")
        return 0
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nEvaluation cancelled by user.", file=sys.stderr)
        return 130

if __name__ == "__main__":
    raise SystemExit(main())