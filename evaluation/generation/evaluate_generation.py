"""Evaluate one model on the bilingual Project-1 RAG question set.

The evaluator supports answerable and unanswerable questions, reports metrics
for English, Indonesian, and the combined dataset, and can optionally use one
fixed LLM judge for faithfulness and answer relevance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import statistics
import subprocess
import requests
from dotenv import load_dotenv
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Iterable

try:
    from .dataset_utils import dataset_summary, load_ground_truth_files
except ImportError:  # Direct script execution.
    from dataset_utils import dataset_summary, load_ground_truth_files

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
EVALUATION_DIR = PROJECT_ROOT / "evaluation"
DEFAULT_DATASETS = [
    EVALUATION_DIR / "datasets" / "qna_english_user.csv",
    EVALUATION_DIR / "datasets" / "qna_indonesia_user.csv",
]
LLM_BASE_URL = os.getenv("EVAL_LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("EVAL_LLM_API_KEY", "ollama")
LLM_MODEL = os.getenv("EVAL_LLM_MODEL", "qwen3-custom:latest")

REFUSAL_PREFIXES = (
    # Canonical backend refusals and direct first-person refusals.
    "informasi tersebut tidak ditemukan",
    "informasi tidak ditemukan",
    "tidak ditemukan dengan bukti",
    "belum ditemukan di dokumen",
    "belum ketemu di dokumen",
    "tidak ada informasi yang cukup",
    "konteks tidak cukup",
    "saya tidak menemukan",
    "saya belum menemukan",
    "saya tidak dapat menemukan",
    "the requested information was not found",
    "the information was not found",
    "i cannot answer",
    "i can't answer",
    "i could not find",
    "i couldn't find",
    "i cannot find",
    "could not find the requested information",
    "no sufficient information was found",
    "no reliable source",
    "insufficient context",
    "insufficient evidence",
)

DOCUMENT_REFUSAL_PREFIXES = (
    "dokumen yang diindeks tidak",
    "dokumen yang telah diindeks tidak",
    "dokumen tidak menyebutkan",
    "dokumen tidak menentukan",
    "the indexed documents do not",
    "the documents do not provide",
    "the documents do not specify",
    "the documents do not mention",
)

UNAVAILABLE_OPENING_PATTERN = re.compile(
    r"^(?:"
    r"(?:the\s+)?[a-z0-9][^.]{0,180}\s+(?:is|are)\s+not\s+"
    r"(?:available|stated|specified|provided|found)\s+in\s+(?:the\s+)?indexed\s+documents"
    r"|informasi\s+mengenai\s+[^.]{0,180}\s+tidak\s+tersedia"
    r"|laporan\s+[^.]{0,180}\s+tidak\s+tersedia"
    r")",
    flags=re.I,
)

CONTRAST_MARKERS = (
    " but ",
    " however ",
    " although ",
    " yet ",
    " namun ",
    " tetapi ",
    " meskipun ",
    " akan tetapi ",
)


def normalize_document(name: Any) -> str:
    value = str(name or "").replace("\\", "/").split("/")[-1].lower().strip()
    value = re.sub(r"\.(pdf|txt|docx|doc)$", "", value)
    return re.sub(r"[\s-]+", "_", value)


def normalize_page(page: Any) -> str:
    value = str(page or "").lower().strip()
    match = re.search(r"\d+", value)
    return match.group(0) if match else ""


def normalize_source(item: Any) -> tuple[str, str]:
    if not isinstance(item, dict):
        return "", ""
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    document = (
        item.get("document")
        or item.get("documentName")
        or item.get("document_name")
        or item.get("file")
        or item.get("file_name")
        or item.get("source")
        or metadata.get("filename")
        or metadata.get("source")
        or ""
    )
    page = (
        item.get("page")
        or item.get("page_number")
        or item.get("page_no")
        or metadata.get("page")
        or ""
    )
    return normalize_document(document), normalize_page(page)


def source_set(items: Iterable[Any]) -> set[tuple[str, str]]:
    output: set[tuple[str, str]] = set()
    for item in items or []:
        source = normalize_source(item)
        if source[0]:
            output.add(source)
    return output


def _source_units(items: Iterable[Any], document_only: bool) -> set[Any]:
    sources = source_set(items)
    return {document for document, _ in sources} if document_only else sources


def _sources_are_interchangeable(items: Iterable[Any]) -> bool:
    references = [item for item in items or [] if isinstance(item, dict)]
    return bool(
        len(references) > 1
        and all(reference.get("acceptable_alternative") is True for reference in references)
    )


def source_metrics(
    retrieved_sources: list[Any],
    expected_sources: list[Any],
    citations: list[Any],
    *,
    answerable: bool,
) -> dict[str, float | None]:
    expected = source_set(expected_sources)
    retrieved = source_set(retrieved_sources)
    cited = source_set(citations)

    if not answerable:
        citation_precision = 1.0 if not cited else 0.0
        return {
            "context_precision": 1.0 if not retrieved else 0.0,
            "context_recall": None,
            "citation_precision": citation_precision,
            "citation_recall": None,
            "citation_f1": citation_precision,
            "citation_accuracy": citation_precision,
            "retrieval_no_result": 1.0 if not retrieved else 0.0,
        }

    document_only = bool(expected) and all(not page for _, page in expected)
    expected_units = _source_units(expected_sources, document_only)
    retrieved_units = _source_units(retrieved_sources, document_only)
    cited_units = _source_units(citations, document_only)
    interchangeable = _sources_are_interchangeable(expected_sources)
    if not expected_units:
        return {
            "context_precision": None,
            "context_recall": None,
            "citation_precision": None,
            "citation_recall": None,
            "citation_f1": None,
            "citation_accuracy": None,
            "retrieval_no_result": 1.0 if not retrieved_units else 0.0,
        }

    intersection = expected_units & retrieved_units
    cited_intersection = expected_units & cited_units
    citation_precision = len(cited_intersection) / max(len(cited_units), 1)
    citation_recall = (
        1.0 if cited_intersection else 0.0
    ) if interchangeable else len(cited_intersection) / len(expected_units)
    citation_f1 = (
        2 * citation_precision * citation_recall
        / (citation_precision + citation_recall)
        if citation_precision + citation_recall > 0
        else 0.0
    )
    return {
        "context_precision": len(intersection) / max(len(retrieved_units), 1),
        "context_recall": (
            1.0 if intersection else 0.0
        ) if interchangeable else len(intersection) / len(expected_units),
        "citation_precision": citation_precision,
        "citation_recall": citation_recall,
        "citation_f1": citation_f1,
        # Compatibility alias. New reports label this as F1, not "accuracy".
        "citation_accuracy": citation_f1,
        "retrieval_no_result": 1.0 if not retrieved_units else 0.0,
    }


def ranked_retrieval_metrics(
    ranked_candidates: list[Any],
    expected_sources: list[Any],
    *,
    answerable: bool,
    top_k: int,
) -> dict[str, float | None]:
    """Compute document-level Precision@K, Recall@K, Hit@K, and MRR."""
    if not answerable:
        return {
            "precision_at_k": None,
            "recall_at_k": None,
            "hit_at_k": None,
            "mrr": None,
            "top1_accuracy": None,
            "ndcg_at_k": None,
            "first_relevant_rank": None,
        }

    expected_documents = {document for document, _ in source_set(expected_sources)}
    interchangeable = _sources_are_interchangeable(expected_sources)
    if not expected_documents:
        return {
            "precision_at_k": None,
            "recall_at_k": None,
            "hit_at_k": None,
            "mrr": None,
            "top1_accuracy": None,
            "ndcg_at_k": None,
            "first_relevant_rank": None,
        }

    ranked_documents: list[str] = []
    seen: set[str] = set()
    for candidate in ranked_candidates or []:
        if not isinstance(candidate, dict):
            continue
        document = normalize_document(
            candidate.get("document")
            or candidate.get("documentName")
            or candidate.get("document_name")
        )
        if document and document not in seen:
            seen.add(document)
            ranked_documents.append(document)

    k = max(1, int(top_k or 5))
    top_documents = ranked_documents[:k]
    relevant_in_top_k = expected_documents.intersection(top_documents)
    first_rank = next(
        (index for index, document in enumerate(ranked_documents, start=1) if document in expected_documents),
        None,
    )
    if interchangeable:
        dcg = (
            1.0 / math.log2(first_rank + 1)
            if first_rank is not None and first_rank <= k
            else 0.0
        )
    else:
        dcg = sum(
            1.0 / math.log2(rank + 1)
            for rank, document in enumerate(top_documents, start=1)
            if document in expected_documents
        )
    ideal_relevant = 1 if interchangeable else min(len(expected_documents), k)
    ideal_dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank in range(1, ideal_relevant + 1)
    )
    return {
        "precision_at_k": len(relevant_in_top_k) / k,
        "recall_at_k": (
            1.0 if relevant_in_top_k else 0.0
        ) if interchangeable else len(relevant_in_top_k) / len(expected_documents),
        "hit_at_k": 1.0 if relevant_in_top_k else 0.0,
        "mrr": (1.0 / first_rank) if first_rank else 0.0,
        "top1_accuracy": (
            1.0
            if top_documents and top_documents[0] in expected_documents
            else 0.0
        ),
        "ndcg_at_k": dcg / ideal_dcg if ideal_dcg else None,
        "first_relevant_rank": float(first_rank) if first_rank else None,
    }


def metadata_metrics(
    retrieved_sources: list[Any],
    expected_sources: list[Any],
    citations: list[Any],
) -> tuple[float, float, float]:
    """Legacy 1-to-5 wrapper around the canonical 0-to-1 source metrics."""
    metrics = source_metrics(
        retrieved_sources,
        expected_sources,
        citations,
        answerable=bool(expected_sources),
    )

    def scaled(name: str) -> float:
        value = metrics.get(name)
        return 0.0 if value is None else round(float(value) * 5.0, 4)

    return (
        scaled("context_precision"),
        scaled("context_recall"),
        scaled("citation_accuracy"),
    )


def normalize_answer(text: str) -> str:
    value = str(text or "").casefold()
    number_words = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "satu": "1", "dua": "2", "tiga": "3", "empat": "4", "lima": "5",
        "enam": "6", "tujuh": "7", "delapan": "8", "sembilan": "9", "sepuluh": "10",
    }
    for word, digit in number_words.items():
        value = re.sub(rf"\b{word}\b", digit, value)
    value = value.replace("upper case", "uppercase").replace("lower case", "lowercase")
    # Canonicalize equivalent negative phrases so keyword scoring is fair.
    value = __import__("re").sub(r"\bnone\s+resulting\s+in\b", "no", value)
    value = __import__("re").sub(r"\b(?:did|does)\s+not\s+result\s+in\b", "no", value)
    value = value.replace("wib", " wib ")
    value = re.sub(r"(?<=\d)[.,:](?=\d)", "", value)
    value = re.sub(r"[^a-z0-9à-ÿ%]+", " ", value)
    return " ".join(value.split())


def answer_tokens(text: str) -> list[str]:
    return normalize_answer(text).split()


def exact_match(expected: str, generated: str) -> float:
    return 1.0 if normalize_answer(expected) == normalize_answer(generated) else 0.0


def token_f1(expected: str, generated: str) -> float:
    expected_tokens = answer_tokens(expected)
    generated_tokens = answer_tokens(generated)
    if not expected_tokens or not generated_tokens:
        return 0.0
    common = Counter(expected_tokens) & Counter(generated_tokens)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(generated_tokens)
    recall = overlap / len(expected_tokens)
    return 2 * precision * recall / (precision + recall)


def _keyword_coverage_in_text(keywords: list[str], text: str) -> float | None:
    if not keywords:
        return None
    normalized_text = normalize_answer(text)
    text_tokens = set(normalized_text.split())
    hits = 0
    for keyword in keywords:
        normalized = normalize_answer(keyword)
        keyword_tokens = set(normalized.split())
        if normalized and (
            normalized in normalized_text
            or (keyword_tokens and keyword_tokens.issubset(text_tokens))
        ):
            hits += 1
    return hits / len(keywords)


def keyword_coverage(keywords: list[str], question: str, generated: str) -> float | None:
    """Measure annotated concepts in the generated answer only.

    ``question`` remains in the public signature for backward compatibility,
    but it is deliberately excluded. Counting prompt words as answer content
    inflates correctness and can hide a missing answer fact.
    """
    del question
    return _keyword_coverage_in_text(keywords, generated)


def question_keyword_coverage(keywords: list[str], question: str) -> float | None:
    """Diagnostic only: quantify how much of the annotation leaks from the prompt."""
    return _keyword_coverage_in_text(keywords, question)


def question_answer_keyword_coverage(
    keywords: list[str],
    question: str,
    generated: str,
) -> float | None:
    """Compatibility diagnostic for historical question-plus-answer scoring."""
    return _keyword_coverage_in_text(keywords, f"{question} {generated}")


def detect_abstention(answer: str) -> bool:
    """Detect a direct refusal without treating a factual caveat as abstention."""
    text = re.sub(r"\s+", " ", str(answer or "")).strip().casefold()
    if not text:
        return False
    if re.search(r"(?:^|\s)confidence\s*:\s*0\s*%(?:\s|$)", text):
        return True
    if text.startswith(REFUSAL_PREFIXES):
        return True
    if UNAVAILABLE_OPENING_PATTERN.search(text):
        return True

    # Legacy answers sometimes use a document-scoped refusal. Restrict this to
    # the opening statement and ignore "not specified, but ..." caveats that
    # continue with a supported answer.
    first_statement = re.split(r"(?<=[.!?])\s+|\n+", text, maxsplit=1)[0]
    if first_statement.startswith(DOCUMENT_REFUSAL_PREFIXES):
        return not any(marker in f" {text[:320]} " for marker in CONTRAST_MARKERS)
    return False


def clamp_score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return max(1.0, min(score, 5.0))


def parse_json_object(text: str) -> dict[str, Any]:
    clean = re.sub(r"```(?:json)?|```", "", str(text or ""), flags=re.I).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def llm_judge(
    *,
    question: str,
    expected_answer: str,
    context: str,
    answer: str,
    answerable: bool,
) -> dict[str, Any]:
    task_rule = (
        "The question is ANSWERABLE. The response should answer correctly using only the context."
        if answerable
        else "The question is UNANSWERABLE from the indexed documents. A safe refusal is correct; inventing a specific fact is hallucination."
    )
    prompt = f"""
