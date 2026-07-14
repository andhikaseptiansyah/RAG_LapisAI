"""Evaluate LapisAI generation quality with answerability-aware metrics."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

LLM_BASE_URL = os.getenv("EVAL_LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("EVAL_LLM_API_KEY", "ollama")
LLM_MODEL = os.getenv("EVAL_LLM_MODEL", "qwen3-custom:latest")

client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

ABSTENTION_PATTERNS = (
    "belum ketemu",
    "tidak ditemukan",
    "tidak disebutkan",
    "tidak dicantumkan",
    "tidak tersedia",
    "no reliable source",
    "not found",
    "not provided",
)


def normalize_document(name: Any) -> str:
    value = str(name or "").replace("\\", "/").split("/")[-1].lower().strip()
    value = re.sub(r"\.(pdf|txt|docx|doc)$", "", value)
    value = re.sub(r"[\s-]+", "_", value)
    return value


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


def source_set(items: list[Any]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for item in items or []:
        normalized = normalize_source(item)
        if normalized[0]:
            result.add(normalized)
    return result


def score_ratio(ratio: float) -> float:
    if ratio >= 0.90:
        return 5.0
    if ratio >= 0.70:
        return 4.0
    if ratio >= 0.50:
        return 3.0
    if ratio > 0:
        return 2.0
    return 1.0


def metadata_metrics(
    retrieved_sources: list[Any],
    expected_sources: list[Any],
    citations: list[Any],
) -> tuple[float, float, float]:
    expected = source_set(expected_sources)
    retrieved = source_set(retrieved_sources)
    cited = source_set(citations)

    if not expected:
        raise ValueError("metadata_metrics is only defined for answerable questions")

    recall = score_ratio(len(expected & retrieved) / len(expected))
    precision = score_ratio(len(expected & retrieved) / max(len(retrieved), 1))

    exact_citation_ratio = len(expected & cited) / len(expected)
    if cited == expected:
        citation = 5.0
    elif exact_citation_ratio >= 0.70:
        citation = 4.0
    elif exact_citation_ratio > 0:
        citation = 3.0
    elif {doc for doc, _ in expected} & {doc for doc, _ in cited}:
        citation = 2.0
    else:
        citation = 1.0

    return precision, recall, citation


def detect_abstention(answer: str) -> bool:
    text = str(answer or "").lower()
    return "confidence: 0%" in text or any(pattern in text for pattern in ABSTENTION_PATTERNS)


def clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 1.0
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
    answerable: bool,
    expected_answer: str,
    expected_keywords: list[str],
    context: str,
    answer: str,
) -> dict[str, Any]:
    prompt = f"""
Anda adalah evaluator independen untuk sistem Retrieval-Augmented Generation.

STATUS GROUND TRUTH:
- Answerable: {str(answerable).lower()}
- Expected answer: {expected_answer}
- Important keywords: {json.dumps(expected_keywords, ensure_ascii=False)}

PERTANYAAN:
{question}

RETRIEVED CONTEXT:
{context or '[EMPTY CONTEXT]'}

SYSTEM ANSWER:
{answer}

Rubrik:
1. faithfulness (1-5): semua klaim faktual harus didukung retrieved context. Jawaban abstain yang tidak mengarang dapat tetap faithful.
2. answer_relevance (1-5): bandingkan langsung dengan expected answer. Untuk answerable=false, penolakan yang jelas dan tepat mendapat nilai tinggi.
3. is_hallucination: true jika ada klaim faktual spesifik yang tidak didukung context.

