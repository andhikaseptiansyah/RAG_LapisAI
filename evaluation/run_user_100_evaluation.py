"""Run LapisAI evaluation using only the approved 50 EN + 50 ID questions."""
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", choices=("ollama", "gemini", "groq"), default=["ollama", "gemini", "groq"])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-llm-judge", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

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
    if args.validate_only:
        command.append("--validate-only")
    if args.output_dir:
        command.extend(["--output-dir", str(args.output_dir)])

    print("> " + " ".join(command))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


if __name__ == "__main__":
    main()
