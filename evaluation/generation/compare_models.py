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
    "question_keyword_coverage",
    "question_answer_keyword_coverage",
    "faithfulness_1_to_5",
    "answer_relevance_1_to_5",
    "context_precision",
    "context_recall",
    "citation_precision",
    "citation_recall",
    "citation_f1",
    "citation_accuracy",
    "precision_at_k",
    "recall_at_k",
    "hit_at_k",
    "mrr",
    "top1_accuracy",
    "ndcg_at_k",
    "retrieval_debug_coverage",
    "average_retrieval_time_ms",
    "false_refusal_rate",
    "unanswerable_safety_rate",
    "unanswerable_no_citation_rate",
    "unanswerable_no_result_rate",
    "hallucination_rate",
    "pipeline_failure_rate",
    "retrieval_or_context_failure_rate",
    "answer_postprocessing_failure_rate",
    "generation_output_failure_rate",
    "generation_failure_rate",
    "average_response_time_ms",
    "median_response_time_ms",
    "p95_response_time_ms",
    "average_estimated_sequential_e2e_ms",
    "p95_estimated_sequential_e2e_ms",
)


def load_summaries(paths: list[Path]) -> list[dict[str, Any]]:
    summaries = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    models = [str(item.get("model") or "") for item in summaries]
    if len(models) != len(set(models)):
        raise ValueError(f"Duplicate model summaries: {models}")
    roles = {str(item.get("benchmark_role") or "development") for item in summaries}
    if len(roles) != 1:
        raise ValueError(f"Benchmark roles differ across summaries: {sorted(roles)}")
    judges = {str(item.get("judge_model") or "") for item in summaries}
    if len(judges) != 1:
        raise ValueError(f"Judge models differ across summaries: {sorted(judges)}")
    if any(
        item.get("judge_model") and item.get("judge_independent") is False
        for item in summaries
    ):
        raise ValueError("At least one summary was produced with a non-independent judge")

    dataset_signatures = []
    for item in summaries:
        files = (item.get("reproducibility") or {}).get("files") or []
        signature = tuple(sorted(
            (str(file.get("path") or ""), str(file.get("sha256") or ""))
            for file in files
            if "/datasets/" in f"/{str(file.get('path') or '')}"
        ))
        if signature:
            dataset_signatures.append(signature)
    if dataset_signatures and len(set(dataset_signatures)) != 1:
        raise ValueError("Ground-truth dataset hashes differ across summaries")
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