You are one fixed, independent evaluator for a bilingual Retrieval-Augmented Generation system.
Apply the same rubric regardless of which model produced the answer.

TASK STATUS:
{task_rule}

QUESTION:
{question}

EXPECTED ANSWER / EXPECTED BEHAVIOR:
{expected_answer}

RETRIEVED CONTEXT:
{context or '[EMPTY CONTEXT]'}

SYSTEM ANSWER:
{answer}

Score:
1. faithfulness (1-5): factual claims are supported by retrieved context. For an unanswerable item, a clean refusal with no invented fact scores 5.
2. answer_relevance (1-5): directly and correctly satisfies the expected answer or expected refusal behavior.
3. is_hallucination: true only when the response asserts a specific unsupported fact.

Return JSON only:
{{
  "faithfulness": 1,
  "answer_relevance": 1,
  "is_hallucination": false,
  "reason": "maximum 25 words"
}}
"""

    try:
        endpoint = LLM_BASE_URL.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        }
        request = {
            "model": LLM_MODEL,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": "Return one valid JSON object only."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        response = requests.post(endpoint, headers=headers, json=request, timeout=120)
        if response.status_code >= 400:
            request.pop("response_format", None)
            response = requests.post(endpoint, headers=headers, json=request, timeout=120)
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"].get("content") or ""
        result = parse_json_object(content)
        raw_hallucination = result.get("is_hallucination", False)
        if isinstance(raw_hallucination, str):
            is_hallucination = raw_hallucination.strip().casefold() in {"true", "1", "yes"}
        else:
            is_hallucination = bool(raw_hallucination)
        return {
            "faithfulness": clamp_score(result.get("faithfulness")),
            "answer_relevance": clamp_score(result.get("answer_relevance")),
            "is_hallucination": is_hallucination,
            "reason": str(result.get("reason") or "")[:240],
            "judge_error": "",
        }
    except Exception as error:
        print(f"[ERROR JUDGE] {error}")
        return {
            "faithfulness": None,
            "answer_relevance": None,
            "is_hallucination": None,
            "reason": "",
            "judge_error": str(error)[:240],
        }


def mean(values: Iterable[float | None]) -> float | None:
    valid = [float(value) for value in values if value is not None]
    return round(sum(valid) / len(valid), 4) if valid else None


def percentile(values: Iterable[float | None], percentile_value: float) -> float | None:
    valid = sorted(float(value) for value in values if value is not None)
    if not valid:
        return None
    if len(valid) == 1:
        return round(valid[0], 2)
    position = (len(valid) - 1) * percentile_value
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        result = valid[lower]
    else:
        fraction = position - lower
        result = valid[lower] + (valid[upper] - valid[lower]) * fraction
    return round(result, 2)


def wilson_interval_95(values: Iterable[float | int | None]) -> dict[str, Any]:
    """Return a Wilson 95% interval for a binary rate."""
    valid = [float(value) for value in values if value is not None]
    if not valid:
        return {"estimate": None, "lower": None, "upper": None, "n": 0}
    if any(value not in {0.0, 1.0} for value in valid):
        raise ValueError("Wilson interval requires binary 0/1 observations")
    n = len(valid)
    estimate = sum(valid) / n
    z = 1.959963984540054
    denominator = 1 + (z * z / n)
    center = (estimate + z * z / (2 * n)) / denominator
    margin = (
        z
        * math.sqrt(
            estimate * (1 - estimate) / n + z * z / (4 * n * n)
        )
        / denominator
    )
    return {
        "estimate": round(estimate, 4),
        "lower": round(max(0.0, center - margin), 4),
        "upper": round(min(1.0, center + margin), 4),
        "n": n,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _dependency_versions(requirement_files: list[Path]) -> dict[str, str]:
    names: set[str] = set()
    for path in requirement_files:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or line.startswith("-"):
                continue
            match = re.match(r"([A-Za-z0-9_.-]+)", line)
            if match:
                names.add(match.group(1))
    output: dict[str, str] = {}
    for name in sorted(names, key=str.casefold):
        try:
            output[name] = version(name)
        except PackageNotFoundError:
            output[name] = "not-installed"
    return output


def reproducibility_manifest(
    *,
    datasets: list[Path],
    input_path: Path,
    answers: list[dict[str, Any]],
    model_name: str,
    judge_model: str | None,
) -> dict[str, Any]:
    """Capture immutable inputs and runtime metadata without recording secrets."""
    requirement_files = [
        PROJECT_ROOT / "backend" / "requirements.txt",
        PROJECT_ROOT / "backend" / "requirements-dev.txt",
    ]
    files = [
        *datasets,
        input_path,
        *requirement_files,
        Path(__file__).resolve(),
    ]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "dependency_versions": _dependency_versions(requirement_files),
        "files": [
            {
                "path": _manifest_path(path),
                "sha256": _sha256_file(path.resolve()),
                "bytes": path.resolve().stat().st_size,
            }
            for path in files
        ],
        "model_name": model_name,
        "model_reference_mutable": model_name.casefold().endswith(":latest"),
        "judge_model": judge_model,
        "judge_independent": bool(
            judge_model
            and judge_model.strip().casefold() != model_name.strip().casefold()
        ),
        "backend_build_versions": sorted({
            str(item.get("backend_build_version") or "")
            for item in answers
            if item.get("backend_build_version")
        }),
        "retrieval_snapshot_builds": sorted({
            str(item.get("retrieval_snapshot_build") or "")
            for item in answers
            if item.get("retrieval_snapshot_build")
        }),
        "evaluation_context_modes": sorted({
            str(item.get("evaluation_context_mode") or "")
            for item in answers
            if item.get("evaluation_context_mode")
        }),
        "retrieval_top_k": sorted({
            int(item.get("retrieval_top_k") or 5) for item in answers
        }),
    }


def bilingual_pairing_diagnostics(
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Report whether EN-vs-ID scores measure the same underlying questions."""
    by_language: dict[str, dict[str, dict[str, Any]]] = {
        "EN": {},
        "ID": {},
    }
    for item in items:
        language = str(item.get("language") or "").upper()
        if language not in by_language:
            continue
        qid = str(item.get("id") or "")
        pair_key = qid.split("-", 1)[-1]
        by_language[language][pair_key] = item

    paired_keys = sorted(
        set(by_language["EN"]).intersection(by_language["ID"])
    )
    same_source_pairs = 0
    for key in paired_keys:
        english_sources = {
            document
            for document, _ in source_set(
                by_language["EN"][key].get("references") or []
            )
        }
        indonesian_sources = {
            document
            for document, _ in source_set(
                by_language["ID"][key].get("references") or []
            )
        }
        if english_sources and english_sources == indonesian_sources:
            same_source_pairs += 1

    paired_count = len(paired_keys)
    comparable = bool(paired_count and same_source_pairs == paired_count)
    return {
        "status": (
            "paired_equivalent_source_targets"
            if comparable
            else "descriptive_only_unpaired_targets"
        ),
        "paired_id_count": paired_count,
        "same_expected_source_pair_count": same_source_pairs,
        "direct_language_gap_interpretation_supported": comparable,
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answerable_rows = [row for row in rows if row["Answerable"]]
    unanswerable_rows = [row for row in rows if not row["Answerable"]]
    judge_attempted = [
        row for row in rows
        if row["Judge Error"] not in {
            "SKIPPED",
            "GENERATION_FAILED",
            "PIPELINE_FAILED",
        }
    ]
    judge_rows = [row for row in judge_attempted if not row["Judge Error"]]
    latencies = [
        float(row["Client Response Time (ms)"])
        for row in rows
        if row.get("Client Response Time (ms)") is not None
    ]
    estimated_e2e_latencies = [
        float(row["Estimated Sequential E2E (ms)"])
        for row in rows
        if row.get("Estimated Sequential E2E (ms)") is not None
    ]
    failure_categories = Counter(
        str(row.get("Failure Category") or "")
        for row in rows
        if row.get("Pipeline Failed")
    )
    failure_stages = Counter(
        str(row.get("Failure Stage") or "")
        for row in rows
        if row.get("Pipeline Failed")
    )

    return {
        "total_questions": len(rows),
        "answerable_questions": len(answerable_rows),
        "unanswerable_questions": len(unanswerable_rows),
        "normalized_exact_match": mean(row["Normalized Exact Match"] for row in answerable_rows),
        "token_f1": mean(row["Token F1"] for row in answerable_rows),
        "keyword_coverage": mean(row["Keyword Coverage"] for row in answerable_rows),
        "question_keyword_coverage": mean(
            row["Question Keyword Coverage"] for row in answerable_rows
        ),
        "question_answer_keyword_coverage": mean(
            row["Question+Answer Keyword Coverage"] for row in answerable_rows
        ),
        "faithfulness_1_to_5": mean(row["Faithfulness"] for row in judge_rows),
        "answer_relevance_1_to_5": mean(row["Answer Relevance"] for row in judge_rows),
        "context_precision": mean(row["Context Precision"] for row in answerable_rows),
        "context_recall": mean(row["Context Recall"] for row in answerable_rows),
        "citation_precision": mean(row["Citation Precision"] for row in answerable_rows),
        "citation_recall": mean(row["Citation Recall"] for row in answerable_rows),
        "citation_f1": mean(row["Citation F1"] for row in answerable_rows),
        "citation_accuracy": mean(row["Citation Accuracy"] for row in answerable_rows),
        "precision_at_k": mean(row["Precision@K"] for row in answerable_rows),
        "recall_at_k": mean(row["Recall@K"] for row in answerable_rows),
        "hit_at_k": mean(row["Hit@K"] for row in answerable_rows),
        "mrr": mean(row["MRR"] for row in answerable_rows),
        "top1_accuracy": mean(row["Top-1 Accuracy"] for row in answerable_rows),
        "ndcg_at_k": mean(row["NDCG@K"] for row in answerable_rows),
        "retrieval_debug_coverage": mean(row["Retrieval Debug Available"] for row in rows),
        "average_retrieval_time_ms": mean(row["Retrieval Time (ms)"] for row in rows),
        "false_refusal_rate": mean(row["False Refusal"] for row in answerable_rows),
        "unanswerable_safety_rate": mean(row["Correct Unanswerable Refusal"] for row in unanswerable_rows),
        "unanswerable_no_citation_rate": mean(row["No Citation On Unanswerable"] for row in unanswerable_rows),
        "unanswerable_no_result_rate": mean(row["Retrieval No Result"] for row in unanswerable_rows),
        "hallucination_rate": mean(row["Hallucination"] for row in judge_rows),
        "pipeline_failure_rate": mean(row["Pipeline Failed"] for row in rows),
        "retrieval_or_context_failure_rate": mean(
            int(row["Failure Category"] == "retrieval_or_context")
            for row in rows
        ),
        "answer_postprocessing_failure_rate": mean(
            int(row["Failure Category"] == "answer_postprocessing")
            for row in rows
        ),
        "generation_output_failure_rate": mean(
            int(row["Failure Category"] == "generation_output")
            for row in rows
        ),
        "generation_failure_rate": mean(row["Generation Failed"] for row in rows),
        "failure_category_counts": {
            key or "unspecified": value
            for key, value in sorted(failure_categories.items())
        },
        "failure_stage_counts": {
            key or "unspecified": value
            for key, value in sorted(failure_stages.items())
        },
        "judge_error_rate": (
            round(1 - (len(judge_rows) / len(judge_attempted)), 4)
            if judge_attempted
            else None
        ),
        "average_response_time_ms": mean(latencies),
        "median_response_time_ms": round(statistics.median(latencies), 2) if latencies else None,
        "p95_response_time_ms": percentile(latencies, 0.95),
        "average_estimated_sequential_e2e_ms": mean(estimated_e2e_latencies),
        "median_estimated_sequential_e2e_ms": (
            round(statistics.median(estimated_e2e_latencies), 2)
            if estimated_e2e_latencies
            else None
        ),
        "p95_estimated_sequential_e2e_ms": percentile(
            estimated_e2e_latencies,
            0.95,
        ),
        "confidence_intervals_95": {
            "pipeline_failure_rate": wilson_interval_95(
                row["Pipeline Failed"] for row in rows
            ),
            "false_refusal_rate": wilson_interval_95(
                row["False Refusal"] for row in answerable_rows
            ),
            "unanswerable_safety_rate": wilson_interval_95(
                row["Correct Unanswerable Refusal"] for row in unanswerable_rows
            ),
            "unanswerable_no_result_rate": wilson_interval_95(
                row["Retrieval No Result"] for row in unanswerable_rows
            ),
            "hit_at_k": wilson_interval_95(
                row["Hit@K"] for row in answerable_rows
            ),
            "top1_accuracy": wilson_interval_95(
                row["Top-1 Accuracy"] for row in answerable_rows
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ground-truth",
        type=Path,
        action="append",
        dest="ground_truth_files",
        help="Repeat this option for English and Indonesian CSV files.",
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "results",
    )
    parser.add_argument("--output-prefix", default=None)
    parser.add_argument("--skip-llm-judge", action="store_true")
    parser.add_argument(
        "--allow-self-judge",
        action="store_true",
        help="Explicitly allow the evaluated model to judge its own answers.",
    )
    parser.add_argument(
        "--benchmark-role",
        choices=("development", "holdout"),
        default="development",
    )
    args = parser.parse_args()

    datasets = args.ground_truth_files or DEFAULT_DATASETS
    gt_items = load_ground_truth_files(datasets)
    ground_truth = {str(item["id"]): item for item in gt_items}
    answers = json.loads(args.input.resolve().read_text(encoding="utf-8"))
    if not isinstance(answers, list):
        raise ValueError("Input answers file must contain a JSON array")

    answer_ids = {str(item.get("id") or "") for item in answers if isinstance(item, dict)}
    missing_ids = sorted(set(ground_truth) - answer_ids)
    if missing_ids:
        raise RuntimeError(
            f"Input is missing {len(missing_ids)} questions: {', '.join(missing_ids[:10])}"
        )

    model_names = {str(item.get("model") or "unknown") for item in answers}
    if len(model_names) != 1:
        raise ValueError(f"Input must contain one model only; found {sorted(model_names)}")
    model = next(iter(model_names))
    resolved_names = {str(item.get("model_name") or model) for item in answers}
    if len(resolved_names) != 1:
        raise ValueError(f"Input contains multiple concrete model names: {sorted(resolved_names)}")
    model_name = next(iter(resolved_names))
    if (
        not args.skip_llm_judge
        and not args.allow_self_judge
        and model_name.strip().casefold() == LLM_MODEL.strip().casefold()
    ):
        raise RuntimeError(
            "The configured judge is the same as the evaluated model. "
            "Use an independent judge, --skip-llm-judge, or explicitly "
            "acknowledge the limitation with --allow-self-judge."
        )
    prefix = args.output_prefix or model

    rows: list[dict[str, Any]] = []
    print(f"Dataset: {dataset_summary(gt_items)}")
    print(f"Provider under evaluation: {model}")
    print(f"Concrete model: {model_name}")
    print(f"LLM judge: {'SKIPPED' if args.skip_llm_judge else LLM_MODEL}")

    for index, item in enumerate(answers, start=1):
        qid = str(item.get("id") or "")
        gt = ground_truth.get(qid)
        if gt is None:
            continue
        print(f"[{index}/{len(answers)}] {qid}")

        generated_answer = str(item.get("generated_answer") or "")
        generation_failed = bool(item.get("generation_failed"))
        pipeline_failed = bool(item.get("pipeline_failed")) or generation_failed
        structured_refusal = (
            str(item.get("generation_mode") or "").strip().casefold()
            == "retrieval_refusal"
        )
        failure_category = str(item.get("failure_category") or "").strip()
        if pipeline_failed and not failure_category:
            if structured_refusal:
                # Backward-compatible correction for v4 rows, which marked a
                # deterministic retrieval refusal as generation_failed.
                failure_category = "retrieval_or_context"
                generation_failed = False
            else:
                failure_category = (
                    "generation_or_provider"
                    if generation_failed
                    else "pipeline_unknown"
                )
        expected_answer = str(gt.get("expected_answer") or "")
        answerable = bool(gt.get("answerable"))
        abstained = structured_refusal or detect_abstention(generated_answer)
        metadata = source_metrics(
            item.get("retrieved_sources") or [],
            gt.get("references") or [],
            item.get("citation") or [],
            answerable=answerable,
        )
        retrieval_top_k = int(item.get("retrieval_top_k") or 5)
        ranked_metrics = ranked_retrieval_metrics(
            item.get("ranked_candidates") or [],
            gt.get("references") or [],
            answerable=answerable,
            top_k=retrieval_top_k,
        )
        em = exact_match(expected_answer, generated_answer) if answerable else None
        f1 = token_f1(expected_answer, generated_answer) if answerable else None
        keywords = list(gt.get("expected_answer_keywords") or [])
        coverage = (
            keyword_coverage(keywords, str(gt.get("question") or ""), generated_answer)
            if answerable
            else None
        )
        question_coverage = (
            question_keyword_coverage(keywords, str(gt.get("question") or ""))
            if answerable
            else None
        )
        question_answer_coverage = (
            question_answer_keyword_coverage(
                keywords,
                str(gt.get("question") or ""),
                generated_answer,
            )
            if answerable
            else None
        )

        if pipeline_failed:
            semantic = {
                "faithfulness": None,
                "answer_relevance": None,
                "is_hallucination": None,
                "reason": str(
                    item.get("pipeline_error")
                    or item.get("generation_error")
                    or "Pipeline failed"
                ),
                "judge_error": (
                    "GENERATION_FAILED"
                    if generation_failed
                    else "PIPELINE_FAILED"
                ),
            }
        elif args.skip_llm_judge:
            semantic = {
                "faithfulness": None,
                "answer_relevance": None,
                "is_hallucination": None,
                "reason": "",
                "judge_error": "SKIPPED",
            }
        else:
            semantic = llm_judge(
                question=str(gt.get("question") or ""),
                expected_answer=expected_answer,
                context=str(item.get("retrieved_context") or ""),
                answer=generated_answer,
                answerable=answerable,
            )

        citations = item.get("citation") or []
        correct_unanswerable = int(
            (not answerable)
            and abstained
            and not citations
            and not pipeline_failed
        )
        retrieval_time_ms = item.get("retrieval_time_ms")
        client_response_time_ms = item.get("client_response_time_ms")
        retrieval_time_value = (
            float(retrieval_time_ms) if retrieval_time_ms is not None else None
        )
        client_time_value = (
            float(client_response_time_ms)
            if client_response_time_ms is not None
            else None
        )
        estimated_sequential_e2e = (
            retrieval_time_value + client_time_value
            if retrieval_time_value is not None and client_time_value is not None
            else None
        )
        row = {
            "ID": qid,
            "Model": model,
            "Model Name": model_name,
            "Language": str(gt.get("language") or item.get("language") or ""),
            "Answerable": answerable,
            "Question": gt.get("question"),
            "Expected Answer": expected_answer,
            "Expected Keywords": " | ".join(keywords),
            "Generated Answer": generated_answer,
            "Expected Source": " | ".join(
                str(reference.get("document") or "")
                for reference in gt.get("references") or []
            ),
            "Retrieved Sources": " | ".join(
                str(source.get("document") or source.get("document_name") or "")
                for source in item.get("retrieved_sources") or []
                if isinstance(source, dict)
            ),
            "Citations": " | ".join(
                str(source.get("document") or source.get("document_name") or "")
                for source in citations
                if isinstance(source, dict)
            ),
            "Pipeline Failed": int(pipeline_failed),
            "Failure Category": failure_category,
            "Failure Stage": str(item.get("failure_stage") or ""),
            "Failure Reason": str(item.get("failure_reason") or ""),
            "Rejected Native Answer": str(
                item.get("rejected_native_answer") or ""
            ),
            "Citation Validation": json.dumps(
                item.get("citation_validation") or {},
                ensure_ascii=False,
                sort_keys=True,
            ),
            "Generation Mode": str(item.get("generation_mode") or ""),
            "Pipeline Error": str(item.get("pipeline_error") or ""),
            "Context Count Before Failure": int(
                item.get("context_count_before_failure")
                or len(item.get("generation_contexts") or [])
            ),
            "Retrieval Mode": str(item.get("retrieval_mode") or ""),
            "Retrieval Query": str(item.get("retrieval_query") or ""),
            "Backend Build Version": str(item.get("backend_build_version") or ""),
            "Generation Failed": int(generation_failed),
            "Generation Error": str(item.get("generation_error") or ""),
            "Abstained": int(abstained),
            "False Refusal": int(answerable and (abstained or pipeline_failed)),
            "Correct Unanswerable Refusal": correct_unanswerable,
            "No Citation On Unanswerable": int((not answerable) and not citations),
            "Normalized Exact Match": round(em, 4) if em is not None else None,
            "Token F1": round(f1, 4) if f1 is not None else None,
            "Keyword Coverage": round(coverage, 4) if coverage is not None else None,
            "Question Keyword Coverage": (
                round(question_coverage, 4)
                if question_coverage is not None
                else None
            ),
            "Question+Answer Keyword Coverage": (
                round(question_answer_coverage, 4)
                if question_answer_coverage is not None
                else None
            ),
            "Faithfulness": semantic["faithfulness"],
            "Answer Relevance": semantic["answer_relevance"],
            "Context Precision": (
                round(metadata["context_precision"], 4)
                if metadata["context_precision"] is not None
                else None
            ),
            "Context Recall": (
                round(metadata["context_recall"], 4)
                if metadata["context_recall"] is not None
                else None
            ),
            "Citation Accuracy": (
                round(metadata["citation_accuracy"], 4)
                if metadata["citation_accuracy"] is not None
                else None
            ),
            "Citation Precision": (
                round(metadata["citation_precision"], 4)
                if metadata["citation_precision"] is not None
                else None
            ),
            "Citation Recall": (
                round(metadata["citation_recall"], 4)
                if metadata["citation_recall"] is not None
                else None
            ),
            "Citation F1": (
                round(metadata["citation_f1"], 4)
                if metadata["citation_f1"] is not None
                else None
            ),
            "Retrieval Top K": retrieval_top_k,
            "Precision@K": (
                round(ranked_metrics["precision_at_k"], 4)
                if ranked_metrics["precision_at_k"] is not None
                else None
            ),
            "Recall@K": (
                round(ranked_metrics["recall_at_k"], 4)
                if ranked_metrics["recall_at_k"] is not None
                else None
            ),
            "Hit@K": (
                round(ranked_metrics["hit_at_k"], 4)
                if ranked_metrics["hit_at_k"] is not None
                else None
            ),
            "MRR": (
                round(ranked_metrics["mrr"], 4)
                if ranked_metrics["mrr"] is not None
                else None
            ),
            "Top-1 Accuracy": (
                round(ranked_metrics["top1_accuracy"], 4)
                if ranked_metrics["top1_accuracy"] is not None
                else None
            ),
            "NDCG@K": (
                round(ranked_metrics["ndcg_at_k"], 4)
                if ranked_metrics["ndcg_at_k"] is not None
                else None
            ),
            "First Relevant Rank": ranked_metrics["first_relevant_rank"],
            "Retrieval Debug Available": int(bool(item.get("ranked_candidates"))),
            "Retrieval Time (ms)": retrieval_time_value,
            "Retrieval No Result": metadata["retrieval_no_result"],
            "Hallucination": (
                int(semantic["is_hallucination"])
                if semantic["is_hallucination"] is not None
                else None
            ),
            "Judge Reason": semantic["reason"],
            "Judge Error": semantic["judge_error"],
            "System Confidence": item.get("system_confidence"),
            "Backend Response Time (ms)": item.get("backend_response_time_ms"),
            "Client Response Time (ms)": client_time_value,
            "Estimated Sequential E2E (ms)": (
                round(estimated_sequential_e2e, 2)
                if estimated_sequential_e2e is not None
                else None
            ),
            "Context Fingerprint": item.get("context_fingerprint"),
        }
        rows.append(row)

    if not rows:
        raise RuntimeError("No matching evaluation rows were found")

    pairing = bilingual_pairing_diagnostics(gt_items)
    summary = {
        "project": "LapisAI Enterprise Knowledge Assistant (RAG)",
        "evaluation": "Bilingual RAG generation evaluation",
        "benchmark_role": args.benchmark_role,
        "model": model,
        "model_name": model_name,
        "judge_model": None if args.skip_llm_judge else LLM_MODEL,
        "judge_independent": bool(
            not args.skip_llm_judge
            and model_name.strip().casefold() != LLM_MODEL.strip().casefold()
        ),
        "ground_truth_files": [str(path.resolve()) for path in datasets],
        "dataset": dataset_summary(gt_items),
        "language_pairing": pairing,
        "reproducibility": reproducibility_manifest(
            datasets=[Path(path).resolve() for path in datasets],
            input_path=args.input.resolve(),
            answers=answers,
            model_name=model_name,
            judge_model=None if args.skip_llm_judge else LLM_MODEL,
        ),
        "overall": summarize_rows(rows),
        "by_language": {
            language: summarize_rows([row for row in rows if row["Language"] == language])
            for language in ("EN", "ID")
        },
        "notes": [
            "Precision@K, Recall@K, Hit@K, MRR, Top-1 Accuracy, and NDCG@K are evaluated at document level because the CSV has no page labels.",
            "Precision@K remains a standard ranking metric; with one relevant document its maximum at K=5 is 0.2. Use Hit@K, MRR, Top-1 Accuracy, or NDCG@K for easier interpretation.",
            "Context precision/recall evaluate the final generation contexts; ranked retrieval metrics evaluate the pre-generation retrieval snapshot.",
            "Citation F1 combines citation precision and recall. Citation Accuracy is retained as a compatibility alias for Citation F1.",
            "Pipeline failures are classified by their precise stage; late answer/citation failures preserve evaluation contexts and are not counted as retrieval misses.",
            "Unanswerable safety requires a refusal and no citation.",
            "The same configured judge model must be used for every compared model.",
            "Keyword Coverage is answer-only. Question Keyword Coverage and Question+Answer Keyword Coverage are diagnostics for annotation leakage and historical comparability.",
            "Estimated Sequential E2E is retrieval time plus client generation-call time, not a directly instrumented wall-clock request latency.",
            "Wilson 95% confidence intervals are reported for binary rates; small unanswerable sets can therefore have wide intervals.",
            (
                "English-vs-Indonesian scores are descriptive only because the two language sets do not use equivalent source targets."
                if not pairing["direct_language_gap_interpretation_supported"]
                else "English-vs-Indonesian scores use paired IDs with equivalent expected source targets."
            ),
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / f"generation_results_{prefix}.csv"
    json_path = args.output_dir / f"generation_summary_{prefix}.json"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n[SUCCESS]")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Details: {csv_path}")
    print(f"Summary: {json_path}")


if __name__ == "__main__":
    main()
