"""Combine Ollama, Gemini, and Groq evaluation summaries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]

METRICS = (
    "normalized_exact_match",
    "token_f1",
    "keyword_coverage",
    "question_keyword_coverage",
    "question_answer_keyword_coverage",
    "faithfulness_1_to_5",
    "answer_relevance_1_to_5",
    "judge_eligible_questions",
    "judge_attempted_questions",
    "judge_successful_questions",
    "judge_coverage",
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
    "retrieval_latency_coverage",
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
    "client_latency_coverage",
    "average_estimated_sequential_e2e_ms",
    "p95_estimated_sequential_e2e_ms",
    "estimated_e2e_latency_coverage",
)

SUM_METRICS = {
    "judge_eligible_questions",
    "judge_attempted_questions",
    "judge_successful_questions",
}


def _portable_dataset_path(value: Any) -> str | None:
    normalized = str(value or "").replace("\\", "/").strip()
    lowered = normalized.casefold()
    marker = "/evaluation/datasets/"
    padded = "/" + normalized.lstrip("/")
    padded_lower = padded.casefold()
    if marker in padded_lower:
        start = padded_lower.index(marker) + 1
        return padded[start:]
    if lowered.startswith("evaluation/datasets/"):
        return normalized
    return None


def dataset_signature(summary: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Return a platform-independent ground-truth file signature."""
    files = (summary.get("reproducibility") or {}).get("files") or []
    signature: list[tuple[str, str]] = []
    for file in files:
        portable_path = _portable_dataset_path(file.get("path"))
        digest = str(file.get("sha256") or "").strip().casefold()
        if portable_path and digest:
            signature.append((portable_path.casefold(), digest))
    return tuple(sorted(signature))


def comparison_output_stem(model_count: int) -> str:
    suffix = "model" if model_count == 1 else "models"
    return f"comparison_{model_count}_{suffix}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_manifest_file(value: Any) -> Path | None:
    normalized = str(value or "").replace("\\", "/").strip()
    if not normalized:
        return None

    direct = Path(normalized)
    if direct.is_absolute() and direct.exists():
        return direct

    lowered = normalized.casefold()
    for marker in ("evaluation/", "backend/"):
        index = lowered.find(marker)
        if index >= 0:
            candidate = PROJECT_ROOT / normalized[index:]
            return candidate
    return PROJECT_ROOT / normalized


def verify_artifact_manifest(summary: dict[str, Any]) -> dict[str, Any]:
    """Verify that files on disk still match the summary's recorded inputs."""
    files = (summary.get("reproducibility") or {}).get("files") or []
    if not files:
        return {
            "status": "missing_manifest",
            "checked_files": 0,
            "missing_files": [],
            "mismatched_files": [],
        }

    missing_files: list[str] = []
    mismatched_files: list[dict[str, Any]] = []
    checked_files = 0
    for item in files:
        recorded_path = str(item.get("path") or "")
        path = _resolve_manifest_file(recorded_path)
        if path is None or not path.is_file():
            missing_files.append(recorded_path)
            continue
        checked_files += 1
        expected_hash = str(item.get("sha256") or "").strip().casefold()
        expected_bytes = item.get("bytes")
        actual_hash = _sha256_file(path)
        actual_bytes = path.stat().st_size
        if (
            not expected_hash
            or actual_hash != expected_hash
            or expected_bytes is None
            or actual_bytes != int(expected_bytes)
        ):
            mismatched_files.append({
                "path": recorded_path,
                "expected_sha256": expected_hash or None,
                "actual_sha256": actual_hash,
                "expected_bytes": expected_bytes,
                "actual_bytes": actual_bytes,
            })

    return {
        "status": (
            "verified"
            if not missing_files and not mismatched_files
            else "failed"
        ),
        "checked_files": checked_files,
        "missing_files": missing_files,
        "mismatched_files": mismatched_files,
    }


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

    dataset_signatures = [dataset_signature(item) for item in summaries]
    if len(summaries) > 1 and any(not signature for signature in dataset_signatures):
        raise ValueError(
            "At least one summary is missing ground-truth dataset hashes; "
            "a fair cross-model comparison cannot be verified."
        )
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
    judge_coverage = metrics.get("judge_coverage")
    incomplete_judge_coverage = False
    try:
        incomplete_judge_coverage = (
            judge_coverage is not None and float(judge_coverage) < 1.0
        )
    except (TypeError, ValueError):
        incomplete_judge_coverage = True
    if incomplete_judge_coverage:
        missing_metrics.append("judge_coverage<1.0")
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
            if any(required_metrics[name] is None for name in required_metrics)
            else "INCOMPLETE_JUDGE_COVERAGE"
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
        values = (english.get(metric), indonesian.get(metric))
        if metric in SUM_METRICS:
            available = [float(value) for value in values if value is not None]
            macro[metric] = sum(available) if available else None
        else:
            macro[metric] = _mean_available(*values)
    return macro