def derived_scores(metrics: dict[str, Any]) -> dict[str, Any]:
    citation_f1 = (
        metrics.get("citation_f1")
        if metrics.get("citation_f1") is not None
        else metrics.get("citation_accuracy")
    )
    answer = _mean_available(
        metrics.get("token_f1"),
        metrics.get("keyword_coverage"),
        _scale_five(metrics.get("answer_relevance_1_to_5")),
    )
    grounding = _mean_available(
        _scale_five(metrics.get("faithfulness_1_to_5")),
        citation_f1,
        _inverse_rate(metrics.get("hallucination_rate")),
    )
    retrieval = _mean_available(
        metrics.get("recall_at_k"),
        metrics.get("mrr"),
        (
            metrics.get("ndcg_at_k")
            if metrics.get("ndcg_at_k") is not None
            else metrics.get("hit_at_k")
        ),
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
    deterministic_answer = _mean_available(
        metrics.get("token_f1"),
        metrics.get("keyword_coverage"),
    )
    deterministic_grounding = _mean_available(citation_f1)
    deterministic_weighted = [
        (deterministic_answer, 0.35),
        (deterministic_grounding, 0.30),
        (retrieval, 0.20),
        (safety, 0.15),
    ]
    deterministic_valid = [
        (value, weight)
        for value, weight in deterministic_weighted
        if value is not None
    ]
    deterministic_score = (
        sum(value * weight for value, weight in deterministic_valid)
        / sum(weight for _, weight in deterministic_valid)
        if deterministic_valid
        else None
    )

    required_metrics = {
        "answer_relevance_1_to_5": metrics.get("answer_relevance_1_to_5"),
        "faithfulness_1_to_5": metrics.get("faithfulness_1_to_5"),
        "hallucination_rate": metrics.get("hallucination_rate"),
    }
    missing_metrics = [
        name
        for name, value in required_metrics.items()
        if value is None
    ]
    overall = (
        sum(value * weight for value, weight in valid)
        / sum(weight for _, weight in valid)
        if valid and not missing_metrics
        else None
    )
    return {
        **{key: round(value * 100, 2) if value is not None else None for key, value in components.items()},
        "overall_score": round(overall * 100, 2) if overall is not None else None,
        "deterministic_score": (
            round(deterministic_score * 100, 2)
            if deterministic_score is not None
            else None
        ),
        "score_status": (
            "COMPLETE"
            if not missing_metrics
            else "INCOMPLETE_MISSING_JUDGE"
        ),
        "missing_score_metrics": ", ".join(missing_metrics),
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
    language_pairing = summary.get("language_pairing", {}) or {}
    row = {
        "Model": summary.get("model"),
        "Model Name": summary.get("model_name"),
        "Scope": scope,
        "Total Questions": metrics.get("total_questions"),
        "Answerable": metrics.get("answerable_questions"),
        "Unanswerable": metrics.get("unanswerable_questions"),
        "Benchmark Role": summary.get("benchmark_role"),
        "Judge Model": summary.get("judge_model"),
        "Judge Independent": summary.get("judge_independent"),
        "Model Reference Mutable": (
            summary.get("reproducibility") or {}
        ).get("model_reference_mutable"),
        "Language Comparison Status": language_pairing.get("status"),
        "Paired Language IDs": language_pairing.get("paired_id_count"),
        "Equivalent Source Pairs": language_pairing.get(
            "same_expected_source_pair_count"
        ),
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

    consistency_applicable = len(summaries) > 1
    comparable_fingerprints = {
        qid: values
        for qid, values in fingerprints.items()
        if len(values) == len(summaries)
    }
    mismatches = (
        {
            qid: values
            for qid, values in comparable_fingerprints.items()
            if len(set(values.values())) > 1
        }
        if consistency_applicable
        else {}
    )
    questions_checked = (
        len(comparable_fingerprints)
        if consistency_applicable
        else 0
    )

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
            "status": "checked" if consistency_applicable else "not_applicable",
            "questions_checked": questions_checked,
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
        },
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    overall = [row for row in rows if row["Scope"] == "MACRO"] or [row for row in rows if row["Scope"] == "ALL"]
    model_count = len(summaries)
    headers = [
        "Model", "Model Name", "Overall", "Deterministic", "Answer", "Grounding", "Retrieval", "Safety",
        "Status", "P@K", "R@K", "Hit@K", "MRR", "NDCG@K", "Token F1", "Faithfulness", "Citation F1",
        "Hallucination", "Avg generation ms", "Estimated E2E ms",
    ]
    table_rows = []
    for row in overall:
        table_rows.append([
            row["Model"], row.get("Model Name"), row.get("overall_score"),
            row.get("deterministic_score"),
            row.get("answer_quality_score"), row.get("grounding_score"),
            row.get("retrieval_score"), row.get("safety_score"),
            row.get("score_status"),
            row.get("precision_at_k"), row.get("recall_at_k"), row.get("hit_at_k"),
            row.get("mrr"), row.get("ndcg_at_k"), row.get("token_f1"),
            row.get("faithfulness_1_to_5"),
            row.get("citation_f1") if row.get("citation_f1") is not None else row.get("citation_accuracy"),
            row.get("hallucination_rate"),
            row.get("average_response_time_ms"),
            row.get("average_estimated_sequential_e2e_ms"),
        ])
    lines = [
        f"# Comparison of {model_count} LLM Model{'s' if model_count != 1 else ''} (Bilingual Macro)",
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
        f"- Status: {'checked' if consistency_applicable else 'not applicable (only one model)'}",
        f"- Questions checked: {questions_checked}",
        f"- Context mismatches across models: {len(mismatches)}",
        "",
        "## Composite score",
        "",
        "The primary comparison uses a bilingual macro average, so English and Indonesian receive equal weight despite different question counts.",
        "",
        "Overall score = 35% answer quality + 30% grounding + 20% retrieval + 15% safety. Latency is reported separately and does not increase the quality score.",
        "",
        "If the LLM judge is skipped or fails, Overall is intentionally left empty and score_status is INCOMPLETE_MISSING_JUDGE; deterministic_score remains available for diagnostics.",
    ])
    pairing_statuses = {
        str(row.get("Language Comparison Status") or "")
        for row in overall
    }
    if "descriptive_only_unpaired_targets" in pairing_statuses:
        lines.extend([
            "",
            "## Language comparison",
            "",
            "English and Indonesian scores are descriptive by-language slices, not a controlled language-gap test, because the question sets do not use equivalent source targets.",
        ])
    if consistency_applicable:
        lines[lines.index("## Composite score"):lines.index("## Composite score")] = [
            (
                "A zero mismatch count confirms that the compared models used identical retrieved evidence."
                if not mismatches
                else "Context mismatches were found; model-level comparisons are not evidence-locked for every question."
            ),
            "",
        ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Comparison CSV : {csv_path}")
    print(f"Comparison JSON: {json_path}")
    print(f"Comparison MD  : {md_path}")
    print(f"Context mismatches: {len(mismatches)}")


if __name__ == "__main__":
    main()
