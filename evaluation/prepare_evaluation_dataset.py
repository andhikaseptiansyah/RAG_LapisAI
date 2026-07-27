"""Validate and deduplicate bilingual Project-1 evaluation CSV files.

Exact duplicate questions with the same answerability and source are merged.
The more descriptive expected answer is retained and keywords are combined.
Conflicting duplicates fail loudly because silently averaging contradictions is
not evaluation; it is spreadsheet-themed fiction.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = (
    "question",
    "expected_answer",
    "source_document",
    "answerable",
    "expected_answer_keywords",
)
TRUE_VALUES = {"true", "1", "yes", "y", "ya"}
FALSE_VALUES = {"false", "0", "no", "n", "tidak"}
NULL_VALUES = {"", "none", "null", "nan", "n/a", "-"}


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def normalize_optional(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.casefold() in NULL_VALUES else text


def parse_bool(value: Any) -> bool:
    text = normalize_text(value)
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    raise ValueError(f"Invalid answerable value: {value!r}")


def parse_keywords(value: Any) -> list[str]:
    text = normalize_optional(value)
    if not text:
        return []
    parts = [part.strip() for part in text.replace(";", "|").split("|")]
    output: list[str] = []
    seen: set[str] = set()
    for part in parts:
        key = normalize_text(part)
        if part and key and key not in seen:
            seen.add(key)
            output.append(part)
    return output


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(REQUIRED_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name} is missing columns: {', '.join(sorted(missing))}")
        rows = [{key: str(row.get(key) or "").strip() for key in REQUIRED_COLUMNS} for row in reader]
    if not rows:
        raise ValueError(f"Dataset is empty: {path}")
    return rows


def merge_rows(rows: list[dict[str, str]], source_name: str) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    merged: dict[str, dict[str, str]] = {}
    first_row_number: dict[str, int] = {}
    duplicate_log: list[dict[str, Any]] = []

    for row_number, row in enumerate(rows, start=2):
        question = row["question"].strip()
        expected = row["expected_answer"].strip()
        if not question or not expected:
            raise ValueError(f"Empty question or expected answer at {source_name}:{row_number}")

        answerable = parse_bool(row["answerable"])
        source = normalize_optional(row["source_document"])
        if answerable and not source:
            raise ValueError(f"Answerable row has no source at {source_name}:{row_number}")
        if not answerable and source:
            raise ValueError(f"Unanswerable row unexpectedly has a source at {source_name}:{row_number}")

        key = normalize_text(question)
        canonical = {
            "question": question,
            "expected_answer": expected,
            "source_document": source,
            "answerable": "TRUE" if answerable else "FALSE",
            "expected_answer_keywords": " | ".join(parse_keywords(row["expected_answer_keywords"])) or "None",
        }
        if key not in merged:
            merged[key] = canonical
            first_row_number[key] = row_number
            continue

        existing = merged[key]
        if existing["answerable"] != canonical["answerable"] or normalize_text(existing["source_document"]) != normalize_text(canonical["source_document"]):
            raise ValueError(
                f"Conflicting duplicate question at {source_name}:{first_row_number[key]} and {row_number}: {question}"
            )

        existing_keywords = parse_keywords(existing["expected_answer_keywords"])
        new_keywords = parse_keywords(canonical["expected_answer_keywords"])
        combined: list[str] = []
        seen: set[str] = set()
        for keyword in [*existing_keywords, *new_keywords]:
            normalized = normalize_text(keyword)
            if normalized and normalized not in seen:
                seen.add(normalized)
                combined.append(keyword)

        if len(canonical["expected_answer"]) > len(existing["expected_answer"]):
            existing["expected_answer"] = canonical["expected_answer"]
        existing["expected_answer_keywords"] = " | ".join(combined) or "None"
        duplicate_log.append({
            "question": question,
            "kept_row": first_row_number[key],
            "merged_row": row_number,
            "source_document": source,
        })

    return list(merged.values()), duplicate_log


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REQUIRED_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, str]]) -> dict[str, int]:
    flags = Counter(parse_bool(row["answerable"]) for row in rows)
    return {
        "total": len(rows),
        "answerable": flags[True],
        "unanswerable": flags[False],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--english", type=Path, required=True)
    parser.add_argument("--indonesian", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    report: dict[str, Any] = {"files": {}, "duplicates_removed": []}
    total_rows: list[dict[str, str]] = []

    for language, input_path, output_name in (
        ("EN", args.english.resolve(), "qna_english_user.csv"),
        ("ID", args.indonesian.resolve(), "qna_indonesia_user.csv"),
    ):
        original = load_rows(input_path)
        cleaned, duplicates = merge_rows(original, input_path.name)
        output_path = output_dir / output_name
        write_csv(output_path, cleaned)
        report["files"][language] = {
            "input": str(input_path),
            "output": str(output_path),
            "original_rows": len(original),
            "cleaned": summarize(cleaned),
        }
        report["duplicates_removed"].extend(
            {"language": language, **item} for item in duplicates
        )
        total_rows.extend(cleaned)

    report["combined"] = summarize(total_rows)
    report_path = output_dir / "dataset_audit_user.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Audit report: {report_path}")


if __name__ == "__main__":
    main()