def flatten_summary(summary: dict[str, Any], scope: str, metrics: dict[str, Any]) -> dict[str, Any]:
    language_pairing = summary.get("language_pairing", {}) or {}
    evaluation_status = summary.get("evaluation_status", {}) or {}
    row = {
        "Model": summary.get("model"),
        "Model Name": summary.get("model_name"),
        "Scope": scope,
        "Total Questions": metrics.get("total_questions"),
        "Answerable": metrics.get("answerable_questions"),
        "Unanswerable": metrics.get("unanswerable_questions"),
        "Benchmark Role": summary.get("benchmark_role"),
        "Evaluation Status": evaluation_status.get("status") or "UNKNOWN",
        "Final Eligible": evaluation_status.get("final_eligible"),
        "Evaluation Blockers": " | ".join(
            str(item) for item in evaluation_status.get("blockers") or []
        ),
        "Evaluation Warnings": " | ".join(
            str(item) for item in evaluation_status.get("warnings") or []
        ),
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


def load_benchmark_audit(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Benchmark audit must contain one JSON object")
    return payload


def _inferred_summary_blockers(summary: dict[str, Any]) -> list[str]:
    explicit = (summary.get("evaluation_status") or {}).get("blockers") or []
    if explicit:
        return [str(item) for item in explicit]

    blockers: list[str] = []
    overall = summary.get("overall") or {}
    if str(summary.get("benchmark_role") or "development") != "holdout":
        blockers.append("Benchmark is not a blind holdout.")
    required_judge_metrics = (
        overall.get("faithfulness_1_to_5"),
        overall.get("answer_relevance_1_to_5"),
        overall.get("hallucination_rate"),
    )
    if any(value is None for value in required_judge_metrics):
        blockers.append("Independent LLM-judge metrics are incomplete.")
    coverage = overall.get("judge_coverage")
    if coverage is not None:
        try:
            if float(coverage) < 1.0:
                blockers.append("Independent LLM-judge coverage is below 100%.")
        except (TypeError, ValueError):
            blockers.append("Independent LLM-judge coverage is invalid.")
    if (summary.get("reproducibility") or {}).get("model_reference_mutable"):
        blockers.append("The evaluated model reference is mutable.")
    if summary.get("judge_model") and summary.get("judge_independent") is not True:
        blockers.append("The LLM judge is not independent.")
    return blockers


def comparison_quality(
    summaries: list[dict[str, Any]],
    *,
    benchmark_audit: dict[str, Any] | None,
    artifact_integrity: dict[str, dict[str, Any]],
    consistency_status: str,
    mismatch_count: int,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    for summary in summaries:
        model = str(summary.get("model") or "unknown")
        blockers.extend(
            f"{model}: {message}"
            for message in _inferred_summary_blockers(summary)
        )
        integrity = artifact_integrity.get(model) or {}
        if integrity.get("status") != "verified":
            blockers.append(
                f"{model}: recorded evaluation inputs are missing or no longer match their manifest hashes."
            )

    if benchmark_audit is None:
        warnings.append(
            "No benchmark-leakage audit was attached to the comparison."
        )
    else:
        audit_role = str(benchmark_audit.get("benchmark_role") or "")
        summary_roles = {
            str(summary.get("benchmark_role") or "development")
            for summary in summaries
        }
        if audit_role and audit_role not in summary_roles:
            blockers.append(
                "Benchmark-audit role does not match the evaluated summaries."
            )
        overlap_count = int(
            benchmark_audit.get("overlap_item_count")
            or len({
                str(finding.get("id") or "")
                for finding in benchmark_audit.get("findings") or []
                if finding.get("id")
            })
        )
        if overlap_count:
            blockers.append(
                f"Benchmark leakage audit found exact overlap in {overlap_count} item(s)."
            )

    if len(summaries) == 1:
        warnings.append(
            "Only one model was evaluated; this is a model diagnostic, not a comparative ranking."
        )
    if len(summaries) > 1 and consistency_status != "checked":
        blockers.append(
            "Retrieval-context consistency could not be verified for every model and question."
        )
    if mismatch_count:
        blockers.append(
            f"Retrieved generation context differs on {mismatch_count} question(s)."
        )

    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    return {
        "status": "FINAL_ELIGIBLE" if not blockers else "DIAGNOSTIC_ONLY",
        "final_eligible": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--benchmark-audit", type=Path)
    parser.add_argument(
        "--output-stem",
        help="Optional filename stem; defaults to comparison_<N>_model(s).",
    )
    parser.add_argument(
        "--require-final-report",
        action="store_true",
        help="Exit non-zero when quality gates classify the report as diagnostic only.",
    )
    args = parser.parse_args()

    summaries = load_summaries([path.resolve() for path in args.summary])
    benchmark_audit = load_benchmark_audit(args.benchmark_audit)
    artifact_integrity = {
        str(summary.get("model") or "unknown"): verify_artifact_manifest(summary)
        for summary in summaries
    }
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
    question_ids_by_model: dict[str, set[str]] = {}
    for summary_path, summary in zip(args.summary, summaries):
        model = str(summary.get("model") or "")
        details_path = summary_path.parent / f"generation_results_{summary_path.stem.removeprefix('generation_summary_')}.csv"
        if details_path.exists():
            details_files.append(details_path)
            question_ids_by_model[model] = set()
            with details_path.open(encoding="utf-8-sig", newline="") as file:
                for row in csv.DictReader(file):
                    qid = str(row.get("ID") or "").strip()
                    if not qid:
                        continue
                    question_ids_by_model[model].add(qid)
                    fingerprints[qid][model] = row.get("Context Fingerprint", "")

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
    expected_question_counts = {
        str(summary.get("model") or ""): int(
            (summary.get("overall") or {}).get("total_questions") or 0
        )
        for summary in summaries
    }
    missing_details_models = sorted(
        set(expected_question_counts) - set(question_ids_by_model)
    )
    incomplete_detail_models = sorted(
        model
        for model, expected_count in expected_question_counts.items()
        if model in question_ids_by_model
        and len(question_ids_by_model[model]) != expected_count
    )
    expected_questions = max(expected_question_counts.values(), default=0)
    if not consistency_applicable:
        consistency_status = "not_applicable"
    elif (
        missing_details_models
        or incomplete_detail_models
        or questions_checked != expected_questions
    ):
        consistency_status = "incomplete"
    elif mismatches:
        consistency_status = "mismatch"
    else:
        consistency_status = "checked"

    quality = comparison_quality(
        summaries,
        benchmark_audit=benchmark_audit,
        artifact_integrity=artifact_integrity,
        consistency_status=consistency_status,
        mismatch_count=len(mismatches),
    )
    overlap_count = (
        int(
            benchmark_audit.get("overlap_item_count")
            or len({
                str(finding.get("id") or "")
                for finding in benchmark_audit.get("findings") or []
                if finding.get("id")
            })
        )
        if benchmark_audit
        else None
    )
    for row in rows:
        row["Report Status"] = quality["status"]
        row["Report Final Eligible"] = quality["final_eligible"]
        row["Benchmark Overlap Count"] = overlap_count
        row["Artifact Integrity"] = (
            artifact_integrity.get(str(row.get("Model") or ""), {}).get("status")
        )

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_stem = args.output_stem or comparison_output_stem(len(summaries))
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", output_stem):
        raise ValueError("--output-stem may contain only letters, digits, dot, dash, and underscore")
    csv_path = output_dir / f"{output_stem}.csv"
    json_path = output_dir / f"{output_stem}.json"
    md_path = output_dir / f"{output_stem}.md"

    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "report_schema_version": 2,
        "models": [summary.get("model") for summary in summaries],
        "report_quality": quality,
        "artifact_integrity": artifact_integrity,
        "benchmark_audit": ({
            "status": benchmark_audit.get("status"),
            "benchmark_role": benchmark_audit.get("benchmark_role"),
            "final_eligible": benchmark_audit.get("final_eligible"),
            "overlap_item_count": benchmark_audit.get("overlap_item_count"),
            "question_overlap_count": benchmark_audit.get("question_overlap_count"),
            "expected_answer_overlap_count": benchmark_audit.get("expected_answer_overlap_count"),
            "production_overlap_count": benchmark_audit.get("production_overlap_count"),
            "test_overlap_count": benchmark_audit.get("test_overlap_count"),
        } if benchmark_audit else None),
        "rows": rows,
        "retrieval_context_consistency": {
            "status": consistency_status,
            "questions_checked": questions_checked,
            "expected_questions": expected_questions if consistency_applicable else 0,
            "question_counts_by_model": {
                model: len(ids) for model, ids in question_ids_by_model.items()
            },
            "missing_details_models": missing_details_models,
            "incomplete_details_models": incomplete_detail_models,
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
        },
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    overall = [row for row in rows if row["Scope"] == "MACRO"] or [row for row in rows if row["Scope"] == "ALL"]
    model_count = len(summaries)
    headers = [
        "Model", "Model Name", "Overall", "Deterministic", "Answer", "Grounding", "Retrieval", "Safety",
        "Score Status", "Judge Coverage", "P@K", "R@K", "Hit@K", "MRR", "NDCG@K", "Token F1", "Faithfulness", "Citation F1",
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
            row.get("judge_coverage"),
            row.get("precision_at_k"), row.get("recall_at_k"), row.get("hit_at_k"),
            row.get("mrr"), row.get("ndcg_at_k"), row.get("token_f1"),
            row.get("faithfulness_1_to_5"),
            row.get("citation_f1") if row.get("citation_f1") is not None else row.get("citation_accuracy"),
            row.get("hallucination_rate"),
            row.get("average_response_time_ms"),
            row.get("average_estimated_sequential_e2e_ms"),
        ])
    title = (
        "# Evaluation of 1 LLM Model (Bilingual Macro)"
        if model_count == 1
        else f"# Comparison of {model_count} LLM Models (Bilingual Macro)"
    )
    lines = [
        title,
        "",
        f"> Report status: **{quality['status']}**",
        "",
        "## Quality gate",
        "",
    ]
    if quality["blockers"]:
        lines.append("Final-use blockers:")
        lines.extend(f"- {message}" for message in quality["blockers"])
    else:
        lines.append("- All final-report quality gates passed.")
    if quality["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {message}" for message in quality["warnings"])
    lines.extend([
        "",
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ])
    for table_row in table_rows:
        lines.append("| " + " | ".join(str(value) for value in table_row) + " |")
    lines.extend([
        "",
        "## Retrieval-context consistency",
        "",
        f"- Status: {consistency_status}",
        f"- Questions checked: {questions_checked}",
        f"- Expected questions: {expected_questions if consistency_applicable else 0}",
        f"- Context mismatches across models: {len(mismatches)}",
        "",
        "## Composite score",
        "",
        "The primary comparison uses a bilingual macro average, so English and Indonesian receive equal weight despite different question counts.",
        "",
        "Overall score = 35% answer quality + 30% grounding + 20% retrieval + 15% safety. Latency is reported separately and does not increase the quality score.",
        "",
        "If the LLM judge is skipped, fails, or has incomplete coverage, Overall is intentionally left empty; deterministic_score remains available for diagnostics only.",
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
                if consistency_status == "checked"
                else "Context mismatches were found; model-level comparisons are not evidence-locked for every question."
                if consistency_status == "mismatch"
                else "Context consistency is incomplete because one or more per-question detail files are missing or incomplete."
            ),
            "",
        ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Comparison CSV : {csv_path}")
    print(f"Comparison JSON: {json_path}")
    print(f"Comparison MD  : {md_path}")
    print(f"Report status  : {quality['status']}")
    print(f"Context mismatches: {len(mismatches)}")
    if args.require_final_report and not quality["final_eligible"]:
        raise SystemExit(
            "Report did not pass final-use quality gates. See the Markdown or JSON report."
        )


if __name__ == "__main__":
    main()
