"""Utilities for the bilingual 3-model generation evaluation dataset."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

NULL_VALUES = {"", "none", "null", "nan", "n/a", "-"}
TRUE_VALUES = {"true", "1", "yes", "y", "ya"}
FALSE_VALUES = {"false", "0", "no", "n", "tidak"}


def normalize_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.casefold() in NULL_VALUES else text


def parse_bool(value: Any, *, field_name: str = "answerable") -> bool:
    text = str(value or "").strip().casefold()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    raise ValueError(f"Invalid {field_name} value: {value!r}")


def parse_keywords(value: Any) -> list[str]:
    text = normalize_optional(value)
    if not text:
        return []
    parts = re.split(r"\s*\|\s*|\s*;\s*", text)
    output: list[str] = []
    seen: set[str] = set()
    for part in parts:
        clean = part.strip()
        key = clean.casefold()
        if clean and key not in NULL_VALUES and key not in seen:
            seen.add(key)
            output.append(clean)
    return output


def infer_language_from_path(path: Path) -> str:
    name = path.name.casefold()
    if "indonesia" in name or "indonesian" in name or re.search(r"(^|[_-])id([_.-]|$)", name):
        return "ID"
    if "english" in name or re.search(r"(^|[_-])en([_.-]|$)", name):
        return "EN"
    raise ValueError(
        f"Cannot infer language from filename {path.name!r}. "
        "Use a filename containing 'english' or 'indonesia'."
    )


def _canonical_row(
    row: dict[str, Any],
    *,
    language: str,
    index: int,
    source_path: Path,
) -> dict[str, Any]:
    question = str(row.get("question") or "").strip()
    expected_answer = str(row.get("expected_answer") or "").strip()
    if not question:
        raise ValueError(f"Empty question at {source_path}:{index + 1}")
    if not expected_answer:
        raise ValueError(f"Empty expected_answer at {source_path}:{index + 1}")

    answerable = parse_bool(row.get("answerable"), field_name="answerable")
    source_document = normalize_optional(row.get("source_document"))
    keywords = parse_keywords(row.get("expected_answer_keywords"))

    if answerable and not source_document:
        raise ValueError(
            f"Answerable row has no source_document at {source_path}:{index + 1}"
        )
    if not answerable and source_document:
        raise ValueError(
            f"Unanswerable row unexpectedly has source_document={source_document!r} "
            f"at {source_path}:{index + 1}"
        )

    prefix = "ID" if language == "ID" else "EN"
    return {
        "id": f"{prefix}-{index:03d}",
        "split": "all",
        "language": language,
        "question": question,
        "answerable": answerable,
        "expected_answer": expected_answer,
        "expected_answer_keywords": keywords,
        "references": (
            [{"document": source_document, "page": ""}]
            if source_document
            else []
        ),
        "source_dataset": source_path.name,
    }


def load_csv_dataset(path: Path, language: str | None = None) -> list[dict[str, Any]]:
    language = (language or infer_language_from_path(path)).upper()
    if language not in {"EN", "ID"}:
        raise ValueError(f"Unsupported language {language!r}; expected EN or ID")

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = set(reader.fieldnames or [])

    required = {
        "question",
        "expected_answer",
        "source_document",
        "answerable",
        "expected_answer_keywords",
    }
    missing = required - fieldnames
    if missing:
        raise ValueError(
            f"Missing columns in {path}: {', '.join(sorted(missing))}"
        )
    if not rows:
        raise ValueError(f"Dataset is empty: {path}")

    items = [
        _canonical_row(
            row,
            language=language,
            index=index,
            source_path=path,
        )
        for index, row in enumerate(rows, start=1)
    ]
    return items


def load_ground_truth_files(paths: Iterable[Path]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in paths:
        resolved = path.resolve()
        if resolved.suffix.casefold() == ".csv":
            items.extend(load_csv_dataset(resolved))
            continue

        payload = json.loads(resolved.read_text(encoding="utf-8"))
        json_items = payload.get("items") if isinstance(payload, dict) else payload
        if not isinstance(json_items, list) or not json_items:
            raise ValueError(f"Ground-truth JSON contains no items: {resolved}")
        items.extend(json_items)

    ids = [str(item.get("id") or "") for item in items]
    duplicates = [item for item, count in Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate question IDs: {', '.join(duplicates)}")

    normalized_questions: dict[str, str] = {}
    duplicate_questions: list[str] = []
    for item in items:
        normalized = " ".join(str(item.get("question") or "").casefold().split())
        if normalized in normalized_questions:
            duplicate_questions.append(str(item.get("question") or ""))
        normalized_questions[normalized] = str(item.get("id") or "")
    if duplicate_questions:
        raise ValueError(
            "Duplicate question text found: " + "; ".join(duplicate_questions[:5])
        )

    return items


def dataset_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    language_counts = Counter(str(item.get("language") or "") for item in items)
    answerable_counts = Counter(bool(item.get("answerable")) for item in items)
    by_language: dict[str, dict[str, int]] = {}
    for language in sorted(language_counts):
        subset = [item for item in items if item.get("language") == language]
        by_language[language] = {
            "total": len(subset),
            "answerable": sum(bool(item.get("answerable")) for item in subset),
            "unanswerable": sum(not bool(item.get("answerable")) for item in subset),
        }
    return {
        "total": len(items),
        "answerable": answerable_counts[True],
        "unanswerable": answerable_counts[False],
        "by_language": by_language,
    }


def context_fingerprint(contexts: list[dict[str, Any]]) -> str:
    canonical = [
        {
            "document": str(item.get("document_name") or "").casefold().strip(),
            "page": str(item.get("page") or "").strip(),
            "chunk_id": str(item.get("chunk_id") or "").strip(),
            "text": " ".join(str(item.get("text") or "").casefold().split()),
        }
        for item in contexts
    ]
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
