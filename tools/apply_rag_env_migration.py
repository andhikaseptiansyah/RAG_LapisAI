"""Safely update RAG tuning keys in an existing project .env.

Unknown keys and secrets are preserved. A timestamped backup is created before
writing. Run from the project root or pass --env path/to/.env.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

UPDATES: dict[str, str] = {
    "MIN_RESULT_SCORE": "0.24",
    "ENABLE_QUERY_DECOMPOSITION": "true",
    "QUERY_DECOMPOSITION_MAX_PARTS": "3",
    "MIN_EVIDENCE_SCORE": "0.42",
    "ANSWERABILITY_MIN_TOP_SCORE": "0.35",
    "ANSWERABILITY_MIN_BASE_SCORE": "0.22",
    "ANSWERABILITY_MIN_EVIDENCE_SCORE": "0.42",
    "ANSWERABILITY_MIN_SCORE_MARGIN": "0.0",
    "ANSWERABILITY_REQUIRE_SUPPORTED_EVIDENCE": "false",
    "ANSWERABILITY_STRONG_RETRIEVAL_SCORE": "0.68",
    "ANSWERABILITY_STRONG_EXACT_COVERAGE": "0.20",
    "ANSWERABILITY_MAX_CONTEXTS": "5",
    "ANSWERABILITY_PRE_RERANK_VETO": "false",
    "MIN_ANSWER_CONFIDENCE": "0.48",
    "MIN_SOURCE_CONFIDENCE": "0.24",
    "MAX_SOURCE_CITATIONS": "4",
    "ENABLE_GENERATION_GROUNDING_VALIDATION": "true",
    "GENERATION_MIN_CLAIM_SUPPORT": "0.32",
}


def migrate(env_path: Path) -> tuple[Path, list[str]]:
    if not env_path.exists():
        raise FileNotFoundError(f".env not found: {env_path}")

    original_lines = env_path.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    seen: set[str] = set()
    changed: list[str] = []

    for line in original_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue

        key, _, current_value = line.partition("=")
        normalized_key = key.strip()
        if normalized_key not in UPDATES:
            output.append(line)
            continue

        seen.add(normalized_key)
        new_value = UPDATES[normalized_key]
        output.append(f"{normalized_key}={new_value}")
        if current_value.strip() != new_value:
            changed.append(normalized_key)

    missing = [key for key in UPDATES if key not in seen]
    if missing:
        if output and output[-1].strip():
            output.append("")
        output.append("# RAG grounding and answerability calibration")
        for key in missing:
            output.append(f"{key}={UPDATES[key]}")
            changed.append(key)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = env_path.with_name(f"{env_path.name}.backup_{timestamp}")
    shutil.copy2(env_path, backup)
    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    return backup, changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, default=Path(".env"))
    args = parser.parse_args()

    backup, changed = migrate(args.env.resolve())
    print(f"Backup: {backup}")
    print(f"Updated keys: {len(changed)}")
    for key in changed:
        print(f"- {key}")


if __name__ == "__main__":
    main()
