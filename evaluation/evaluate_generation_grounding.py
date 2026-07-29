"""Validate correct answers and automatically corrupted answers against context."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
EVALUATION_DIR = PROJECT_ROOT / "evaluation"
for path in (BACKEND_DIR, EVALUATION_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api.grounding_validator import validate_grounded_answer
from evaluate_ground_truth_sqlite import load_chroma_records


def corrupt_answer(answer: str) -> str:
    """Create a deterministic unsupported fact without changing the question."""
    if re.search(r"\d", answer):
        return re.sub(r"\d+(?:[.,]\d+)*", "987654321", answer, count=1)
    return f"{answer.rstrip()} The required system identifier is ZXQ9."


def evaluate(csv_path: Path, db_path: Path, collection_name: str) -> dict[str, Any]:
    records = load_chroma_records(db_path, collection_name)
    by_filename: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        enriched = {
            **record,
            "score": 0.90,
            "baseScore": 0.80,
            "evidenceScore": 0.90,
            "evidenceSupported": True,
            "evidenceHardFailures": [],
            "answerabilityEvidenceSelected": True,
        }
        filename = str(record.get("metadata", {}).get("filename") or "").casefold()
        by_filename[filename].append(enriched)

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    details: list[dict[str, Any]] = []
    for row in rows:
        question = str(row.get("question") or "")
        expected_answer = str(row.get("expected_answer") or "")
        source = Path(str(row.get("source_document") or "")).name.casefold()
        chunks = by_filename[source]

        correct = validate_grounded_answer(question, expected_answer, chunks)
        corrupted_text = corrupt_answer(expected_answer)
        corrupted = validate_grounded_answer(question, corrupted_text, chunks)
        details.append(
            {
                "question": question,
                "source": source,
                "correct_answer_supported": correct.supported,
                "correct_answer_reasons": list(correct.reasons),
                "corrupted_answer_rejected": not corrupted.supported,
                "corrupted_answer_reasons": list(corrupted.reasons),
                "corrupted_unsupported_facts": list(corrupted.unsupported_facts),
            }
        )

    total = len(details)
    correct_count = sum(item["correct_answer_supported"] for item in details)
    rejected_count = sum(item["corrupted_answer_rejected"] for item in details)
    return {
        "summary": {
            "questions": total,
            "correct_answers_supported": correct_count,
            "correct_answer_support_rate": round(correct_count / total if total else 0.0, 6),
            "corrupted_answers_rejected": rejected_count,
            "corrupted_answer_rejection_rate": round(rejected_count / total if total else 0.0, 6),
            "evaluation_mode": "post_generation_grounding_regression",
        },
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        type=Path,
        default=EVALUATION_DIR / "ground_truth_qa.csv",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=PROJECT_ROOT / "backend" / "chroma_db" / "chroma.sqlite3",
    )
    parser.add_argument("--collection", default="knowledge_base_multilingual_v1")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = evaluate(args.csv, args.db, args.collection)
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
