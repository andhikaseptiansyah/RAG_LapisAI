"""Strict final evaluation runner for a frozen private holdout."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from private_holdout import (
    DEFAULT_PRIVATE_HOLDOUT_DIR,
    corpus_fingerprint,
    load_corpus_chunks,
    load_project_env,
    require_distinct_models,
    validate_private_holdout,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATION_DIR = Path(__file__).resolve().parent / "generation"
RUNNER = GENERATION_DIR / "run_three_model_evaluation.py"
AUDITOR = Path(__file__).resolve().parent / "audit_benchmark_leakage.py"
MODEL_ENV = {
    "ollama": "OLLAMA_MODEL",
    "gemini": "GEMINI_MODEL",
    "groq": "GROQ_MODEL",
}


def run(command: list[str]) -> None:
    print("\n> " + " ".join(command))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def configured_models(providers: list[str]) -> list[str]:
    models: list[str] = []
    missing: list[str] = []
    for provider in providers:
        env_name = MODEL_ENV[provider]
        value = os.getenv(env_name, "").strip()
        if not value:
            missing.append(env_name)
        else:
            models.append(value)
    if missing:
        raise ValueError(
            "Final evaluation requires explicit model references: "
            + ", ".join(missing)
        )
    return models


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run final evaluation only after every strict holdout gate passes."
    )
    parser.add_argument("--holdout-dir", type=Path, default=DEFAULT_PRIVATE_HOLDOUT_DIR)
    parser.add_argument(
        "--models",
        nargs="+",
        choices=("ollama", "gemini", "groq"),
        default=["ollama"],
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    load_project_env()
    holdout_dir = args.holdout_dir.resolve()
    active_chunks = load_corpus_chunks()
    active_corpus_sha256 = corpus_fingerprint(active_chunks)
    package = validate_private_holdout(
        holdout_dir,
        require_human_approval=True,
        expected_corpus_sha256=active_corpus_sha256,
    )
    manifest = package["manifest"]

    judge_model = os.getenv("EVAL_LLM_MODEL", "").strip()
    if not judge_model:
        raise SystemExit(
            "EVAL_LLM_MODEL is required. Configure a pinned independent judge model."
        )
    evaluated_models = configured_models(list(args.models))
    try:
        require_distinct_models(
            author=str(manifest.get("author_model") or ""),
            reviewer=str(manifest.get("reviewer_model") or ""),
            judge=judge_model,
            evaluated=evaluated_models,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if not os.getenv("EVAL_LLM_BASE_URL", "").strip():
        raise SystemExit("EVAL_LLM_BASE_URL must be explicitly configured.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (
        args.output_dir
        or (GENERATION_DIR / "results" / f"final_{timestamp}")
    ).resolve()
    if output_dir == holdout_dir or holdout_dir in output_dir.parents:
        raise SystemExit("Evaluation output must not be written inside the private holdout.")
    if output_dir.exists() and any(output_dir.iterdir()) and not args.resume:
        raise SystemExit(
            f"Output directory is not empty: {output_dir}. Use a new directory or --resume."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    print("FINAL EVALUATION PREFLIGHT: PASS")
    print(f"Holdout pairs : {manifest.get('pair_count')}")
    print(f"Corpus hash   : {active_corpus_sha256[:12]}")
    print(f"Author model  : {manifest.get('author_model')}")
    print(f"Reviewer model: {manifest.get('reviewer_model')}")
    print(f"Judge model   : {judge_model}")
    print(f"Evaluated     : {', '.join(evaluated_models)}")

    # Child evaluation processes record the frozen review manifest alongside
    # datasets and raw answers in their reproducibility hashes.
    os.environ["LAPISAI_HOLDOUT_MANIFEST"] = str(
        holdout_dir / "holdout_manifest.json"
    )

    audit_path = output_dir / "benchmark_leakage_preflight.json"
    run(
        [
            sys.executable,
            str(AUDITOR),
            "--ground-truth",
            str(package["english_path"]),
            "--ground-truth",
            str(package["indonesian_path"]),
            "--role",
            "holdout",
            "--output",
            str(audit_path),
        ]
    )
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("final_eligible") is not True:
        raise SystemExit("Private holdout leakage audit did not pass.")

    command = [
        sys.executable,
        str(RUNNER),
        "--english",
        str(package["english_path"]),
        "--indonesian",
        str(package["indonesian_path"]),
        "--models",
        *args.models,
        "--top-k",
        str(max(1, args.top_k)),
        "--retries",
        str(max(0, args.retries)),
        "--benchmark-role",
        "holdout",
        "--output-dir",
        str(output_dir),
        "--require-final-report",
    ]
    if args.resume:
        command.append("--resume")
    run(command)

    model_count = len(args.models)
    comparison_stem = (
        "comparison_1_model"
        if model_count == 1
        else f"comparison_{model_count}_models"
    )
    comparison_path = output_dir / f"{comparison_stem}.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    quality = comparison.get("report_quality") or {}
    if quality.get("status") != "FINAL_ELIGIBLE" or quality.get("final_eligible") is not True:
        raise SystemExit(
            "Evaluation finished but final quality gates did not pass: "
            + "; ".join(str(item) for item in quality.get("blockers") or [])
        )

    print("\nFINAL EVALUATION COMPLETE")
    print("Report status : FINAL_ELIGIBLE")
    print(f"Comparison    : {output_dir / f'{comparison_stem}.csv'}")
    print(f"Dashboard     : {output_dir / 'charts' / 'evaluation_dashboard.html'}")


if __name__ == "__main__":
    main()
