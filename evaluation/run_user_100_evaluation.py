"""Run the public 100-question development/regression evaluation.

This command deliberately cannot produce a final holdout report.  Final runs
must use ``run_final_evaluation.py`` with a private, independently reviewed
holdout package.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = PROJECT_ROOT / "evaluation"
RUNNER = EVALUATION_DIR / "generation" / "run_three_model_evaluation.py"
ENGLISH = EVALUATION_DIR / "datasets" / "qna_english_user.csv"
INDONESIAN = EVALUATION_DIR / "datasets" / "qna_indonesia_user.csv"
TEMPORARY_PROVIDER_EXIT_CODE = 75


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", choices=("ollama", "gemini", "groq"), default=["ollama", "gemini", "groq"])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-llm-judge", action="store_true")
    parser.add_argument("--allow-self-judge", action="store_true")
    parser.add_argument(
        "--benchmark-role",
        choices=("development", "holdout"),
        default="development",
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--require-final-report", action="store_true")
    args = parser.parse_args()

    if args.benchmark_role == "holdout" or args.require_final_report:
        raise SystemExit(
            "run_user_100_evaluation.py uses the public development/regression "
            "dataset and cannot be used as a final holdout. Run "
            "evaluation/create_private_holdout.py, complete "
            "evaluation/review_private_holdout.py, then use "
            "evaluation/run_final_evaluation.py."
        )

    readiness_command = [
        sys.executable,
        str(EVALUATION_DIR / "validate_user_100_setup.py"),
    ]
    if args.validate_only:
        # Dataset validation must remain usable before the local corpus and
        # Chroma index are prepared.
        readiness_command.append("--dataset-only")
    subprocess.run(readiness_command, cwd=PROJECT_ROOT, check=True)

    command = [
        sys.executable,
        str(RUNNER),
        "--english", str(ENGLISH),
        "--indonesian", str(INDONESIAN),
        "--top-k", str(max(1, args.top_k)),
        "--models", *args.models,
    ]
    if args.resume:
        command.append("--resume")
    if args.skip_llm_judge:
        command.append("--skip-llm-judge")
    if args.allow_self_judge:
        command.append("--allow-self-judge")
    command.extend(["--benchmark-role", args.benchmark_role])
    if args.validate_only:
        command.append("--validate-only")
    if args.output_dir:
        command.extend(["--output-dir", str(args.output_dir)])
    if args.require_final_report:
        command.append("--require-final-report")

    print("> " + " ".join(command))
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode == TEMPORARY_PROVIDER_EXIT_CODE:
        print(
            "\nEVALUASI SEBAGIAN SELESAI. Satu provider tertunda karena rate limit "
            "atau kuota. Progress tersimpan; ulangi perintah ini dengan --resume."
        )
        raise SystemExit(TEMPORARY_PROVIDER_EXIT_CODE)
    completed.check_returncode()
    if not args.validate_only:
        print("\nPUBLIC REGRESSION COMPLETE")
        print(
            "Expected status: DIAGNOSTIC_ONLY. This public dataset is for "
            "regression/debugging and cannot become a final holdout report."
        )
        if args.skip_llm_judge:
            print(
                "Semantic judge metrics are intentionally empty because "
                "--skip-llm-judge was used."
            )


if __name__ == "__main__":
    main()
