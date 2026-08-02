"""Audit exact benchmark leakage into production code and regression tests."""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tokenize
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATION_DIR = Path(__file__).resolve().parent / "generation"
if str(GENERATION_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATION_DIR))

from dataset_utils import load_ground_truth_files

PRODUCTION_ROOTS = (
    PROJECT_ROOT / "backend" / "api",
    PROJECT_ROOT / "backend" / "ingestion",
    PROJECT_ROOT / "backend" / "retrieval",
    PROJECT_ROOT / "backend" / "uploads",
)
TEST_ROOT = PROJECT_ROOT / "backend" / "tests"

IGNORED_FILE_MARKERS = (
    ".backup_",
    ".backup.",
    ".bak.",
)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _is_active_python_file(path: Path) -> bool:
    """Exclude archived source copies that are not imported by the runtime."""
    name = path.name.casefold()
    return (
        path.suffix.casefold() == ".py"
        and not any(marker in name for marker in IGNORED_FILE_MARKERS)
        and "__pycache__" not in path.parts
    )


def _text_files(roots: tuple[Path, ...]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file() and _is_active_python_file(root):
            files.append(root)
        elif root.is_dir():
            files.extend(
                path
                for path in root.rglob("*.py")
                if path.is_file() and _is_active_python_file(path)
            )
    return sorted(set(files))


def _searchable_python(path: Path) -> str:
    """Return Python source without comments.

    Comments often contain illustrative values such as ``50 GB`` and must not
    be reported as executable benchmark leakage. String literals remain in the
    searchable text because hard-coded questions or answers can influence the
    production pipeline directly.
    """
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        source = " ".join(
            token.string
            for token in tokens
            if token.type
            not in {
                tokenize.COMMENT,
                tokenize.ENCODING,
            }
        )
    except (IndentationError, SyntaxError, tokenize.TokenError):
        # A malformed file should not make the audit disappear. Fall back to
        # raw text and let the report expose any exact overlap conservatively.
        pass
    return _normalize(source)


def audit(items: list[dict[str, Any]]) -> dict[str, Any]:
    scopes = {
        "production": _text_files(PRODUCTION_ROOTS),
        "tests": _text_files((TEST_ROOT,)),
    }
    normalized_files = {
        scope: {
            path: _searchable_python(path)
            for path in paths
        }
        for scope, paths in scopes.items()
    }
    findings: list[dict[str, Any]] = []
    for item in items:
        values = {
            "question": _normalize(item.get("question") or ""),
            "expected_answer": _normalize(item.get("expected_answer") or ""),
        }
        for value_type, needle in values.items():
            if not needle:
                continue
            for scope, files in normalized_files.items():
                matches = [
                    str(path.relative_to(PROJECT_ROOT))
                    for path, content in files.items()
                    if needle in content
                ]
                if matches:
                    findings.append({
                        "id": str(item.get("id") or ""),
                        "language": str(item.get("language") or ""),
                        "value_type": value_type,
                        "scope": scope,
                        "files": matches,
                    })

    question_ids = sorted({
        finding["id"]
        for finding in findings
        if finding["value_type"] == "question"
    })
    answer_ids = sorted({
        finding["id"]
        for finding in findings
        if finding["value_type"] == "expected_answer"
    })
    production_ids = sorted({
        finding["id"] for finding in findings if finding["scope"] == "production"
    })
    test_ids = sorted({
        finding["id"] for finding in findings if finding["scope"] == "tests"
    })
    production_question_ids = sorted({
        finding["id"]
        for finding in findings
        if finding["scope"] == "production"
        and finding["value_type"] == "question"
    })
    production_answer_ids = sorted({
        finding["id"]
        for finding in findings
        if finding["scope"] == "production"
        and finding["value_type"] == "expected_answer"
    })
    test_question_ids = sorted({
        finding["id"]
        for finding in findings
        if finding["scope"] == "tests"
        and finding["value_type"] == "question"
    })
    test_answer_ids = sorted({
        finding["id"]
        for finding in findings
        if finding["scope"] == "tests"
        and finding["value_type"] == "expected_answer"
    })
    overlap_ids = sorted({finding["id"] for finding in findings})
    return {
        "total_items": len(items),
        "overlap_item_count": len(overlap_ids),
        "question_overlap_count": len(question_ids),
        "expected_answer_overlap_count": len(answer_ids),
        "production_overlap_count": len(production_ids),
        "test_overlap_count": len(test_ids),
        "production_question_overlap_count": len(production_question_ids),
        "production_expected_answer_overlap_count": len(production_answer_ids),
        "test_question_overlap_count": len(test_question_ids),
        "test_expected_answer_overlap_count": len(test_answer_ids),
        "question_overlap_ids": question_ids,
        "expected_answer_overlap_ids": answer_ids,
        "production_overlap_ids": production_ids,
        "test_overlap_ids": test_ids,
        "production_question_overlap_ids": production_question_ids,
        "production_expected_answer_overlap_ids": production_answer_ids,
        "test_question_overlap_ids": test_question_ids,
        "test_expected_answer_overlap_ids": test_answer_ids,
        "overlap_item_ids": overlap_ids,
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ground-truth",
        type=Path,
        action="append",
        required=True,
        dest="ground_truth_files",
    )
    parser.add_argument(
        "--role",
        choices=("development", "holdout"),
        default="development",
        help="Holdout mode fails on any exact overlap.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    items = load_ground_truth_files(args.ground_truth_files)
    report = {
        "benchmark_role": args.role,
        **audit(items),
    }
    overlap_count = int(report["overlap_item_count"])
    report["status"] = (
        "clean"
        if not overlap_count
        else "holdout_invalid_leakage"
        if args.role == "holdout"
        else "development_overlap_detected"
    )
    report["final_eligible"] = args.role == "holdout" and not overlap_count
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")

    if args.role == "holdout" and overlap_count:
        raise SystemExit(
            f"Holdout benchmark leakage detected in {overlap_count} item(s)."
        )
    if args.role == "development" and overlap_count:
        print(
            "WARNING: exact overlaps are allowed only because this benchmark "
            "is explicitly marked as a development/regression set. "
            f"Production IDs={report['production_overlap_count']}, "
            f"test IDs={report['test_overlap_count']}."
        )


if __name__ == "__main__":
    main()
