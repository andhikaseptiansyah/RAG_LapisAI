from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from uploads.config import (
    ANSWERABILITY_MIN_BASE_SCORE,
    ANSWERABILITY_PRE_RERANK_VETO,
    RERANKER_MODEL,
    RERANKER_WEIGHT,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = PROJECT_ROOT / "evaluation" / "evaluate_retrieval.py"
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
        description="Run retrieval evaluation with and without the cross-encoder reranker."
    )
    parser.add_argument("--split", choices=("development", "test", "all"), default="development")
    parser.add_argument("--k", default="1,3,5")
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--min-score", type=float, default=0.30)
    parser.add_argument("--index-missing", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()

    run_dir = args.output_dir.resolve() / datetime.now().strftime("%Y%m%d_%H%M%S")
    baseline_dir = run_dir / "without_reranker"
    reranker_dir = run_dir / "with_reranker"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    reranker_dir.mkdir(parents=True, exist_ok=True)

    baseline = _run("baseline without reranker", args, baseline_dir, no_reranker=True)
    reranked = _run("cross-encoder reranker", args, reranker_dir, no_reranker=False)

    metrics = {
        "page_mrr": ("overall", "answerable", "page_level", "mrr"),
        "page_hit_at_1": ("overall", "answerable", "page_level", "hit@1"),
        "page_recall_at_5": ("overall", "answerable", "page_level", "recall@5"),
        "false_positive_rate": (
            "overall",
            "unanswerable",
            "retrieval_false_positive_rate",
        ),
        "mean_latency_ms": ("overall", "answerable", "latency_ms", "mean"),
    }

    comparison: dict[str, Any] = {
        "split": args.split,
        "candidate_k_per_retriever": args.candidate_k,
        "minimum_score": args.min_score,
        "reranker_model": RERANKER_MODEL,
        "reranker_weight": RERANKER_WEIGHT,
        "ranking_strategy": "blended_hybrid_plus_cross_encoder",
        "answerability_min_base_score": ANSWERABILITY_MIN_BASE_SCORE,
        "answerability_pre_rerank_veto": ANSWERABILITY_PRE_RERANK_VETO,
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

    comparison["unanswerable_counts"] = {
        "total": int(_metric(reranked, "overall", "unanswerable", "count")),
        "without_reranker": {
            "correctly_rejected": int(_metric(baseline, "overall", "unanswerable", "true_rejection_count")),
            "false_positives": int(_metric(baseline, "overall", "unanswerable", "false_positive_count")),
            "false_positive_ids": baseline.get("overall", {}).get("unanswerable", {}).get("false_positive_ids", []),
        },
        "with_reranker": {
            "correctly_rejected": int(_metric(reranked, "overall", "unanswerable", "true_rejection_count")),
            "false_positives": int(_metric(reranked, "overall", "unanswerable", "false_positive_count")),
            "false_positive_ids": reranked.get("overall", {}).get("unanswerable", {}).get("false_positive_ids", []),
        },
    }

    json_path = run_dir / "reranker_comparison.json"
    json_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# Reranker Ablation Comparison",
        "",
        f"- Split: `{args.split}`",
        f"- Candidate count per retriever: `{args.candidate_k}`",
        f"- Minimum final score: `{args.min_score}`",
        f"- Reranker model: `{RERANKER_MODEL}`",
        f"- Reranker weight: `{RERANKER_WEIGHT}`",
        "- Ranking strategy: `blended hybrid + cross-encoder`",
        f"- Minimum original hybrid score: `{ANSWERABILITY_MIN_BASE_SCORE}`",
        f"- Pre-rerank rejection veto: `{ANSWERABILITY_PRE_RERANK_VETO}`",
        "",
        "| Metric | Without reranker | With reranker | Delta |",
        "|---|---:|---:|---:|",
    ]
    for name in metrics:
        report_lines.append(
            f"| {name} | {comparison['without_reranker'][name]:.6f} | "
            f"{comparison['with_reranker'][name]:.6f} | {comparison['delta'][name]:+.6f} |"
        )
    counts = comparison["unanswerable_counts"]
    report_lines.extend(
        [
            "",
            "## Unanswerable absolute counts",
            "",
            f"- Total unanswerable questions: `{counts['total']}`",
            f"- Without reranker - correctly rejected: `{counts['without_reranker']['correctly_rejected']}`, false positives: `{counts['without_reranker']['false_positives']}`",
            f"- Without reranker false-positive IDs: `{', '.join(counts['without_reranker']['false_positive_ids']) or '-'}`",
            f"- With reranker - correctly rejected: `{counts['with_reranker']['correctly_rejected']}`, false positives: `{counts['with_reranker']['false_positives']}`",
            f"- With reranker false-positive IDs: `{', '.join(counts['with_reranker']['false_positive_ids']) or '-'}`",
            "",
            "A positive delta is desirable for MRR, Hit@1, and Recall@5. A negative delta is "
            "desirable for false-positive rate. Latency is expected to increase and should be "
            "reported rather than hidden.",
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
