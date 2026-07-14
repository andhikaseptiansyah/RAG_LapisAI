from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
UPLOAD_DIR = BACKEND_DIR / "uploads" / "files"
GROUND_TRUTH_PATH = PROJECT_ROOT / "evaluation" / "ground_truth.json"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ingestion.parser import parse_file
from retrieval.evidence_verifier import verify_evidence
from uploads.config import MIN_EVIDENCE_SCORE


def main() -> None:
    dataset = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []
    checked = 0
    strongly_supported = 0

    for item in dataset.get("items") or []:
        if not item.get("answerable"):
            continue

        references = item.get("references") or []
        if not references:
            failures.append(f"{item.get('id')}: missing reference")
            continue

        # Multi-hop questions may require evidence from more than one document.
        # Combine every labelled reference instead of validating only the first.
        reference_contents: list[str] = []
        for reference in references:
            document_path = UPLOAD_DIR / str(reference.get("document") or "")
            target_page = str(reference.get("page") or "")
            pages = parse_file(str(document_path))
            matching_pages = [
                page for page in pages
                if str(page.get("page") or "") == target_page
            ]
            # TXT and layout-unreliable DOCX references intentionally do not
            # expose fabricated page numbers. Fall back to the full document
            # instead of producing an empty evidence string.
            selected_pages = matching_pages or pages
            reference_contents.extend(
                str(page.get("text") or "")
                for page in selected_pages
            )

        content = " ".join(reference_contents)

        decision = verify_evidence(
            str(item.get("question") or ""),
            content,
            minimum_score=MIN_EVIDENCE_SCORE,
        )
        checked += 1
        if decision.supported:
            strongly_supported += 1

        # Runtime retrieval only removes a candidate when evidence has a hard
        # subject contradiction, such as a different year or mutually exclusive
        # metric. A low lexical score is allowed because many
        # ground-truth questions are Indonesian paraphrases of English sources.
        if decision.hard_failures:
            failures.append(
                f"{item.get('id')}: {decision.reason} "
                f"missing={list(decision.missing_concepts)}"
            )

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)

    print(
        "Evidence verifier did not hard-reject any answerable ground-truth "
        f"source set ({strongly_supported}/{checked} received a strong-evidence bonus)."
    )


if __name__ == "__main__":
    main()
