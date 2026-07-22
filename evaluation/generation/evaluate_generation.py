"""Evaluate one model on the bilingual Project-1 RAG question set.

The evaluator supports answerable and unanswerable questions, reports metrics
for English, Indonesian, and the combined dataset, and can optionally use one
fixed LLM judge for faithfulness and answer relevance.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import statistics
import requests
from dotenv import load_dotenv
from collections import Counter
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
    EVALUATION_DIR / "datasets" / "qna_english_50.csv",
    EVALUATION_DIR / "datasets" / "qna_indonesia_50.csv",
]
LLM_BASE_URL = os.getenv("EVAL_LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("EVAL_LLM_API_KEY", "ollama")
LLM_MODEL = os.getenv("EVAL_LLM_MODEL", "qwen3-custom:latest")

ABSTENTION_PATTERNS = (
    # Indonesian
    "belum ketemu",
    "belum ditemukan",
    "tidak ditemukan",
    "tidak disebutkan",
    "tidak dicantumkan",
    "tidak tersedia",
    "tidak ada informasi",
    "tidak memiliki informasi",
    "tidak dapat ditemukan",
    "dokumen yang diindeks tidak",
    "dokumen tidak menyebutkan",
    "dokumen tidak menentukan",
    "informasi tersebut tidak tersedia",
    "saya tidak menemukan",
    # English
    "no reliable source",
    "not found",
    "not provided",
    "not specified",
    "not mentioned",
    "no information",
    "cannot find",
    "could not find",
    "indexed documents do not",
    "documents do not specify",
    "documents do not mention",
    "not available in the documents",
    "not available in the indexed documents",
    "not stated in the indexed documents",
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
        return {
            "context_precision": 1.0 if not retrieved else 0.0,
            "context_recall": None,
            "citation_accuracy": 1.0 if not cited else 0.0,
            "retrieval_no_result": 1.0 if not retrieved else 0.0,
        }

    document_only = bool(expected) and all(not page for _, page in expected)
    expected_units = _source_units(expected_sources, document_only)
    retrieved_units = _source_units(retrieved_sources, document_only)
    cited_units = _source_units(citations, document_only)
    if not expected_units:
        return {
            "context_precision": None,
            "context_recall": None,
            "citation_accuracy": None,
            "retrieval_no_result": 1.0 if not retrieved_units else 0.0,
        }

    intersection = expected_units & retrieved_units
    return {
        "context_precision": len(intersection) / max(len(retrieved_units), 1),
        "context_recall": len(intersection) / len(expected_units),
        "citation_accuracy": len(expected_units & cited_units) / len(expected_units),
        "retrieval_no_result": 1.0 if not retrieved_units else 0.0,
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
    value = value.replace("none resulting", "no resulting")
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


def keyword_coverage(keywords: list[str], question: str, generated: str) -> float | None:
    """Measure whether each annotated concept appears in the question-answer pair.

    Some CSV keywords repeat conditions already stated in the question (for
    example "probation" or "above IDR 50 million"). Requiring the answer to
    repeat those conditions would unfairly penalize concise correct answers, so
    the metric checks the complete question-answer pair.
    """
    if not keywords:
        return None
    combined_normalized = normalize_answer(f"{question} {generated}")
    combined_tokens = set(combined_normalized.split())
    hits = 0
    for keyword in keywords:
        normalized = normalize_answer(keyword)
        keyword_tokens = set(normalized.split())
        if normalized and (
            normalized in combined_normalized
            or (keyword_tokens and keyword_tokens.issubset(combined_tokens))
        ):
            hits += 1
    return hits / len(keywords)


def detect_abstention(answer: str) -> bool:
    text = str(answer or "").casefold()
    return "confidence: 0%" in text or any(pattern in text for pattern in ABSTENTION_PATTERNS)


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


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answerable_rows = [row for row in rows if row["Answerable"]]
    unanswerable_rows = [row for row in rows if not row["Answerable"]]
    judge_attempted = [
        row for row in rows
        if row["Judge Error"] not in {"SKIPPED", "GENERATION_FAILED"}
    ]
    judge_rows = [row for row in judge_attempted if not row["Judge Error"]]
    latencies = [row["Client Response Time (ms)"] for row in rows]

    return {
        "total_questions": len(rows),
        "answerable_questions": len(answerable_rows),
        "unanswerable_questions": len(unanswerable_rows),
        "normalized_exact_match": mean(row["Normalized Exact Match"] for row in answerable_rows),
        "token_f1": mean(row["Token F1"] for row in answerable_rows),
        "keyword_coverage": mean(row["Keyword Coverage"] for row in answerable_rows),
        "faithfulness_1_to_5": mean(row["Faithfulness"] for row in judge_rows),
        "answer_relevance_1_to_5": mean(row["Answer Relevance"] for row in judge_rows),
        "context_precision": mean(row["Context Precision"] for row in answerable_rows),
        "context_recall": mean(row["Context Recall"] for row in answerable_rows),
        "citation_accuracy": mean(row["Citation Accuracy"] for row in answerable_rows),
        "false_refusal_rate": mean(row["False Refusal"] for row in answerable_rows),
        "unanswerable_safety_rate": mean(row["Correct Unanswerable Refusal"] for row in unanswerable_rows),
        "unanswerable_no_citation_rate": mean(row["No Citation On Unanswerable"] for row in unanswerable_rows),
        "unanswerable_no_result_rate": mean(row["Retrieval No Result"] for row in unanswerable_rows),
        "hallucination_rate": mean(row["Hallucination"] for row in judge_rows),
        "generation_failure_rate": mean(row["Generation Failed"] for row in rows),
        "judge_error_rate": (
            round(1 - (len(judge_rows) / len(judge_attempted)), 4)
            if judge_attempted
            else None
        ),
        "average_response_time_ms": mean(latencies),
        "median_response_time_ms": round(statistics.median(latencies), 2) if latencies else None,
        "p95_response_time_ms": percentile(latencies, 0.95),
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
        expected_answer = str(gt.get("expected_answer") or "")
        answerable = bool(gt.get("answerable"))
        abstained = detect_abstention(generated_answer)
        metadata = source_metrics(
            item.get("retrieved_sources") or [],
            gt.get("references") or [],
            item.get("citation") or [],
            answerable=answerable,
        )
        em = exact_match(expected_answer, generated_answer) if answerable else None
        f1 = token_f1(expected_answer, generated_answer) if answerable else None
        keywords = list(gt.get("expected_answer_keywords") or [])
        coverage = (
            keyword_coverage(keywords, str(gt.get("question") or ""), generated_answer)
            if answerable
            else None
        )

        if generation_failed:
            semantic = {
                "faithfulness": None,
                "answer_relevance": None,
                "is_hallucination": None,
                "reason": str(item.get("generation_error") or "Generation failed"),
                "judge_error": "GENERATION_FAILED",
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
        correct_unanswerable = int((not answerable) and abstained and not citations)
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
            "Generation Failed": int(generation_failed),
            "Generation Error": str(item.get("generation_error") or ""),
            "Abstained": int(abstained),
            "False Refusal": int(answerable and (abstained or generation_failed)),
            "Correct Unanswerable Refusal": correct_unanswerable,
            "No Citation On Unanswerable": int((not answerable) and not citations),
            "Normalized Exact Match": round(em, 4) if em is not None else None,
            "Token F1": round(f1, 4) if f1 is not None else None,
            "Keyword Coverage": round(coverage, 4) if coverage is not None else None,
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
            "Client Response Time (ms)": float(item.get("client_response_time_ms") or 0),
            "Context Fingerprint": item.get("context_fingerprint"),
        }
        rows.append(row)

    if not rows:
        raise RuntimeError("No matching evaluation rows were found")

    summary = {
        "project": "LapisAI Enterprise Knowledge Assistant (RAG)",
        "evaluation": "Bilingual 3-model generation evaluation",
        "model": model,
        "model_name": model_name,
        "judge_model": None if args.skip_llm_judge else LLM_MODEL,
        "ground_truth_files": [str(path.resolve()) for path in datasets],
        "dataset": dataset_summary(gt_items),
        "overall": summarize_rows(rows),
        "by_language": {
            language: summarize_rows([row for row in rows if row["Language"] == language])
            for language in ("EN", "ID")
        },
        "notes": [
            "All answerable source metrics are evaluated at document level because the CSV has no page labels.",
            "Unanswerable safety requires a refusal and no citation.",
            "The same configured judge model must be used for all three evaluated models.",
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
