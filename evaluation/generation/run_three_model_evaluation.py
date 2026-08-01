"""One-command runner for the bilingual Ollama/Gemini/Groq evaluation."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DIR = PROJECT_ROOT / "evaluation"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_ENGLISH = EVALUATION_DIR / "datasets" / "qna_english_user.csv"
DEFAULT_INDONESIAN = EVALUATION_DIR / "datasets" / "qna_indonesia_user.csv"
VALID_MODELS = ("ollama", "gemini", "groq")


def run(command: list[str]) -> None:
    print("\n> " + " ".join(command))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--english", type=Path, default=DEFAULT_ENGLISH)
    parser.add_argument("--indonesian", type=Path, default=DEFAULT_INDONESIAN)
    parser.add_argument("--models", nargs="+", choices=VALID_MODELS, default=list(VALID_MODELS))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--skip-llm-judge", action="store_true")
    parser.add_argument("--allow-self-judge", action="store_true")
    parser.add_argument(
        "--benchmark-role",
        choices=("development", "holdout"),
        default="development",
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    english = args.english.resolve()
    indonesian = args.indonesian.resolve()
    common_dataset_args = [
        "--ground-truth", str(english),
        "--ground-truth", str(indonesian),
    ]

    validate_command = [
        sys.executable,
        str(SCRIPT_DIR / "build_generation_dataset.py"),
        *common_dataset_args,
        "--validate-only",
    ]
    run(validate_command)
    if args.validate_only:
        run([
            sys.executable,
            str(EVALUATION_DIR / "audit_benchmark_leakage.py"),
            *common_dataset_args,
            "--role", args.benchmark_role,
        ])
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (args.output_dir or (SCRIPT_DIR / "results" / f"three_model_{timestamp}")).resolve()
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    run([
        sys.executable,
        str(EVALUATION_DIR / "audit_benchmark_leakage.py"),
        *common_dataset_args,
        "--role", args.benchmark_role,
        "--output", str(output_dir / "benchmark_leakage_audit.json"),
    ])

    retrieval_snapshot = output_dir / "retrieval_snapshot.json"
    retrieval_command = [
        sys.executable,
        str(SCRIPT_DIR / "build_retrieval_snapshot.py"),
        *common_dataset_args,
        "--output", str(retrieval_snapshot),
        "--top-k", str(max(1, args.top_k)),
    ]
    if args.resume:
        retrieval_command.append("--resume")
    run(retrieval_command)

    summary_paths: list[Path] = []
    for model in args.models:
        raw_output = raw_dir / f"input_answers_{model}.json"
        build_command = [
            sys.executable,
            str(SCRIPT_DIR / "build_generation_dataset.py"),
            *common_dataset_args,
            "--model", model,
            "--output", str(raw_output),
            "--top-k", str(max(1, args.top_k)),
            "--retries", str(max(0, args.retries)),
            "--retrieval-snapshot", str(retrieval_snapshot),
        ]
        if args.resume:
            build_command.append("--resume")
        run(build_command)

        evaluate_command = [
            sys.executable,
            str(SCRIPT_DIR / "evaluate_generation.py"),
            *common_dataset_args,
            "--input", str(raw_output),
            "--output-dir", str(output_dir),
            "--output-prefix", model,
            "--benchmark-role", args.benchmark_role,
        ]
        if args.skip_llm_judge:
            evaluate_command.append("--skip-llm-judge")
        if args.allow_self_judge:
            evaluate_command.append("--allow-self-judge")
        run(evaluate_command)
        summary_paths.append(output_dir / f"generation_summary_{model}.json")

    compare_command = [
        sys.executable,
        str(SCRIPT_DIR / "compare_models.py"),
        "--output-dir", str(output_dir),
    ]
    for summary in summary_paths:
        compare_command.extend(["--summary", str(summary)])
    run(compare_command)

    charts_dir = output_dir / "charts"
    run([
        sys.executable,
        str(SCRIPT_DIR / "generate_evaluation_charts.py"),
        "--comparison", str(output_dir / "comparison_3_models.csv"),
        "--output-dir", str(charts_dir),
    ])

    print("\nEvaluation completed.")
    print(f"Results directory: {output_dir}")
    print(f"Main comparison : {output_dir / 'comparison_3_models.csv'}")
    print(f"Charts          : {charts_dir}")
    print(f"HTML dashboard  : {charts_dir / 'evaluation_dashboard.html'}")


if __name__ == "__main__":
    main()
