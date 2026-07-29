"""Combine Ollama, Gemini, and Groq evaluation summaries."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

METRICS = (
    "normalized_exact_match",
    "token_f1",
    "keyword_coverage",
    "faithfulness_1_to_5",
    "answer_relevance_1_to_5",
    "context_precision",
    "context_recall",
    "citation_accuracy",
    "precision_at_k",
    "recall_at_k",
    "hit_at_k",
    "mrr",
    "retrieval_debug_coverage",
    "average_retrieval_time_ms",
    "false_refusal_rate",
    "unanswerable_safety_rate",
    "unanswerable_no_citation_rate",
    "unanswerable_no_result_rate",
    "hallucination_rate",
    "generation_failure_rate",
    "average_response_time_ms",
    "p95_response_time_ms",
)


def load_summaries(paths: list[Path]) -> list[dict[str, Any]]:
    summaries = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    models = [str(item.get("model") or "") for item in summaries]
    if len(models) != len(set(models)):
        raise ValueError(f"Duplicate model summaries: {models}")
    return summaries


def _mean_available(*values: Any) -> float | None:
    valid: list[float] = []
    for value in values:
        try:
            if value is not None:
                valid.append(float(value))
        except (TypeError, ValueError):
            continue
    return sum(valid) / len(valid) if valid else None


def _inverse_rate(value: Any) -> float | None:
    try:
        return max(0.0, min(1.0, 1.0 - float(value)))
    except (TypeError, ValueError):
        return None


def _scale_five(value: Any) -> float | None:
    try:
        return max(0.0, min(1.0, float(value) / 5.0))
    except (TypeError, ValueError):
        return None


def derived_scores(metrics: dict[str, Any]) -> dict[str, float | None]:
    answer = _mean_available(
        metrics.get("token_f1"),
        metrics.get("keyword_coverage"),
        _scale_five(metrics.get("answer_relevance_1_to_5")),
    )
    grounding = _mean_available(
        _scale_five(metrics.get("faithfulness_1_to_5")),
        metrics.get("citation_accuracy"),
        _inverse_rate(metrics.get("hallucination_rate")),
    )
    retrieval = _mean_available(
        metrics.get("recall_at_k"),
        metrics.get("hit_at_k"),
        metrics.get("mrr"),
    )
    safety = _mean_available(
        _inverse_rate(metrics.get("false_refusal_rate")),
        metrics.get("unanswerable_safety_rate"),
        _inverse_rate(metrics.get("generation_failure_rate")),
    )
    components = {
        "answer_quality_score": answer,
        "grounding_score": grounding,
        "retrieval_score": retrieval,
        "safety_score": safety,
    }
    weighted = [
        (answer, 0.35),
        (grounding, 0.30),
        (retrieval, 0.20),
        (safety, 0.15),
    ]
    valid = [(value, weight) for value, weight in weighted if value is not None]
    overall = (sum(value * weight for value, weight in valid) / sum(weight for _, weight in valid)) if valid else None
    return {
        **{key: round(value * 100, 2) if value is not None else None for key, value in components.items()},
        "overall_score": round(overall * 100, 2) if overall is not None else None,
    }


def bilingual_macro_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    by_language = summary.get("by_language", {})
    english = by_language.get("EN", {}) or {}
    indonesian = by_language.get("ID", {}) or {}
    macro: dict[str, Any] = {
        "total_questions": int(english.get("total_questions") or 0) + int(indonesian.get("total_questions") or 0),
        "answerable_questions": int(english.get("answerable_questions") or 0) + int(indonesian.get("answerable_questions") or 0),
        "unanswerable_questions": int(english.get("unanswerable_questions") or 0) + int(indonesian.get("unanswerable_questions") or 0),
    }
    for metric in METRICS:
        macro[metric] = _mean_available(english.get(metric), indonesian.get(metric))
    return macro


def flatten_summary(summary: dict[str, Any], scope: str, metrics: dict[str, Any]) -> dict[str, Any]:
    row = {
        "Model": summary.get("model"),
        "Model Name": summary.get("model_name"),
        "Scope": scope,
        "Total Questions": metrics.get("total_questions"),
        "Answerable": metrics.get("answerable_questions"),
        "Unanswerable": metrics.get("unanswerable_questions"),
    }
    for metric in METRICS:
        row[metric] = metrics.get(metric)
    row.update(derived_scores(metrics))
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    summaries = load_summaries([path.resolve() for path in args.summary])
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        rows.append(flatten_summary(summary, "ALL", summary["overall"]))
        for language in ("EN", "ID"):
            rows.append(
                flatten_summary(
                    summary,
                    language,
                    summary.get("by_language", {}).get(language, {}),
                )
            )
        rows.append(flatten_summary(summary, "MACRO", bilingual_macro_metrics(summary)))

    # Verify fairness: each question should have the same retrieval-context
    # fingerprint across the three model runs. Empty contexts on unanswerable
    # items are expected and still hash identically.
    fingerprints: dict[str, dict[str, str]] = defaultdict(dict)
    details_files: list[Path] = []
    for summary_path, summary in zip(args.summary, summaries):
        model = str(summary.get("model") or "")
        details_path = summary_path.parent / f"generation_results_{summary_path.stem.removeprefix('generation_summary_')}.csv"
        if details_path.exists():
            details_files.append(details_path)
            with details_path.open(encoding="utf-8-sig", newline="") as file:
                for row in csv.DictReader(file):
                    fingerprints[row["ID"]][model] = row.get("Context Fingerprint", "")

    mismatches = {
        qid: values
        for qid, values in fingerprints.items()
        if len(values) == len(summaries) and len(set(values.values())) > 1
    }

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "comparison_3_models.csv"
    json_path = output_dir / "comparison_3_models.json"
    md_path = output_dir / "comparison_3_models.md"

    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "models": [summary.get("model") for summary in summaries],
        "rows": rows,
        "retrieval_context_consistency": {
            "questions_checked": len(fingerprints),
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
        },
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    overall = [row for row in rows if row["Scope"] == "MACRO"] or [row for row in rows if row["Scope"] == "ALL"]
    headers = [
        "Model", "Model Name", "Overall", "Answer", "Grounding", "Retrieval", "Safety",
        "P@K", "R@K", "Hit@K", "MRR", "Token F1", "Faithfulness", "Citation",
        "Hallucination", "Avg ms",
    ]
    table_rows = []
    for row in overall:
        table_rows.append([
            row["Model"], row.get("Model Name"), row.get("overall_score"),
            row.get("answer_quality_score"), row.get("grounding_score"),
            row.get("retrieval_score"), row.get("safety_score"),
            row.get("precision_at_k"), row.get("recall_at_k"), row.get("hit_at_k"),
            row.get("mrr"), row.get("token_f1"), row.get("faithfulness_1_to_5"),
            row.get("citation_accuracy"), row.get("hallucination_rate"),
            row.get("average_response_time_ms"),
        ])
    lines = [
        "# Comparison of 3 LLM Models (Bilingual Macro)",
        "",
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for table_row in table_rows:
        lines.append("| " + " | ".join(str(value) for value in table_row) + " |")
    lines.extend([
        "",
        "## Retrieval-context consistency",
        "",
        f"- Questions checked: {len(fingerprints)}",
        f"- Context mismatches across models: {len(mismatches)}",
        "",
        "A zero mismatch count confirms that the three models were compared using identical retrieved evidence.",
        "",
        "## Composite score",
        "",
        "The primary comparison uses a bilingual macro average, so English and Indonesian receive equal weight despite different question counts.",
        "",
        "Overall score = 35% answer quality + 30% grounding + 20% retrieval + 15% safety. Latency is reported separately and does not increase the quality score.",
    ])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Comparison CSV : {csv_path}")
    print(f"Comparison JSON: {json_path}")
    print(f"Comparison MD  : {md_path}")
    print(f"Context mismatches: {len(mismatches)}")


if __name__ == "__main__":
    main()
