"""Validate the LapisAI ground-truth dataset against the indexed source corpus.

The validator intentionally uses the same page construction rules as
``backend/ingestion/parser.py``:

* PDF: physical PDF page number
* DOCX: one logical page per ten non-empty paragraphs
* TXT: one logical page per fifty source lines

Run from the project root:

    python evaluation/validate_ground_truth.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pymupdf
from docx import Document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = Path(__file__).resolve().with_name("ground_truth.json")
SOURCE_DIR = PROJECT_ROOT / "backend" / "uploads" / "files"
EXPECTED_PREFIXES = ("FAQ_", "Policy_", "Report_", "SOP_", "TECH_")


def normalize(text: str) -> str:
    """Normalize whitespace and punctuation spacing for robust excerpt checks."""
    value = str(text or "").replace("#", " ").replace("=", " ")
    value = re.sub(r"\s+", " ", value).strip().casefold()
    return value.replace("–", "-").replace("—", "-")


def parse_document(path: Path) -> dict[int, str]:
    """Return page-number to text using the production parser's page rules."""
    extension = path.suffix.lower()

    if extension == ".pdf":
        pages: dict[int, str] = {}
        document = pymupdf.open(path)
        try:
            for index, page in enumerate(document):
                text = page.get_text().strip()
                if text:
                    pages[index + 1] = text
        finally:
            document.close()
        return pages

    if extension == ".docx":
        document = Document(path)
        paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        return {
            (index // 10) + 1: "\n".join(paragraphs[index : index + 10])
            for index in range(0, len(paragraphs), 10)
        }

    if extension == ".txt":
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
        pages: dict[int, str] = {}
        for index in range(0, len(lines), 50):
            text = "\n".join(line for line in lines[index : index + 50] if line)
            if text.strip():
                pages[(index // 50) + 1] = text
        return pages

    raise ValueError(f"Unsupported source type: {path.suffix}")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def require(item: dict[str, Any], field: str, errors: list[str]) -> Any:
    if field not in item:
        fail(errors, f"{item.get('id', '<unknown>')}: missing field '{field}'")
        return None
    return item[field]


def validate() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not DATASET_PATH.exists():
        return [f"Dataset not found: {DATASET_PATH}"], warnings

    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    items = payload.get("items")
    if not isinstance(items, list):
        return ["Top-level 'items' must be a list."], warnings

    ids: set[str] = set()
    referenced_primary_docs: list[str] = []
    source_cache: dict[str, dict[int, str]] = {}

    allowed_splits = {"development", "test"}
    allowed_categories = {"faq", "policy", "report", "sop", "technical", "negative"}
    allowed_languages = {"en", "id"}
    allowed_difficulties = {"easy", "medium", "hard"}

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            fail(errors, f"Item #{index} must be an object.")
            continue

        item_id = require(item, "id", errors)
        split = require(item, "split", errors)
        category = require(item, "category", errors)
        language = require(item, "language", errors)
        difficulty = require(item, "difficulty", errors)
        question = require(item, "question", errors)
        answerable = require(item, "answerable", errors)
        expected_answer = require(item, "expected_answer", errors)
        keywords = require(item, "expected_answer_keywords", errors)
        references = require(item, "references", errors)

        if not isinstance(item_id, str) or not re.fullmatch(r"[A-Z]+-[0-9]{3}", item_id):
            fail(errors, f"Item #{index}: invalid id '{item_id}'.")
        elif item_id in ids:
            fail(errors, f"Duplicate id: {item_id}")
        else:
            ids.add(item_id)

        if split not in allowed_splits:
            fail(errors, f"{item_id}: invalid split '{split}'.")
        if category not in allowed_categories:
            fail(errors, f"{item_id}: invalid category '{category}'.")
        if language not in allowed_languages:
            fail(errors, f"{item_id}: invalid language '{language}'.")
        if difficulty not in allowed_difficulties:
            fail(errors, f"{item_id}: invalid difficulty '{difficulty}'.")
        if not isinstance(question, str) or not question.strip():
            fail(errors, f"{item_id}: question must be non-empty.")
        if not isinstance(expected_answer, str) or not expected_answer.strip():
            fail(errors, f"{item_id}: expected_answer must be non-empty.")
        if not isinstance(answerable, bool):
            fail(errors, f"{item_id}: answerable must be boolean.")
        if not isinstance(keywords, list):
            fail(errors, f"{item_id}: expected_answer_keywords must be a list.")
        if not isinstance(references, list):
            fail(errors, f"{item_id}: references must be a list.")
            continue

        if answerable:
            if not references:
                fail(errors, f"{item_id}: answerable question has no reference.")
            if not keywords:
                fail(errors, f"{item_id}: answerable question has no expected keywords.")
        else:
            if references:
                fail(errors, f"{item_id}: unanswerable question must not have references.")
            if keywords:
                fail(errors, f"{item_id}: unanswerable question must not have expected keywords.")

        for reference_index, reference in enumerate(references, start=1):
            if not isinstance(reference, dict):
                fail(errors, f"{item_id}: reference #{reference_index} must be an object.")
                continue

            document_name = reference.get("document")
            page_number = reference.get("page")
            source_excerpt = reference.get("source_excerpt")

            if not isinstance(document_name, str) or not document_name:
                fail(errors, f"{item_id}: reference #{reference_index} has no document name.")
                continue
            if not isinstance(page_number, int) or page_number < 1:
                fail(errors, f"{item_id}: invalid page '{page_number}' for {document_name}.")
                continue
            if not isinstance(source_excerpt, str) or not source_excerpt.strip():
                fail(errors, f"{item_id}: empty source excerpt for {document_name}.")
                continue

            source_path = SOURCE_DIR / document_name
            if not source_path.exists():
                fail(errors, f"{item_id}: source document does not exist: {document_name}")
                continue

            if document_name not in source_cache:
                try:
                    source_cache[document_name] = parse_document(source_path)
                except Exception as exc:  # noqa: BLE001
                    fail(errors, f"{item_id}: failed to parse {document_name}: {exc}")
                    continue

            pages = source_cache[document_name]
            if page_number not in pages:
                fail(errors, f"{item_id}: page {page_number} does not exist in {document_name}.")
                continue

            if normalize(source_excerpt) not in normalize(pages[page_number]):
                fail(
                    errors,
                    f"{item_id}: source excerpt was not found on page {page_number} of {document_name}.",
                )

            if reference_index == 1:
                referenced_primary_docs.append(document_name)

    corpus_docs = sorted(
        path.name
        for path in SOURCE_DIR.iterdir()
        if path.is_file() and path.name.startswith(EXPECTED_PREFIXES)
    )
    covered_docs = set(referenced_primary_docs)
    uncovered_docs = sorted(set(corpus_docs) - covered_docs)
    unexpected_docs = sorted(covered_docs - set(corpus_docs))

    if len(corpus_docs) != 50:
        warnings.append(f"Expected 50 enterprise corpus documents, found {len(corpus_docs)}.")
    if uncovered_docs:
        fail(errors, "Answerable dataset does not cover these corpus documents: " + ", ".join(uncovered_docs))
    if unexpected_docs:
        fail(errors, "Dataset references non-corpus documents: " + ", ".join(unexpected_docs))

    actual_stats = {
        "total_questions": len(items),
        "answerable_questions": sum(1 for item in items if item.get("answerable") is True),
        "unanswerable_questions": sum(1 for item in items if item.get("answerable") is False),
        "development_questions": sum(1 for item in items if item.get("split") == "development"),
        "test_questions": sum(1 for item in items if item.get("split") == "test"),
        "english_questions": sum(1 for item in items if item.get("language") == "en"),
        "indonesian_questions": sum(1 for item in items if item.get("language") == "id"),
    }
    declared_stats = payload.get("statistics", {})
    for key, actual_value in actual_stats.items():
        if declared_stats.get(key) != actual_value:
            fail(
                errors,
                f"statistics.{key} is {declared_stats.get(key)!r}; expected {actual_value}.",
            )

    duplicate_primary_docs = sorted(
        document for document, count in Counter(referenced_primary_docs).items() if count > 1
    )
    if duplicate_primary_docs:
        warnings.append(
            "Some source documents are primary references for multiple questions: "
            + ", ".join(duplicate_primary_docs)
        )

    return errors, warnings


def main() -> int:
    errors, warnings = validate()

    print("LapisAI ground-truth validation")
    print("=" * 34)
    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"\nValidation failed with {len(errors)} error(s).")
        return 1

    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    stats = payload["statistics"]
    print(f"Questions      : {stats['total_questions']}")
    print(f"Answerable     : {stats['answerable_questions']}")
    print(f"Unanswerable   : {stats['unanswerable_questions']}")
    print(f"Development    : {stats['development_questions']}")
    print(f"Test           : {stats['test_questions']}")
    print(f"English        : {stats['english_questions']}")
    print(f"Indonesian     : {stats['indonesian_questions']}")
    print("Source coverage: 50/50 enterprise documents")
    print("\nValidation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
