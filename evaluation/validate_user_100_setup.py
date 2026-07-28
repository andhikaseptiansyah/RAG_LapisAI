"""Validate that the exact 100-question bilingual dataset is ready for LapisAI evaluation."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = PROJECT_ROOT / "evaluation"
BACKEND_DIR = PROJECT_ROOT / "backend"
TRUE_VALUES = {"true", "1", "yes", "y", "ya"}
FALSE_VALUES = {"false", "0", "no", "n", "tidak"}


def parse_bool(value: Any) -> bool:
    text = str(value or "").strip().casefold()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    raise ValueError(f"Invalid answerable value: {value!r}")


def load(path: Path, language: str) -> list[dict[str, Any]]:
    required = {
        "question", "expected_answer", "source_document",
        "answerable", "expected_answer_keywords",
    }
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is missing columns: {sorted(missing)}")
        rows = list(reader)

    output: list[dict[str, Any]] = []
    for number, row in enumerate(rows, start=2):
        question = str(row.get("question") or "").strip()
        expected_answer = str(row.get("expected_answer") or "").strip()
        source_document = str(row.get("source_document") or "").strip()
        answerable = parse_bool(row.get("answerable"))
        if not question or not expected_answer:
            raise ValueError(f"Empty question/answer at {path}:{number}")
        if answerable and not source_document:
            raise ValueError(f"Answerable row has no source at {path}:{number}")
        if not answerable and source_document:
            raise ValueError(f"Unanswerable row has a source at {path}:{number}")
        output.append({
            "language": language,
            "question": question,
            "answerable": answerable,
            "source_document": source_document,
        })
    return output


def main() -> None:
    english = EVAL_DIR / "datasets" / "qna_english_user.csv"
    indonesian = EVAL_DIR / "datasets" / "qna_indonesia_user.csv"
    items = [*load(english, "EN"), *load(indonesian, "ID")]

    normalized_questions = [" ".join(item["question"].casefold().split()) for item in items]
    duplicates = [q for q, count in Counter(normalized_questions).items() if count > 1]
    if duplicates:
        raise SystemExit(f"Duplicate questions detected: {duplicates[:5]}")

    by_language: dict[str, dict[str, int]] = {}
    for language in ("EN", "ID"):
        subset = [item for item in items if item["language"] == language]
        by_language[language] = {
            "total": len(subset),
            "answerable": sum(item["answerable"] for item in subset),
            "unanswerable": sum(not item["answerable"] for item in subset),
        }
    summary = {
        "total": len(items),
        "answerable": sum(item["answerable"] for item in items),
        "unanswerable": sum(not item["answerable"] for item in items),
        "by_language": by_language,
    }
    expected = {
        "total": 100,
        "answerable": 90,
        "unanswerable": 10,
        "by_language": {
            "EN": {"total": 50, "answerable": 45, "unanswerable": 5},
            "ID": {"total": 50, "answerable": 45, "unanswerable": 5},
        },
    }
    if summary != expected:
        raise SystemExit(
            "Dataset is not the approved 100-question set.\n"
            f"Expected: {json.dumps(expected, ensure_ascii=False)}\n"
            f"Actual  : {json.dumps(summary, ensure_ascii=False)}"
        )

    expected_docs = {
        item["source_document"] for item in items if item["source_document"]
    }
    store_path = BACKEND_DIR / "documents_store.json"
    store_docs: set[str] = set()
    if store_path.exists():
        payload = json.loads(store_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            store_docs = {
                str(row.get("filename") or "").strip()
                for row in payload
                if isinstance(row, dict) and str(row.get("filename") or "").strip()
            }

    missing_metadata = sorted(expected_docs - store_docs) if store_docs else sorted(expected_docs)
    corpus_dir = BACKEND_DIR / "uploads" / "files"
    actual_files = {path.name for path in corpus_dir.iterdir() if path.is_file()} if corpus_dir.exists() else set()
    missing_files = sorted(expected_docs - actual_files)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Unique expected source documents: {len(expected_docs)}")
    print(f"Missing from documents_store.json: {len(missing_metadata)}")
    print(f"Missing physical corpus files: {len(missing_files)}")
    if missing_metadata:
        print("Metadata missing:", ", ".join(missing_metadata))
    if missing_files:
        print("Physical files missing:", ", ".join(missing_files))
        print("NOTE: the benchmark cannot run end-to-end until these documents and the Chroma index exist locally.")
    print("Dataset validation: PASS (exactly 100 approved questions).")


if __name__ == "__main__":
    main()
