"""Combine Ollama, Gemini, and OpenAI evaluation summaries."""

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

    overall = [row for row in rows if row["Scope"] == "ALL"]
    headers = [
        "Model", "Model Name", "Token F1", "Keyword", "Faithfulness", "Relevance",
        "Citation", "False refusal", "Unanswerable safety", "Hallucination", "Failure rate", "Avg ms",
    ]
    table_rows = []
    for row in overall:
        table_rows.append([
            row["Model"], row.get("Model Name"), row.get("token_f1"), row.get("keyword_coverage"),
            row.get("faithfulness_1_to_5"), row.get("answer_relevance_1_to_5"),
            row.get("citation_accuracy"), row.get("false_refusal_rate"),
            row.get("unanswerable_safety_rate"), row.get("hallucination_rate"),
            row.get("generation_failure_rate"), row.get("average_response_time_ms"),
        ])
    lines = [
        "# Comparison of 3 LLM Models",
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
    ])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Comparison CSV : {csv_path}")
    print(f"Comparison JSON: {json_path}")
    print(f"Comparison MD  : {md_path}")
    print(f"Context mismatches: {len(mismatches)}")


if __name__ == "__main__":
    main()
