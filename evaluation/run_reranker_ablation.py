from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from uploads.config import (  # noqa: E402
    ANSWERABILITY_MIN_BASE_SCORE,
    ANSWERABILITY_PRE_RERANK_VETO,
    RERANKER_MODEL,
    RERANKER_WEIGHT,
)

EVALUATOR = PROJECT_ROOT / "evaluation" / "evaluate_retrieval.py"
DEFAULT_GROUND_TRUTH = PROJECT_ROOT / "evaluation" / "ground_truth_qa.csv"
DEFAULT_RESULTS = PROJECT_ROOT / "evaluation" / "results" / "reranker_ablation"


def _metric(summary: dict[str, Any], *path: str) -> float:
    value: Any = summary
    for key in path:
        if not isinstance(value, dict):
            return 0.0
        value = value.get(key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _run(label: str, args: argparse.Namespace, output_dir: Path, no_reranker: bool) -> dict[str, Any]:
    command = [
        sys.executable,
        str(EVALUATOR),
        "--ground-truth",
        str(args.ground_truth),
        "--split",
        args.split,
        "--k",
        args.k,
        "--candidate-k",
        str(args.candidate_k),
        "--min-score",
        str(args.min_score),
        "--output-dir",
        str(output_dir),
    ]
    if args.index_missing:
        command.append("--index-missing")
    if args.no_evidence_verification:
        command.append("--no-evidence-verification")
    if no_reranker:
        command.append("--no-reranker")

    print(f"\nRunning {label}...")
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {completed.returncode}")

    summary_path = output_dir / "retrieval_summary_latest.json"
    return json.loads(summary_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare retrieval with and without the cross-encoder reranker."
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=DEFAULT_GROUND_TRUTH,
        help="Official ground_truth_qa.csv or a legacy ground-truth JSON file.",
    )
    parser.add_argument("--split", choices=("development", "test", "all"), default="all")
    parser.add_argument("--k", default="1,3,5")
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--min-score", type=float, default=0.30)
    parser.add_argument("--index-missing", action="store_true")
    parser.add_argument("--no-evidence-verification", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()
    args.ground_truth = args.ground_truth.resolve()

    run_dir = args.output_dir.resolve() / datetime.now().strftime("%Y%m%d_%H%M%S")
    baseline_dir = run_dir / "without_reranker"
    reranker_dir = run_dir / "with_reranker"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    reranker_dir.mkdir(parents=True, exist_ok=True)

    baseline = _run("baseline without reranker", args, baseline_dir, no_reranker=True)
    reranked = _run("cross-encoder reranker", args, reranker_dir, no_reranker=False)

    primary_level = str(reranked.get("primary_level") or "document")
    level_path = ("overall", "answerable", f"{primary_level}_level")
    metrics = {
        "mrr": (*level_path, "mrr"),
        "hit_at_1": (*level_path, "hit@1"),
        "hit_at_3": (*level_path, "hit@3"),
        "recall_at_5": (*level_path, "recall@5"),
        "mean_latency_ms": ("overall", "answerable", "latency_ms", "mean"),
    }

    unanswerable_total = int(_metric(reranked, "overall", "unanswerable", "count"))
    if unanswerable_total > 0:
        metrics["false_positive_rate"] = (
            "overall",
            "unanswerable",
            "retrieval_false_positive_rate",
        )

    comparison: dict[str, Any] = {
        "dataset": reranked.get("dataset_name"),
        "ground_truth": str(args.ground_truth),
        "split": args.split,
        "primary_level": primary_level,
        "candidate_k_per_retriever": args.candidate_k,
        "minimum_score": args.min_score,
        "reranker_model": RERANKER_MODEL,
        "reranker_weight": RERANKER_WEIGHT,
        "ranking_strategy": "blended_hybrid_plus_cross_encoder",
        "answerability_min_base_score": ANSWERABILITY_MIN_BASE_SCORE,
        "answerability_pre_rerank_veto": ANSWERABILITY_PRE_RERANK_VETO,
        "unanswerable_evaluated": unanswerable_total > 0,
        "without_reranker": {},
        "with_reranker": {},
        "delta": {},
    }

    for name, path in metrics.items():
        before = _metric(baseline, *path)
        after = _metric(reranked, *path)
        comparison["without_reranker"][name] = before
        comparison["with_reranker"][name] = after
        comparison["delta"][name] = round(after - before, 6)

    if unanswerable_total > 0:
        comparison["unanswerable_counts"] = {
            "total": unanswerable_total,
            "without_reranker": baseline.get("overall", {}).get("unanswerable", {}),
            "with_reranker": reranked.get("overall", {}).get("unanswerable", {}),
        }

    json_path = run_dir / "reranker_comparison.json"
    json_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# Reranker Ablation Comparison",
        "",
        f"- Dataset: `{comparison.get('dataset') or '-'}`",
        f"- Ground truth: `{args.ground_truth}`",
        f"- Questions: `{reranked.get('question_counts', {}).get('total', 0)}`",
        f"- Primary retrieval level: `{primary_level}`",
        f"- Candidate count per retriever: `{args.candidate_k}`",
        f"- Minimum final score: `{args.min_score}`",
        f"- Reranker model: `{RERANKER_MODEL}`",
        f"- Reranker weight: `{RERANKER_WEIGHT}`",
        "",
        "| Metric | Without reranker | With reranker | Delta |",
        "|---|---:|---:|---:|",
    ]
    for name in metrics:
        report_lines.append(
            f"| {name} | {comparison['without_reranker'][name]:.6f} | "
            f"{comparison['with_reranker'][name]:.6f} | {comparison['delta'][name]:+.6f} |"
        )

    if unanswerable_total == 0:
        report_lines.extend(
            [
                "",
                "False-positive retrieval was not evaluated because the official CSV contains no unanswerable questions.",
            ]
        )

    report_lines.extend(
        [
            "",
            "A positive delta is desirable for MRR, Hit@1, Hit@3, and Recall@5. "
            "Latency should be reported separately and not hidden.",
            "",
        ]
    )
    report_path = run_dir / "reranker_comparison.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print("\nSaved comparison:")
    print(f"  {json_path}")
    print(f"  {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
