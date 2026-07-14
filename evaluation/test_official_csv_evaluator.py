from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from evaluation.evaluate_retrieval import (
    build_summary,
    evaluate_item,
    load_ground_truth,
    write_markdown_report,
)
from evaluation.generation.evaluate_generation import (
    exact_match,
    metadata_metrics,
    token_f1,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "evaluation" / "ground_truth_qa.csv"


def test_official_csv_is_the_default_30_question_dataset() -> None:
    dataset, items = load_ground_truth(CSV_PATH)

    assert dataset["source_format"] == "csv"
    assert dataset["evaluation_level"] == "document"
    assert dataset["has_page_references"] is False
    assert len(items) == 30
    assert all(item["answerable"] for item in items)
    assert items[0]["id"] == "QA-001"
    assert items[-1]["id"] == "QA-030"


def test_document_retrieval_is_scored_without_page_labels() -> None:
    _, items = load_ground_truth(CSV_PATH)
    item = items[0]

    def fake_search(*args, **kwargs):
        return [
            {
                "documentName": "SOP_Onboarding.pdf",
                "page": 2,
                "chunkIndex": 0,
                "score": 0.91,
                "content": "The probation period is three months.",
            }
        ]

    row = evaluate_item(
        item=item,
        hybrid_search=fake_search,
        k_values=[1, 3, 5],
        candidate_k=20,
        min_score=0.3,
        use_reranker=True,
        verify_evidence=True,
    )

    assert row["first_relevant_document_rank"] == 1
    assert row["document_mrr"] == 1.0
    assert row["document_metrics"]["hit@1"] == 1.0
    assert row["page_mrr"] is None
    assert row["page_metrics"] == {}


def test_official_report_does_not_invent_page_or_unanswerable_metrics(tmp_path: Path) -> None:
    dataset, items = load_ground_truth(CSV_PATH)

    def fake_search(question, **kwargs):
        source = next(
            item["references"][0]["document"]
            for item in items
            if item["question"] == question
        )
        return [{"documentName": source, "page": 1, "score": 0.9, "content": "supported"}]

    rows = [
        evaluate_item(
            item=item,
            hybrid_search=fake_search,
            k_values=[1, 3, 5],
            candidate_k=20,
            min_score=0.3,
            use_reranker=True,
            verify_evidence=True,
        )
        for item in items[:2]
    ]
    args = Namespace(
        split="all",
        k_values=[1, 3, 5],
        candidate_k=20,
        min_score=0.3,
        no_reranker=False,
        no_evidence_verification=False,
        ground_truth=CSV_PATH,
    )
    summary = build_summary(
        dataset,
        rows,
        args,
        {
            "corpus_files": 50,
            "indexed_corpus_files": 50,
            "missing_corpus_files": 0,
            "indexed_document_names": set(),
        },
    )
    report = tmp_path / "report.md"
    write_markdown_report(report, summary)
    text = report.read_text(encoding="utf-8")

    assert summary["primary_level"] == "document"
    assert summary["overall"]["answerable"]["document_level"]["hit@1"] == 1.0
    assert summary["overall"]["answerable"]["page_level"] == {}
    assert "Not evaluated because `ground_truth_qa.csv` provides" in text
    assert "official CSV contains only answerable questions" in text


def test_generation_source_metrics_compare_csv_labels_at_document_level() -> None:
    expected = [{"document": "SOP_Onboarding.pdf", "page": ""}]
    retrieved = [{"document": "SOP_Onboarding.pdf", "page": "2"}]
    citations = [{"document": "SOP_Onboarding.pdf", "page": "2"}]

    precision, recall, citation = metadata_metrics(retrieved, expected, citations)

    assert precision == 5.0
    assert recall == 5.0
    assert citation == 5.0


def test_deterministic_answer_accuracy_metrics() -> None:
    expected = "60 minutes."
    assert exact_match(expected, "60 minutes") == 1.0
    assert token_f1(expected, "Internal API tokens are valid for 60 minutes.") >= 0.4