Kembalikan JSON saja:
{{
  "faithfulness": 1,
  "answer_relevance": 1,
  "is_hallucination": false,
  "reason": "maksimal 25 kata"
}}
"""

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": "Return a valid JSON object only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        result = parse_json_object(response.choices[0].message.content or "")
        return {
            "faithfulness": clamp_score(result.get("faithfulness", 1)),
            "answer_relevance": clamp_score(result.get("answer_relevance", 1)),
            "is_hallucination": bool(result.get("is_hallucination", True)),
            "reason": str(result.get("reason") or "")[:240],
        }
    except Exception as error:
        print(f"[ERROR JUDGE] {error}")
        return {
            "faithfulness": 1.0,
            "answer_relevance": 1.0,
            "is_hallucination": True,
            "reason": f"Judge error: {error}",
        }


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", type=Path, default=Path("generation_ground_truth.json"))
    parser.add_argument("--input", type=Path, default=Path("input_answers_after.json"))
    parser.add_argument("--output-prefix", default="after")
    args = parser.parse_args()

    gt_payload = json.loads(args.ground_truth.read_text(encoding="utf-8"))
    ground_truth = {str(item["id"]): item for item in gt_payload.get("items", [])}
    answers = json.loads(args.input.read_text(encoding="utf-8"))

    rows: list[dict[str, Any]] = []
    answerable_precision: list[float] = []
    answerable_recall: list[float] = []
    answerable_citation: list[float] = []
    faithfulness: list[float] = []
    relevance: list[float] = []
    hallucinations = 0
    answerability_correct = 0
    false_refusals = 0
    unsafe_answers = 0

    print(f"Mulai Evaluasi ({LLM_MODEL})")

    for index, item in enumerate(answers, start=1):
        qid = str(item.get("id") or "")
        if qid not in ground_truth:
            continue
        gt = ground_truth[qid]
        print(f"[{index}/{len(answers)}] {qid}")

        is_answerable = bool(gt.get("answerable", True))
        is_abstention = detect_abstention(str(item.get("generated_answer") or ""))
        is_answerability_correct = (is_answerable and not is_abstention) or (
            not is_answerable and is_abstention
        )
        answerability_correct += int(is_answerability_correct)
        false_refusals += int(is_answerable and is_abstention)
        unsafe_answers += int((not is_answerable) and (not is_abstention))

        precision: float | None = None
        recall: float | None = None
        citation: float | None = None
        if is_answerable:
            precision, recall, citation = metadata_metrics(
                item.get("retrieved_sources") or [],
                gt.get("references") or [],
                item.get("citation") or [],
            )
            answerable_precision.append(precision)
            answerable_recall.append(recall)
            answerable_citation.append(citation)

        semantic = llm_judge(
            question=str(item.get("question") or gt.get("question") or ""),
            answerable=is_answerable,
            expected_answer=str(gt.get("expected_answer") or ""),
            expected_keywords=list(gt.get("expected_answer_keywords") or []),
            context=str(item.get("retrieved_context") or ""),
            answer=str(item.get("generated_answer") or ""),
        )

        faithfulness.append(semantic["faithfulness"])
        relevance.append(semantic["answer_relevance"])
        hallucinations += int(semantic["is_hallucination"])

        rows.append(
            {
                "ID": qid,
                "Answerable": is_answerable,
                "Abstained": is_abstention,
                "Answerability Correct": is_answerability_correct,
                "Faithfulness": semantic["faithfulness"],
                "Answer Relevance": semantic["answer_relevance"],
                "Context Precision": precision,
                "Context Recall": recall,
                "Citation Accuracy": citation,
                "Hallucination": int(semantic["is_hallucination"]),
                "Judge Reason": semantic["reason"],
            }
        )

    if not rows:
        raise RuntimeError("No matching evaluation rows were found")

    n = len(rows)
    answerable_count = sum(bool(row["Answerable"]) for row in rows)
    unanswerable_count = n - answerable_count
    summary = {
        "project": "LapisAI Enterprise Knowledge Assistant",
        "evaluation": "Answerability-aware Generation Quality Evaluation",
        "total_questions": n,
        "question_counts": {
            "answerable": answerable_count,
            "unanswerable": unanswerable_count,
        },
        "metrics": {
            "faithfulness": mean(faithfulness),
            "answer_relevance": mean(relevance),
            "context_precision_answerable_only": mean(answerable_precision),
            "context_recall_answerable_only": mean(answerable_recall),
            "citation_accuracy_answerable_only": mean(answerable_citation),
            "hallucination_rate": round(hallucinations / n, 4),
            "answerability_accuracy": round(answerability_correct / n, 4),
            "false_refusal_rate_answerable": round(false_refusals / max(answerable_count, 1), 4),
            "unsafe_answer_rate_unanswerable": round(unsafe_answers / max(unanswerable_count, 1), 4),
        },
    }

    csv_path = Path(f"generation_results_{args.output_prefix}.csv")
    json_path = Path(f"generation_summary_{args.output_prefix}.json")

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n[SUKSES]")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()