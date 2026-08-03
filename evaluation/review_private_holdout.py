"""Mandatory human review for a generated private holdout package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from private_holdout import (
    DEFAULT_PRIVATE_HOLDOUT_DIR,
    refresh_manifest_file_hashes,
    utc_now,
    validate_private_holdout,
    write_json_atomic,
)


def show_record(record: dict, index: int, total: int) -> None:
    print("\n" + "=" * 78)
    print(
        f"[{index}/{total}] {record.get('pair_id')} | "
        f"{'ANSWERABLE' if record.get('answerable') else 'UNANSWERABLE'}"
    )
    print(f"Topic/source : {record.get('topic_document') or record.get('source_document')}")
    print(f"Question EN  : {record.get('question_en')}")
    print(f"Answer EN    : {record.get('answer_en')}")
    print(f"Question ID  : {record.get('question_id')}")
    print(f"Answer ID    : {record.get('answer_id')}")
    if record.get("answerable"):
        print(f"Evidence     : {record.get('evidence_quote')}")
    else:
        checked = record.get("reviewed_evidence") or []
        checked_names = sorted({
            str(item.get("filename") or "")
            for item in checked
            if isinstance(item, dict) and item.get("filename")
        })
        print(f"Corpus checks: {len(checked)} relevant chunks")
        if checked_names:
            print(f"Checked docs : {', '.join(checked_names)}")
    print(f"Model review : {record.get('reviewer_reason')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review every independently checked private-holdout pair."
    )
    parser.add_argument("--holdout-dir", type=Path, default=DEFAULT_PRIVATE_HOLDOUT_DIR)
    parser.add_argument("--reviewer-name", required=True)
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()

    reviewer_name = args.reviewer_name.strip()
    if len(reviewer_name) < 2:
        raise SystemExit("--reviewer-name must identify the human reviewer")

    holdout_dir = args.holdout_dir.resolve()
    package = validate_private_holdout(
        holdout_dir,
        require_human_approval=False,
    )
    review_path = holdout_dir / "holdout_review.json"
    review = package["review"]
    records = package["records"]

    if args.restart:
        for record in records:
            record["human_approved"] = False
            record["human_reviewer"] = None
            record["human_reviewed_at_utc"] = None
            record.pop("human_rejected", None)
            record.pop("human_rejection_reason", None)

    print(
        "Review each bilingual pair against its evidence. "
        "Approve only when the wording, answer, source, and translation are correct."
    )
    print("Commands: [a] approve, [r] reject, [q] save and quit")

    for index, record in enumerate(records, start=1):
        if record.get("human_approved") is True and not args.restart:
            continue
        show_record(record, index, len(records))
        while True:
            choice = input("Decision [a/r/q]: ").strip().casefold()
            if choice in {"a", "approve"}:
                record["human_approved"] = True
                record["human_reviewer"] = reviewer_name
                record["human_reviewed_at_utc"] = utc_now()
                record.pop("human_rejected", None)
                record.pop("human_rejection_reason", None)
                break
            if choice in {"r", "reject"}:
                reason = input("Rejection reason: ").strip()
                if not reason:
                    print("A rejection reason is required.")
                    continue
                record["human_approved"] = False
                record["human_rejected"] = True
                record["human_rejection_reason"] = reason
                record["human_reviewer"] = reviewer_name
                record["human_reviewed_at_utc"] = utc_now()
                break
            if choice in {"q", "quit"}:
                write_json_atomic(review_path, review)
                manifest = json.loads(
                    (holdout_dir / "holdout_manifest.json").read_text(encoding="utf-8")
                )
                refresh_manifest_file_hashes(holdout_dir, manifest)
                print("Review progress saved.")
                return
            print("Enter a, r, or q.")

        write_json_atomic(review_path, review)
        manifest = json.loads(
            (holdout_dir / "holdout_manifest.json").read_text(encoding="utf-8")
        )
        refresh_manifest_file_hashes(holdout_dir, manifest)

    rejected = [
        str(record.get("pair_id"))
        for record in records
        if record.get("human_approved") is not True
    ]
    if rejected:
        raise SystemExit(
            "Human review is incomplete or contains rejections: "
            + ", ".join(rejected)
            + ". Regenerate rejected pairs before final evaluation."
        )

    validate_private_holdout(
        holdout_dir,
        require_human_approval=True,
    )
    print("\nHUMAN REVIEW COMPLETE")
    print(f"Approved pairs: {len(records)}/{len(records)}")
    print("The private holdout is ready for strict final evaluation.")


if __name__ == "__main__":
    main()
