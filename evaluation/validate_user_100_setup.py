"""Validate the approved 50 EN + 50 ID evaluation set and local runtime readiness."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = PROJECT_ROOT / "evaluation"
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.language import answer_matches_requested_language, detect_question_language
from uploads.config import CHROMA_PATH, UPLOAD_DIR

TRUE_VALUES = {"true", "1", "yes", "y", "ya"}
FALSE_VALUES = {"false", "0", "no", "n", "tidak"}
NULL_VALUES = {"", "none", "null", "nan", "n/a", "-"}


def parse_bool(value: Any) -> bool:
    text = str(value or "").strip().casefold()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    raise ValueError(f"Invalid answerable value: {value!r}")


def parse_keywords(value: Any) -> list[str]:
    text = str(value or "").strip()
    if text.casefold() in NULL_VALUES:
        return []
    keywords: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"\s*\|\s*|\s*;\s*", text):
        clean = part.strip()
        key = clean.casefold()
        if clean and key not in NULL_VALUES and key not in seen:
            seen.add(key)
            keywords.append(clean)
    return keywords


def normalize_metric_text(text: str) -> str:
    value = str(text or "").casefold()
    number_words = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "satu": "1", "dua": "2", "tiga": "3", "empat": "4", "lima": "5",
        "enam": "6", "tujuh": "7", "delapan": "8", "sembilan": "9", "sepuluh": "10",
    }
    for word, digit in number_words.items():
        value = re.sub(rf"\b{word}\b", digit, value)
    value = value.replace("upper case", "uppercase").replace("lower case", "lowercase")
    # Canonicalize equivalent negative phrases so keyword scoring is fair.
    value = __import__("re").sub(r"\bnone\s+resulting\s+in\b", "no", value)
    value = __import__("re").sub(r"\b(?:did|does)\s+not\s+result\s+in\b", "no", value)
    value = value.replace("wib", " wib ")
    value = re.sub(r"(?<=\d)[.,:](?=\d)", "", value)
    value = re.sub(r"[^a-z0-9à-ÿ%]+", " ", value)
    return " ".join(value.split())


def keyword_self_coverage(question: str, expected_answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    combined = normalize_metric_text(f"{question} {expected_answer}")
    combined_tokens = set(combined.split())
    hits = 0
    for keyword in keywords:
        normalized = normalize_metric_text(keyword)
        keyword_tokens = set(normalized.split())
        if normalized and (
            normalized in combined
            or (keyword_tokens and keyword_tokens.issubset(combined_tokens))
        ):
            hits += 1
    return hits / len(keywords)


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
        keywords = parse_keywords(row.get("expected_answer_keywords"))

        if not question or not expected_answer:
            raise ValueError(f"Empty question/answer at {path}:{number}")
        if answerable and not source_document:
            raise ValueError(f"Answerable row has no source at {path}:{number}")
        if not answerable and source_document:
            raise ValueError(f"Unanswerable row has a source at {path}:{number}")
        if answerable and not keywords:
            raise ValueError(f"Answerable row has no keywords at {path}:{number}")
        if not answerable and keywords:
            raise ValueError(f"Unanswerable row unexpectedly has keywords at {path}:{number}")

        detected = detect_question_language(question, fallback=language)
        if detected != language:
            raise ValueError(
                f"Question language mismatch at {path}:{number}: "
                f"expected {language}, detected {detected}"
            )
        if not answer_matches_requested_language(expected_answer, language):
            raise ValueError(f"Expected-answer language mismatch at {path}:{number}")

        coverage = keyword_self_coverage(question, expected_answer, keywords)
        if coverage < 1.0:
            raise ValueError(
                f"Keyword annotation is inconsistent at {path}:{number}; "
                f"self-coverage={coverage:.3f}; keywords={keywords}"
            )

        output.append({
            "language": language,
            "question": question,
            "answerable": answerable,
            "source_document": source_document,
        })
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-only",
        action="store_true",
        help="Validate CSV structure/language/annotations without requiring a local Chroma index.",
    )
    args = parser.parse_args()

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

    expected_docs = {item["source_document"] for item in items if item["source_document"]}
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
    corpus_dir = Path(UPLOAD_DIR)
    actual_files = (
        {path.name for path in corpus_dir.iterdir() if path.is_file()}
        if corpus_dir.is_dir()
        else set()
    )
    missing_files = sorted(expected_docs - actual_files)
    chroma_dir = Path(CHROMA_PATH)
    chroma_ready = chroma_dir.is_dir() and any(chroma_dir.iterdir())

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Unique expected source documents: {len(expected_docs)}")
    print(f"Missing from documents_store.json: {len(missing_metadata)}")
    print(f"Missing physical corpus files: {len(missing_files)}")
    print(f"Chroma index ready: {chroma_ready} ({chroma_dir})")

    if missing_metadata:
        raise SystemExit("Metadata readiness FAILED: " + ", ".join(missing_metadata))
    if missing_files:
        print("WARNING: physical source files are missing: " + ", ".join(missing_files))
        print("The existing Chroma index may still be evaluated, but the corpus cannot be reproduced/re-indexed.")

    print("Dataset validation: PASS (100 questions, language and keyword annotations are consistent).")
    if args.dataset_only:
        return
    if not chroma_ready:
        raise SystemExit(
            "Runtime readiness FAILED: Chroma index is missing or empty. "
            "Upload/re-index the corpus before running evaluation."
        )
    print("Runtime readiness: PASS.")


if __name__ == "__main__":
    main()
