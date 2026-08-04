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
import time
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Iterable

try:
    import requests
except ModuleNotFoundError:
    requests = None  # type: ignore[assignment]

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:
        return False

try:
    from .dataset_utils import dataset_summary, load_ground_truth_files
    from .atomic_io import replace_file_with_retry
except ImportError:  # Direct script execution.
    from dataset_utils import dataset_summary, load_ground_truth_files
    from atomic_io import replace_file_with_retry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
EVALUATION_DIR = PROJECT_ROOT / "evaluation"
DEFAULT_DATASETS = [
    EVALUATION_DIR / "datasets" / "qna_english_user.csv",
    EVALUATION_DIR / "datasets" / "qna_indonesia_user.csv",
]
LLM_BASE_URL = os.getenv("EVAL_LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("EVAL_LLM_API_KEY", "ollama")
LLM_MODEL = os.getenv("EVAL_LLM_MODEL", "").strip()
JUDGE_MAX_RETRIES = max(0, int(os.getenv("EVAL_JUDGE_MAX_RETRIES", "5")))
JUDGE_REQUEST_TIMEOUT_SECONDS = max(
    1.0,
    float(os.getenv("EVAL_JUDGE_REQUEST_TIMEOUT_SECONDS", "180")),
)
JUDGE_MAX_FORMAT_RETRIES = max(
    0,
    int(os.getenv("EVAL_JUDGE_MAX_FORMAT_RETRIES", "2")),
)
JUDGE_MAX_TOKENS = max(
    64,
    int(os.getenv("EVAL_JUDGE_MAX_TOKENS", "256")),
)
JUDGE_DISABLE_THINKING_MODE = os.getenv(
    "EVAL_JUDGE_DISABLE_THINKING",
    "auto",
).strip().casefold()
JUDGE_MIN_INTERVAL_SECONDS = max(
    0.0,
    float(os.getenv("EVAL_JUDGE_MIN_INTERVAL_SECONDS", "0")),
)
JUDGE_MAX_RATE_LIMIT_WAIT_SECONDS = max(
    0.0,
    float(os.getenv("EVAL_JUDGE_MAX_RATE_LIMIT_WAIT_SECONDS", "120")),
)
_LAST_JUDGE_REQUEST_AT = 0.0
_JUDGE_CIRCUIT_ERROR = ""

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


def model_reference_is_mutable(model_name: str) -> bool:
    """Conservatively identify explicitly mutable local model references."""
    normalized = str(model_name or "").strip().casefold()
    if (
        not normalized
        or normalized.endswith(":latest")
        or normalized in {"latest", "default"}
    ):
        return True
    if "@sha256:" in normalized:
        return False
    if ":" in normalized and normalized.rsplit(":", 1)[-1] not in {"", "latest"}:
        return False
    return re.search(r"(?:^|[-_.])v?\d+(?:[.-]\d+)*", normalized) is None


def validate_answer_records(
    answers: Any,
    ground_truth: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Require exactly one well-formed answer row for every benchmark item."""
    if not isinstance(answers, list):
        raise ValueError("Input answers file must contain a JSON array")

    invalid_rows = [
        index
        for index, item in enumerate(answers, start=1)
        if not isinstance(item, dict)
    ]
    if invalid_rows:
        raise ValueError(
            "Input answers contains non-object rows at positions: "
            + ", ".join(str(index) for index in invalid_rows[:10])
        )

    typed_answers = list(answers)
    answer_ids = [str(item.get("id") or "").strip() for item in typed_answers]
    blank_positions = [
        index
        for index, qid in enumerate(answer_ids, start=1)
        if not qid
    ]
    if blank_positions:
        raise ValueError(
            "Input answers contains blank IDs at positions: "
            + ", ".join(str(index) for index in blank_positions[:10])
        )

    counts = Counter(answer_ids)
    duplicate_ids = sorted(qid for qid, count in counts.items() if count > 1)
    if duplicate_ids:
        raise ValueError(
            "Input answers contains duplicate IDs: "
            + ", ".join(duplicate_ids[:10])
        )

    expected_ids = set(ground_truth)
    actual_ids = set(answer_ids)
    missing_ids = sorted(expected_ids - actual_ids)
    extra_ids = sorted(actual_ids - expected_ids)
    if missing_ids or extra_ids:
        raise RuntimeError(
            "Input answer IDs do not match the evaluation dataset. "
            f"Missing={missing_ids[:10]}, extra={extra_ids[:10]}."
        )
    return typed_answers


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


class JudgePayloadError(ValueError):
    """The judge returned JSON, but it did not satisfy the scoring contract."""


def validate_judge_payload(result: Any) -> dict[str, Any]:
    """Validate all semantic-judge fields before a row counts as successful."""
    if not isinstance(result, dict):
        raise JudgePayloadError("Judge response must be one JSON object.")

    scores: dict[str, float] = {}
    for key in ("faithfulness", "answer_relevance"):
        if key not in result:
            raise JudgePayloadError(f"Judge response is missing required field {key!r}.")
        try:
            score = float(result[key])
        except (TypeError, ValueError) as error:
            raise JudgePayloadError(f"Judge field {key!r} must be numeric.") from error
        if not math.isfinite(score) or not 1.0 <= score <= 5.0:
            raise JudgePayloadError(
                f"Judge field {key!r} must be a finite number from 1 to 5."
            )
        scores[key] = score

    if "is_hallucination" not in result:
        raise JudgePayloadError(
            "Judge response is missing required field 'is_hallucination'."
        )
    raw_hallucination = result["is_hallucination"]
    if isinstance(raw_hallucination, bool):
        is_hallucination = raw_hallucination
    elif isinstance(raw_hallucination, int) and raw_hallucination in {0, 1}:
        is_hallucination = bool(raw_hallucination)
    elif isinstance(raw_hallucination, str):
        normalized = raw_hallucination.strip().casefold()
        if normalized in {"true", "1", "yes"}:
            is_hallucination = True
        elif normalized in {"false", "0", "no"}:
            is_hallucination = False
        else:
            raise JudgePayloadError(
                "Judge field 'is_hallucination' must be true or false."
            )
    else:
        raise JudgePayloadError(
            "Judge field 'is_hallucination' must be true or false."
        )

    return {
        **scores,
        "is_hallucination": is_hallucination,
        "reason": str(result.get("reason") or "")[:240],
    }


def parse_json_object(text: str) -> dict[str, Any]:
    clean = re.sub(r"```(?:json)?|```", "", str(text or ""), flags=re.I).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def judge_thinking_disabled(model_name: str | None = None) -> bool:
    """Resolve whether semantic judging should suppress model reasoning output."""
    mode = JUDGE_DISABLE_THINKING_MODE
    if mode == "auto":
        reference = LLM_MODEL if model_name is None else str(model_name or "")
        return "qwen3" in reference.casefold()
    if mode in {"1", "true", "yes", "on"}:
        return True
    if mode in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        "EVAL_JUDGE_DISABLE_THINKING must be auto, true, or false."
    )


def judge_system_instruction(model_name: str | None = None) -> str:
    """Return the structured-output instruction for the configured judge."""
    instruction = "Return one valid JSON object only."
    if judge_thinking_disabled(model_name):
        # Qwen3 supports this soft switch in user or system messages. It keeps
        # the token budget available for the JSON answer instead of reasoning.
        return f"{instruction} /no_think"
    return instruction


def judge_message_content(payload: Any) -> str:
    """Extract non-empty assistant content with actionable empty-output errors."""
    if not isinstance(payload, dict):
        raise JudgePayloadError("Judge API response must be one JSON object.")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise JudgePayloadError("Judge API response has no choices.")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise JudgePayloadError("Judge API response contains an invalid choice.")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise JudgePayloadError("Judge API response has no assistant message.")

    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        text_parts = [
            str(part.get("text") or "")
            for part in content
            if isinstance(part, dict) and part.get("type") in {None, "text"}
        ]
        joined = "".join(text_parts).strip()
        if joined:
            return joined

    reasoning_chars = sum(
        len(str(message.get(field) or ""))
        for field in ("reasoning", "reasoning_content", "thinking")
    )
    finish_reason = str(choice.get("finish_reason") or "unknown")
    raise JudgePayloadError(
        "Judge returned empty assistant content "
        f"(finish_reason={finish_reason}, reasoning_chars={reasoning_chars})."
    )


def _judge_retry_after(response: Any) -> float | None:
    value = str(response.headers.get("retry-after") or "").strip()
    try:
        return max(0.0, float(value)) if value else None
    except ValueError:
        return None


def _is_transient_judge_exception(error: Exception) -> bool:
    """Return whether a request exception is safe to retry."""
    exceptions = getattr(requests, "exceptions", None)
    if exceptions is None:
        return False
    retryable = tuple(
        exception_type
        for exception_type in (
            getattr(exceptions, "Timeout", None),
            getattr(exceptions, "ConnectionError", None),
        )
        if isinstance(exception_type, type)
    )
    return bool(retryable) and isinstance(error, retryable)


def _post_judge_request(
    endpoint: str,
    headers: dict[str, str],
    request: dict[str, Any],
) -> Any:
    """Send one judge request with pacing and provider-aware transient retries."""
    global _LAST_JUDGE_REQUEST_AT

    for attempt in range(JUDGE_MAX_RETRIES + 1):
        since_last = time.monotonic() - _LAST_JUDGE_REQUEST_AT
        pacing_delay = max(0.0, JUDGE_MIN_INTERVAL_SECONDS - since_last)
        if pacing_delay:
            time.sleep(pacing_delay)

        _LAST_JUDGE_REQUEST_AT = time.monotonic()
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=request,
                timeout=JUDGE_REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as error:
            if not _is_transient_judge_exception(error) or attempt >= JUDGE_MAX_RETRIES:
                raise
            delay = min(2**attempt, 8)
            print(
                f"[JUDGE TRANSIENT ERROR] {type(error).__name__}; "
                f"wait {delay:.1f}s before retry "
                f"{attempt + 1}/{JUDGE_MAX_RETRIES}"
            )
            time.sleep(delay)
            continue
        if response.status_code != 429 and response.status_code < 500:
            return response
        if attempt >= JUDGE_MAX_RETRIES:
            return response

        retry_delay = _judge_retry_after(response)
        delay = retry_delay if retry_delay is not None else min(2**attempt, 8)
        if delay > JUDGE_MAX_RATE_LIMIT_WAIT_SECONDS:
            return response
        label = "RATE LIMIT" if response.status_code == 429 else "SERVER ERROR"
        print(
            f"[JUDGE {label}] wait {delay:.1f}s before retry "
            f"{attempt + 1}/{JUDGE_MAX_RETRIES}"
        )
        time.sleep(delay)

    raise RuntimeError("Unreachable judge retry state")


def llm_judge(
    *,
    question: str,
    expected_answer: str,
    context: str,
    answer: str,
    answerable: bool,
) -> dict[str, Any]:
    global _JUDGE_CIRCUIT_ERROR

    if requests is None:
        return {
            "faithfulness": None,
            "answer_relevance": None,
            "is_hallucination": None,
            "reason": "",
            "judge_error": (
                "Dependency 'requests' is required when the LLM judge is enabled."
            ),
        }
    if _JUDGE_CIRCUIT_ERROR:
        return {
            "faithfulness": None,
            "answer_relevance": None,
            "is_hallucination": None,
            "reason": "",
            "judge_error": _JUDGE_CIRCUIT_ERROR,
        }

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
        last_payload_error: Exception | None = None
        for format_attempt in range(JUDGE_MAX_FORMAT_RETRIES + 1):
            disable_thinking = judge_thinking_disabled(LLM_MODEL)
            request = {
                "model": LLM_MODEL,
                "temperature": 0,
                "max_tokens": JUDGE_MAX_TOKENS,
                "messages": [
                    {
                        "role": "system",
                        "content": judge_system_instruction(LLM_MODEL),
                    },
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            }
            if disable_thinking:
                # Ollama's OpenAI-compatible endpoint maps this to think=false.
                # The /no_think prompt remains as a compatible fallback.
                request["reasoning_effort"] = "none"
            response = _post_judge_request(endpoint, headers, request)
            # Some OpenAI-compatible servers do not implement response_format
            # or reasoning_effort. Retry schema errors without optional fields.
            if response.status_code in {400, 422}:
                request.pop("response_format", None)
                request.pop("reasoning_effort", None)
                response = _post_judge_request(endpoint, headers, request)
            response.raise_for_status()
            try:
                payload = response.json()
                content = judge_message_content(payload)
                validated = validate_judge_payload(parse_json_object(content))
            except (IndexError, KeyError, TypeError, ValueError) as error:
                last_payload_error = error
                if format_attempt >= JUDGE_MAX_FORMAT_RETRIES:
                    raise
                print(
                    f"[JUDGE INVALID PAYLOAD] {error}; retry "
                    f"{format_attempt + 1}/{JUDGE_MAX_FORMAT_RETRIES}"
                )
                continue
            return {
                **validated,
                "judge_error": "",
            }
        raise RuntimeError(f"Unreachable judge format retry state: {last_payload_error}")
    except Exception as error:
        response = getattr(error, "response", None)
        if response is not None and getattr(response, "status_code", None) == 429:
            _JUDGE_CIRCUIT_ERROR = (
                "LLM judge rate limit remains active; remaining judge calls were "
                "stopped to protect quota. Re-run evaluation after the quota resets."
            )
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
    private_manifest_value = os.getenv("LAPISAI_HOLDOUT_MANIFEST", "").strip()
    private_manifest = Path(private_manifest_value).resolve() if private_manifest_value else None
    if private_manifest is not None:
        if not private_manifest.is_file():
            raise FileNotFoundError(
                f"Configured private holdout manifest is missing: {private_manifest}"
            )
        files.append(private_manifest)
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
        "model_reference_mutable": model_reference_is_mutable(model_name),
        "judge_model": judge_model,
        "judge_independent": bool(
            judge_model
            and judge_model.strip().casefold() != model_name.strip().casefold()
        ),
        "judge_request_settings": (
            {
                "max_http_retries": JUDGE_MAX_RETRIES,
                "request_timeout_seconds": JUDGE_REQUEST_TIMEOUT_SECONDS,
                "max_format_retries": JUDGE_MAX_FORMAT_RETRIES,
                "max_tokens": JUDGE_MAX_TOKENS,
                "disable_thinking_mode": JUDGE_DISABLE_THINKING_MODE,
                "thinking_disabled": judge_thinking_disabled(judge_model),
                "minimum_interval_seconds": JUDGE_MIN_INTERVAL_SECONDS,
                "max_rate_limit_wait_seconds": JUDGE_MAX_RATE_LIMIT_WAIT_SECONDS,
            }
            if judge_model
            else None
        ),
        "private_holdout_manifest": (
            _manifest_path(private_manifest) if private_manifest else None
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
        "retrieval_latency_measurement_modes": sorted({
            str(item.get("retrieval_latency_measurement_mode") or "")
            for item in answers
            if item.get("retrieval_latency_measurement_mode")
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
        english_item = by_language["EN"][key]
        indonesian_item = by_language["ID"][key]
        english_sources = {
            document
            for document, _ in source_set(
                english_item.get("references") or []
            )
        }
        indonesian_sources = {
            document
            for document, _ in source_set(
                indonesian_item.get("references") or []
            )
        }
        if (
            bool(english_item.get("answerable"))
            == bool(indonesian_item.get("answerable"))
            and english_sources == indonesian_sources
        ):
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


def has_complete_judge_result(row: dict[str, Any]) -> bool:
    """Require every semantic metric before a judge call counts as successful."""
    if row.get("Judge Error"):
        return False
    try:
        scores = [float(row[field]) for field in ("Faithfulness", "Answer Relevance")]
    except (KeyError, TypeError, ValueError):
        return False
    if any(not math.isfinite(score) or not 1.0 <= score <= 5.0 for score in scores):
        return False
    return row.get("Hallucination") in {0, 1, False, True}


def write_csv_rows_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write an interruption-safe CSV checkpoint for judge resume."""
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    replace_file_with_retry(temporary, path)


def write_json_lf(path: Path, payload: Any) -> None:
    """Write stable UTF-8 JSON with LF endings on every operating system."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
        file.write("\n")
    replace_file_with_retry(temporary, path)


def load_judge_resume_rows(
    csv_path: Path,
    summary_path: Path,
    *,
    model_name: str,
    judge_model: str,
) -> dict[str, dict[str, str]]:
    """Load prior complete judge rows while preventing cross-model reuse."""
    if not csv_path.is_file():
        return {}

    summary_judge = ""
    summary_model = ""
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary_judge = str(summary.get("judge_model") or "").strip()
        summary_model = str(summary.get("model_name") or "").strip()
        if summary_judge and summary_judge.casefold() != judge_model.casefold():
            raise ValueError(
                "Cannot resume judge rows: cached summary uses a different judge model."
            )
        if summary_model and summary_model.casefold() != model_name.casefold():
            raise ValueError(
                "Cannot resume judge rows: cached summary evaluates a different model."
            )

    cached: dict[str, dict[str, str]] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            qid = str(row.get("ID") or "").strip()
            if not qid:
                continue
            row_judge = str(row.get("Judge Model") or summary_judge).strip()
            if not row_judge:
                raise ValueError(
                    "Cannot resume judge rows without a recorded judge-model reference."
                )
            if row_judge.casefold() != judge_model.casefold():
                raise ValueError(
                    f"Cannot resume {qid}: cached row uses a different judge model."
                )
            cached[qid] = row
    return cached


def reusable_judge_result(
    row: dict[str, str] | None,
    *,
    item: dict[str, Any],
    ground_truth: dict[str, Any],
    model_name: str,
    generated_answer: str,
) -> dict[str, Any] | None:
    """Return a cached semantic result only when every judge input still matches."""
    if not row or str(row.get("Judge Error") or "").strip():
        return None
    expected = {
        "Model Name": model_name,
        "Question": str(ground_truth.get("question") or ""),
        "Expected Answer": str(ground_truth.get("expected_answer") or ""),
        "Generated Answer": generated_answer,
        "Answerable": str(bool(ground_truth.get("answerable"))),
        "Context Fingerprint": str(item.get("context_fingerprint") or ""),
    }
    if any(str(row.get(key) or "") != value for key, value in expected.items()):
        return None
    try:
        validated = validate_judge_payload(
            {
                "faithfulness": row.get("Faithfulness"),
                "answer_relevance": row.get("Answer Relevance"),
                "is_hallucination": row.get("Hallucination"),
                "reason": row.get("Judge Reason"),
            }
        )
    except JudgePayloadError:
        return None
    return {**validated, "judge_error": ""}


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answerable_rows = [row for row in rows if row["Answerable"]]
    unanswerable_rows = [row for row in rows if not row["Answerable"]]
    judge_eligible_rows = [
        row for row in rows
        if row["Judge Error"] not in {
            "GENERATION_FAILED",
            "PIPELINE_FAILED",
        }
    ]
    judge_attempted = [
        row for row in judge_eligible_rows
        if row["Judge Error"] != "SKIPPED"
    ]
    judge_rows = [row for row in judge_attempted if has_complete_judge_result(row)]
    judge_incomplete_rows = [
        row
        for row in judge_attempted
        if not row["Judge Error"] and not has_complete_judge_result(row)
    ]
    retrieval_latencies = [
        float(row["Retrieval Time (ms)"])
        for row in rows
        if row.get("Retrieval Time (ms)") is not None
    ]
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
        "judge_eligible_questions": len(judge_eligible_rows),
        "judge_attempted_questions": len(judge_attempted),
        "judge_successful_questions": len(judge_rows),
        "judge_incomplete_response_questions": len(judge_incomplete_rows),
        "judge_coverage": round(
            len(judge_rows) / len(judge_eligible_rows),
            4,
        ) if judge_eligible_rows else None,
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
        "average_retrieval_time_ms": mean(retrieval_latencies),
        "retrieval_latency_coverage": round(
            len(retrieval_latencies) / len(rows),
            4,
        ) if rows else None,
        "false_refusal_rate": mean(row["False Refusal"] for row in answerable_rows),
        "unanswerable_safety_rate": mean(row["Correct Unanswerable Refusal"] for row in unanswerable_rows),
        "unanswerable_no_citation_rate": mean(row["No Citation On Unanswerable"] for row in unanswerable_rows),
        "unanswerable_no_result_rate": mean(row["Retrieval No Result"] for row in unanswerable_rows),
        "hallucination_rate": mean(row["Hallucination"] for row in judge_rows),
        "grounding_repaired_questions": sum(
            int(row.get("Grounding Repaired") or 0) for row in rows
        ),
        "grounding_repair_rate": mean(
            int(row.get("Grounding Repaired") or 0) for row in rows
        ),
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
        "client_latency_coverage": round(
            len(latencies) / len(rows),
            4,
        ) if rows else None,
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
        "estimated_e2e_latency_coverage": round(
            len(estimated_e2e_latencies) / len(rows),
            4,
        ) if rows else None,
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


def language_latency_diagnostics(
    by_language: dict[str, dict[str, Any]],
    *,
    alert_ratio: float = 1.5,
) -> dict[str, Any]:
    """Expose descriptive ID/EN latency ratios without treating them as quality."""
    english = by_language.get("EN") or {}
    indonesian = by_language.get("ID") or {}
    definitions = (
        ("retrieval", "average_retrieval_time_ms", "retrieval"),
        ("generation_call", "average_response_time_ms", "generation-call"),
        (
            "estimated_sequential_e2e",
            "average_estimated_sequential_e2e_ms",
            "estimated sequential E2E",
        ),
    )
    metrics: dict[str, Any] = {}
    alerts: list[str] = []
    valid_ratio_count = 0
    for output_key, metric_key, label in definitions:
        english_value = english.get(metric_key)
        indonesian_value = indonesian.get(metric_key)
        try:
            english_ms = float(english_value)
            indonesian_ms = float(indonesian_value)
            if english_ms <= 0 or indonesian_ms < 0:
                raise ValueError
        except (TypeError, ValueError):
            metrics[output_key] = {
                "english_ms": english_value,
                "indonesian_ms": indonesian_value,
                "indonesian_over_english_ratio": None,
            }
            continue

        valid_ratio_count += 1
        ratio = indonesian_ms / english_ms
        metrics[output_key] = {
            "english_ms": round(english_ms, 2),
            "indonesian_ms": round(indonesian_ms, 2),
            "indonesian_over_english_ratio": round(ratio, 4),
            "difference_ms": round(indonesian_ms - english_ms, 2),
        }
        if ratio >= alert_ratio:
            alerts.append(
                "Descriptive Indonesian/English "
                f"{label} latency ratio is {ratio:.2f}x "
                f"(alert threshold {alert_ratio:.2f}x)."
            )

    return {
        "status": (
            "DESCRIPTIVE_IMBALANCE"
            if alerts
            else "NO_RATIO_ABOVE_THRESHOLD"
            if valid_ratio_count
            else "INSUFFICIENT_DATA"
        ),
        "alert_ratio": alert_ratio,
        "metrics": metrics,
        "alerts": alerts,
    }


def build_evaluation_status(
    *,
    benchmark_role: str,
    overall: dict[str, Any],
    model_name: str,
    judge_model: str | None,
    judge_independent: bool,
    pairing: dict[str, Any],
    performance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """State whether a run is suitable for a final model-quality claim."""
    blockers: list[str] = []
    warnings: list[str] = []

    if benchmark_role != "holdout":
        blockers.append(
            "Benchmark is a development/regression set, not a blind holdout."
        )
    elif not os.getenv("LAPISAI_HOLDOUT_MANIFEST", "").strip():
        blockers.append(
            "A reviewed private-holdout manifest was not attached to this run."
        )
    judge_coverage = overall.get("judge_coverage")
    if judge_coverage is None or float(judge_coverage) < 1.0:
        blockers.append(
            "Independent LLM-judge coverage is incomplete; faithfulness, "
            "answer relevance, and hallucination metrics are not final."
        )
    if judge_model and not judge_independent:
        blockers.append("The evaluated model was also used as its own judge.")
    elif judge_model:
        warnings.append(
            "Judge independence is based on distinct model-reference strings only; "
            "verify checkpoint digest and model-family independence separately."
        )
    if model_reference_is_mutable(model_name):
        blockers.append(
            "The evaluated model reference is mutable; pin a versioned tag or digest."
        )

    for field, label in (
        ("retrieval_latency_coverage", "retrieval latency"),
        ("client_latency_coverage", "generation-call latency"),
        ("estimated_e2e_latency_coverage", "estimated sequential E2E latency"),
    ):
        value = overall.get(field)
        if value is None or float(value) < 1.0:
            warnings.append(f"Coverage for {label} is below 100%.")

    if not pairing.get("direct_language_gap_interpretation_supported"):
        warnings.append(
            "English and Indonesian subsets have non-equivalent targets; "
            "their score gap is descriptive only."
        )
    warnings.extend(
        str(message)
        for message in (performance or {}).get("alerts") or []
    )
    warnings.append(
        "Sequential E2E latency is retrieval time plus the generation API call, "
        "not one directly instrumented wall-clock request."
    )

    return {
        "status": "FINAL_ELIGIBLE" if not blockers else "DIAGNOSTIC_ONLY",
        "final_eligible": not blockers,
        "blockers": blockers,
        "warnings": warnings,
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
        "--resume-judge",
        action="store_true",
        help=(
            "Reuse complete judge rows from the destination CSV when the judge "
            "model, evaluated model, question, answer, and context fingerprint match."
        ),
    )
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
    if args.resume_judge and args.skip_llm_judge:
        parser.error("--resume-judge cannot be combined with --skip-llm-judge")

    datasets = args.ground_truth_files or DEFAULT_DATASETS
    gt_items = load_ground_truth_files(datasets)
    ground_truth = {str(item["id"]): item for item in gt_items}
    answers = validate_answer_records(
        json.loads(args.input.resolve().read_text(encoding="utf-8")),
        ground_truth,
    )

    model_names = {str(item.get("model") or "unknown") for item in answers}
    if len(model_names) != 1:
        raise ValueError(f"Input must contain one model only; found {sorted(model_names)}")
    model = next(iter(model_names))
    resolved_names = {str(item.get("model_name") or model) for item in answers}
    if len(resolved_names) != 1:
        raise ValueError(f"Input contains multiple concrete model names: {sorted(resolved_names)}")
    model_name = next(iter(resolved_names))
    if not args.skip_llm_judge and not LLM_MODEL:
        raise RuntimeError(
            "EVAL_LLM_MODEL is not configured. Set an explicit independent "
            "judge model, or use --skip-llm-judge only for a development run."
        )
    if args.benchmark_role == "holdout":
        if args.skip_llm_judge:
            raise RuntimeError(
                "A holdout evaluation requires complete independent LLM-judge "
                "coverage; --skip-llm-judge is not allowed."
            )
        if args.allow_self_judge:
            raise RuntimeError("--allow-self-judge is not allowed for a holdout evaluation.")
        if model_reference_is_mutable(model_name):
            raise RuntimeError(
                "A holdout evaluation requires an immutable evaluated-model tag or digest."
            )
        if model_reference_is_mutable(LLM_MODEL):
            raise RuntimeError(
                "A holdout evaluation requires an immutable judge-model tag or digest."
            )
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
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / f"generation_results_{prefix}.csv"
    json_path = args.output_dir / f"generation_summary_{prefix}.json"
    preserving_existing_judge_cache = args.resume_judge and csv_path.is_file()
    resume_judge_rows = (
        load_judge_resume_rows(
            csv_path,
            json_path,
            model_name=model_name,
            judge_model=LLM_MODEL,
        )
        if args.resume_judge
        else {}
    )

    rows: list[dict[str, Any]] = []
    print(f"Dataset: {dataset_summary(gt_items)}")
    print(f"Provider under evaluation: {model}")
    print(f"Concrete model: {model_name}")
    print(f"LLM judge: {'SKIPPED' if args.skip_llm_judge else LLM_MODEL}")
    if args.resume_judge:
        print(f"Judge resume cache: {len(resume_judge_rows)} row(s)")

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
            semantic = reusable_judge_result(
                resume_judge_rows.get(qid),
                item=item,
                ground_truth=gt,
                model_name=model_name,
                generated_answer=generated_answer,
            )
            if semantic is not None:
                print(f"[JUDGE RESUME] {qid}")
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
            "Grounding Validation": json.dumps(
                item.get("grounding_validation") or {},
                ensure_ascii=False,
                sort_keys=True,
            ),
            "Grounding Repaired": int(bool(item.get("grounding_repaired"))),
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
            # An explicitly captured empty candidate list is valid diagnostics
            # for an unanswerable query; it must not be treated as missing data.
            "Retrieval Debug Available": int(
                "ranked_candidates" in item
                and isinstance(item.get("ranked_candidates"), list)
            ),
            "Retrieval Time (ms)": retrieval_time_value,
            "Retrieval No Result": metadata["retrieval_no_result"],
            "Hallucination": (
                int(semantic["is_hallucination"])
                if semantic["is_hallucination"] is not None
                else None
            ),
            "Judge Reason": semantic["reason"],
            "Judge Error": semantic["judge_error"],
            "Judge Model": None if args.skip_llm_judge else LLM_MODEL,
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
        # A fresh run checkpoints after every row. During resume, keep the
        # original full cache intact until the replacement report is complete.
        if not args.skip_llm_judge and not preserving_existing_judge_cache:
            write_csv_rows_atomic(csv_path, rows)

    if not rows:
        raise RuntimeError("No matching evaluation rows were found")

    pairing = bilingual_pairing_diagnostics(gt_items)
    overall = summarize_rows(rows)
    by_language = {
        language: summarize_rows(
            [row for row in rows if row["Language"] == language]
        )
        for language in ("EN", "ID")
    }
    performance = language_latency_diagnostics(by_language)
    judge_model = None if args.skip_llm_judge else LLM_MODEL
    judge_independent = bool(
        judge_model
        and model_name.strip().casefold() != judge_model.strip().casefold()
    )
    reproducibility = reproducibility_manifest(
        datasets=[Path(path).resolve() for path in datasets],
        input_path=args.input.resolve(),
        answers=answers,
        model_name=model_name,
        judge_model=judge_model,
    )
    evaluation_status = build_evaluation_status(
        benchmark_role=args.benchmark_role,
        overall=overall,
        model_name=model_name,
        judge_model=judge_model,
        judge_independent=judge_independent,
        pairing=pairing,
        performance=performance,
    )
    summary = {
        "report_schema_version": 2,
        "project": "LapisAI Enterprise Knowledge Assistant (RAG)",
        "evaluation": "Bilingual RAG generation evaluation",
        "benchmark_role": args.benchmark_role,
        "model": model,
        "model_name": model_name,
        "judge_model": judge_model,
        "judge_independent": judge_independent,
        "judge_independence_basis": (
            "distinct_model_reference_strings_only"
            if judge_independent
            else "not_independent_or_not_configured"
        ),
        "ground_truth_files": [
            _manifest_path(Path(path)) for path in datasets
        ],
        "dataset": dataset_summary(gt_items),
        "language_pairing": pairing,
        "evaluation_status": evaluation_status,
        "performance_diagnostics": performance,
        "reproducibility": reproducibility,
        "overall": overall,
        "by_language": by_language,
        "notes": [
            "Precision@K, Recall@K, Hit@K, MRR, Top-1 Accuracy, and NDCG@K are evaluated at document level because the CSV has no page labels.",
            "Precision@K remains a standard ranking metric; with one relevant document its maximum at K=5 is 0.2. Use Hit@K, MRR, Top-1 Accuracy, or NDCG@K for easier interpretation.",
            "Context precision/recall evaluate the final generation contexts; ranked retrieval metrics evaluate the pre-generation retrieval snapshot.",
            "Citation F1 combines citation precision and recall. Citation Accuracy is retained as a compatibility alias for Citation F1.",
            "Pipeline failures are classified by their precise stage; late answer/citation failures preserve evaluation contexts and are not counted as retrieval misses.",
            "Retrieval Debug Available records whether diagnostics were captured; an explicitly empty candidate list remains valid debug data for an unanswerable item.",
            "Unanswerable safety requires a refusal and no citation.",
            "The same configured judge model must be used for every compared model.",
            "A final-eligible report requires a clean holdout, complete independent judge coverage, and an immutable evaluated-model reference.",
            "Keyword Coverage is answer-only. Question Keyword Coverage and Question+Answer Keyword Coverage are diagnostics for annotation leakage and historical comparability.",
            "Token F1, exact match, and keyword coverage are lexical diagnostics; valid paraphrases and translations can score lower, so they are not substitutes for an independent semantic judge.",
            (
                "Snapshot schema v4 measures one strict retrieval request with the standalone debug baseline disabled; older snapshot latency is not directly comparable."
                if reproducibility["retrieval_latency_measurement_modes"]
                == ["single_strict_retrieval_without_debug_baseline"]
                else "Retrieval latency measurement metadata is legacy, missing, or mixed; do not compare it directly with schema-v4 single-pass latency."
            ),
            "Estimated Sequential E2E is retrieval time plus client generation-call time, not a directly instrumented wall-clock request latency.",
            "Wilson 95% confidence intervals are reported for binary rates; small unanswerable sets can therefore have wide intervals.",
            (
                "English-vs-Indonesian scores are descriptive only because the two language sets do not use equivalent source targets."
                if not pairing["direct_language_gap_interpretation_supported"]
                else "English-vs-Indonesian scores use paired IDs with equivalent expected source targets."
            ),
        ],
    }

    write_csv_rows_atomic(csv_path, rows)
    write_json_lf(json_path, summary)

    judge_error_rate = overall.get("judge_error_rate")
    completion_label = (
        "COMPLETED WITH JUDGE ERRORS"
        if not args.skip_llm_judge and judge_error_rate not in {None, 0, 0.0}
        else "SUCCESS"
    )
    print(f"\n[{completion_label}]")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Details: {csv_path}")
    print(f"Summary: {json_path}")


if __name__ == "__main__":
    main()
