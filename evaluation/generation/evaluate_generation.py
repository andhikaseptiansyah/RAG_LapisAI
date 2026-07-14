"""Evaluate generated answers against the official Nusantara Dynamics CSV.

The evaluator reports deterministic answer accuracy plus LLM-judge faithfulness
and answer relevance. The official CSV contains only answerable questions and
labels source documents, not source pages.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DIR = PROJECT_ROOT / "evaluation"
if str(EVALUATION_DIR) not in sys.path:
    sys.path.insert(0, str(EVALUATION_DIR))

from evaluate_retrieval import load_ground_truth as load_official_ground_truth  # noqa: E402

LLM_BASE_URL = os.getenv("EVAL_LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("EVAL_LLM_API_KEY", "ollama")
LLM_MODEL = os.getenv("EVAL_LLM_MODEL", "qwen3-custom:latest")


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

    # The official CSV only labels source_document. When expected pages are
    # blank, compare at document level so a retrieved page number does not turn
    # a correct document into a false miss.
    document_only = all(not page for _, page in expected)
    if document_only:
        expected_units = {document for document, _ in expected}
        retrieved_units = {document for document, _ in retrieved}
        cited_units = {document for document, _ in cited}
    else:
        expected_units = expected
        retrieved_units = retrieved
        cited_units = cited

    recall_ratio = len(expected_units & retrieved_units) / len(expected_units)
    precision_ratio = len(expected_units & retrieved_units) / max(len(retrieved_units), 1)
    citation_ratio = len(expected_units & cited_units) / len(expected_units)

    recall = score_ratio(recall_ratio)
    precision = score_ratio(precision_ratio)
    if cited_units == expected_units:
        citation = 5.0
    elif citation_ratio >= 0.70:
        citation = 4.0
    elif citation_ratio > 0:
        citation = 3.0
    else:
        citation = 1.0

    return precision, recall, citation


def normalize_answer(text: str) -> str:
    value = str(text or "").casefold()
    value = value.replace("wib", " wib ")
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
    expected_answer: str,
    context: str,
    answer: str,
) -> dict[str, Any]:
    prompt = f"""
You are an independent evaluator for a Retrieval-Augmented Generation system.

QUESTION:
{question}

EXPECTED ANSWER:
{expected_answer}

RETRIEVED CONTEXT:
{context or '[EMPTY CONTEXT]'}

SYSTEM ANSWER:
{answer}

Score:
1. faithfulness (1-5): every factual claim must be supported by retrieved context.
2. answer_relevance (1-5): the answer must directly and correctly answer the question compared with the expected answer.
3. is_hallucination: true when the answer contains a specific factual claim unsupported by context.

Return JSON only:
{{
  "faithfulness": 1,
  "answer_relevance": 1,
  "is_hallucination": false,
  "reason": "maximum 25 words"
}}
"""

    try:
        from openai import OpenAI

        client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
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
    return round(sum(values) / len(values), 4) if values else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=EVALUATION_DIR / "ground_truth_qa.csv",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parent / "input_answers_official.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "results",
    )
    parser.add_argument("--output-prefix", default="official")
    args = parser.parse_args()

    dataset, gt_items = load_official_ground_truth(args.ground_truth.resolve())
    ground_truth = {str(item["id"]): item for item in gt_items}
    answers = json.loads(args.input.read_text(encoding="utf-8"))

    rows: list[dict[str, Any]] = []
    context_precision: list[float] = []
    context_recall: list[float] = []
    citation_accuracy: list[float] = []
    faithfulness: list[float] = []
    relevance: list[float] = []
    exact_matches: list[float] = []
    token_f1_values: list[float] = []
    hallucinations = 0
    false_refusals = 0

    print(f"Generation evaluation dataset: {dataset.get('dataset_name')}")
    print(f"LLM judge: {LLM_MODEL}")

    for index, item in enumerate(answers, start=1):
        qid = str(item.get("id") or "")
        if qid not in ground_truth:
            continue
        gt = ground_truth[qid]
        print(f"[{index}/{len(answers)}] {qid}")

        generated_answer = str(item.get("generated_answer") or "")
        expected_answer = str(gt.get("expected_answer") or "")
        is_abstention = detect_abstention(generated_answer)
        false_refusals += int(is_abstention)

        precision, recall, citation = metadata_metrics(
            item.get("retrieved_sources") or [],
            gt.get("references") or [],
            item.get("citation") or [],
        )
        context_precision.append(precision)
        context_recall.append(recall)
        citation_accuracy.append(citation)

        em = exact_match(expected_answer, generated_answer)
        f1 = token_f1(expected_answer, generated_answer)
        exact_matches.append(em)
        token_f1_values.append(f1)

        semantic = llm_judge(
            question=str(item.get("question") or gt.get("question") or ""),
            expected_answer=expected_answer,
            context=str(item.get("retrieved_context") or ""),
            answer=generated_answer,
        )
        faithfulness.append(semantic["faithfulness"])
        relevance.append(semantic["answer_relevance"])
        hallucinations += int(semantic["is_hallucination"])

        rows.append(
            {
                "ID": qid,
                "Question": gt.get("question"),
                "Expected Answer": expected_answer,
                "Generated Answer": generated_answer,
                "Expected Source": " | ".join(
                    str(reference.get("document") or "")
                    for reference in gt.get("references") or []
                ),
                "Abstained": is_abstention,
                "Normalized Exact Match": round(em, 4),
                "Token F1": round(f1, 4),
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
    summary = {
        "project": "LapisAI Enterprise Knowledge Assistant",
        "dataset": dataset.get("dataset_name"),
        "ground_truth": str(args.ground_truth.resolve()),
        "evaluation": "Official 30-question Generation Quality Evaluation",
        "total_questions": n,
        "question_counts": {
            "answerable": n,
            "unanswerable": 0,
        },
        "metrics": {
            "normalized_exact_match": mean(exact_matches),
            "token_f1": mean(token_f1_values),
            "faithfulness_1_to_5": mean(faithfulness),
            "answer_relevance_1_to_5": mean(relevance),
            "context_precision_1_to_5": mean(context_precision),
            "context_recall_1_to_5": mean(context_recall),
            "citation_accuracy_1_to_5": mean(citation_accuracy),
            "hallucination_rate": round(hallucinations / n, 4),
            "false_refusal_rate": round(false_refusals / n, 4),
            "unanswerable_safety_rate": None,
        },
        "notes": [
            "The official CSV contains only answerable questions.",
            "Source accuracy is evaluated at document level because the CSV has no page labels.",
            "Faithfulness and answer relevance use the configured deterministic LLM judge.",
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / f"generation_results_{args.output_prefix}.csv"
    json_path = args.output_dir / f"generation_summary_{args.output_prefix}.json"

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
