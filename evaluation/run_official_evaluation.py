from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = PROJECT_ROOT / "evaluation"
GROUND_TRUTH = EVALUATION_DIR / "ground_truth_qa.csv"


def run(command: list[str]) -> None:
    print("\n>", " ".join(command))
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run LapisAI evaluation using the official 30-question ground_truth_qa.csv."
    )
    parser.add_argument("--k", default="1,3,5")
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--min-score", type=float, default=None)
    parser.add_argument("--index-missing", action="store_true")
    parser.add_argument("--no-reranker", action="store_true")
    parser.add_argument("--no-evidence-verification", action="store_true")
    parser.add_argument(
        "--ablation",
        action="store_true",
        help="Also compare retrieval with and without the reranker.",
    )
    parser.add_argument(
        "--generation",
        action="store_true",
        help="Also call the running backend and Ollama for generation evaluation.",
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    retrieval = [
        sys.executable,
        str(EVALUATION_DIR / "evaluate_retrieval.py"),
        "--ground-truth",
        str(GROUND_TRUTH),
        "--split",
        "all",
        "--k",
        args.k,
        "--candidate-k",
        str(args.candidate_k),
    ]
    if args.min_score is not None:
        retrieval.extend(["--min-score", str(args.min_score)])
    if args.index_missing:
        retrieval.append("--index-missing")
    if args.no_reranker:
        retrieval.append("--no-reranker")
    if args.no_evidence_verification:
        retrieval.append("--no-evidence-verification")
    run(retrieval)

    if args.ablation:
        ablation = [
            sys.executable,
            str(EVALUATION_DIR / "run_reranker_ablation.py"),
            "--ground-truth",
            str(GROUND_TRUTH),
            "--split",
            "all",
            "--k",
            args.k,
            "--candidate-k",
            str(args.candidate_k),
        ]
        if args.min_score is not None:
            ablation.extend(["--min-score", str(args.min_score)])
        if args.index_missing:
            ablation.append("--index-missing")
        if args.no_evidence_verification:
            ablation.append("--no-evidence-verification")
        run(ablation)

    if args.generation:
        generation_dir = EVALUATION_DIR / "generation"
        input_path = generation_dir / "input_answers_official.json"
        run(
            [
                sys.executable,
                str(generation_dir / "build_generation_dataset.py"),
                "--ground-truth",
                str(GROUND_TRUTH),
                "--output",
                str(input_path),
                "--split",
                "all",
                "--top-k",
                str(args.top_k),
            ]
        )
        run(
            [
                sys.executable,
                str(generation_dir / "evaluate_generation.py"),
                "--ground-truth",
                str(GROUND_TRUTH),
                "--input",
                str(input_path),
                "--output-prefix",
                "official",
            ]
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
