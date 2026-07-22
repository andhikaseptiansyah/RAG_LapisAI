from __future__ import annotations

import tempfile
from pathlib import Path

from dataset_utils import load_ground_truth_files, parse_bool, parse_keywords
from evaluate_generation import detect_abstention, keyword_coverage, source_metrics, token_f1


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    items = load_ground_truth_files([
        root / "datasets" / "qna_english_50.csv",
        root / "datasets" / "qna_indonesia_50.csv",
    ])
    assert len(items) == 100
    assert sum(item["language"] == "EN" for item in items) == 50
    assert sum(item["language"] == "ID" for item in items) == 50
    assert sum(item["answerable"] for item in items) == 90
    assert sum(not item["answerable"] for item in items) == 10
    assert parse_bool("TRUE") is True
    assert parse_bool("FALSE") is False
    assert parse_keywords("3 months | week 12") == ["3 months", "week 12"]
    assert detect_abstention("The indexed documents do not specify this value.")
    assert detect_abstention("Dokumen yang diindeks tidak menyebutkan informasi tersebut.")
    assert token_f1("3 months", "The probation period is 3 months.") > 0
    assert keyword_coverage(
        ["IDR 1.500.000"],
        "Berapa tunjangannya?",
        "Tunjangannya adalah IDR 1.500.000.",
    ) == 1.0

    answerable_metrics = source_metrics(
        [{"document": "Policy_WFH.docx"}],
        [{"document": "Policy_WFH.docx"}],
        [{"document": "Policy_WFH.docx"}],
        answerable=True,
    )
    assert answerable_metrics["context_recall"] == 1.0
    assert answerable_metrics["citation_accuracy"] == 1.0

    unanswerable_metrics = source_metrics([], [], [], answerable=False)
    assert unanswerable_metrics["retrieval_no_result"] == 1.0
    assert unanswerable_metrics["citation_accuracy"] == 1.0
    print("Evaluation helper tests passed.")


if __name__ == "__main__":
    main()
