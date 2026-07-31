from evaluation.generation.compare_models import derived_scores
from evaluation.generation.build_generation_dataset import (
    classify_chat_failure,
    load_retrieval_snapshot,
)
from evaluation.generation.evaluate_generation import (
    detect_abstention,
    ranked_retrieval_metrics,
    source_metrics,
)


def test_supported_caveat_is_not_counted_as_a_refusal():
    answer = (
        "The exact date is not specified. However, the policy states that "
        "the review occurs after the three-month probation period."
    )
    assert detect_abstention(answer) is False
    assert detect_abstention(
        "The requested information was not found with sufficient evidence "
        "in the indexed documents."
    ) is True


def test_citation_f1_penalizes_an_extra_wrong_citation():
    metrics = source_metrics(
        [{"document": "Expected.pdf"}],
        [{"document": "Expected.pdf"}],
        [
            {"document": "Expected.pdf"},
            {"document": "Unrelated.pdf"},
        ],
        answerable=True,
    )
    assert metrics["citation_precision"] == 0.5
    assert metrics["citation_recall"] == 1.0
    assert round(float(metrics["citation_f1"]), 4) == 0.6667
    assert metrics["citation_accuracy"] == metrics["citation_f1"]


def test_ndcg_and_top1_expose_rank_quality():
    metrics = ranked_retrieval_metrics(
        [
            {"document": "Wrong.pdf"},
            {"document": "Expected.pdf"},
        ],
        [{"document": "Expected.pdf"}],
        answerable=True,
        top_k=5,
    )
    assert metrics["top1_accuracy"] == 0.0
    assert round(float(metrics["ndcg_at_k"]), 4) == 0.6309


def test_composite_is_incomplete_without_llm_judge():
    result = derived_scores(
        {
            "token_f1": 0.8,
            "keyword_coverage": 0.9,
            "citation_f1": 1.0,
            "recall_at_k": 1.0,
            "hit_at_k": 1.0,
            "mrr": 1.0,
            "false_refusal_rate": 0.0,
            "unanswerable_safety_rate": 1.0,
            "generation_failure_rate": 0.0,
        }
    )
    assert result["overall_score"] is None
    assert result["deterministic_score"] is not None
    assert result["score_status"] == "INCOMPLETE_MISSING_JUDGE"


def test_failure_taxonomy_and_optional_snapshot_mode():
    assert load_retrieval_snapshot(None) is None
    assert classify_chat_failure(
        {
            "generation_mode": "retrieval_refusal",
            "failure_stage": "context_or_answerability",
        }
    ) == "retrieval_or_context"
    assert classify_chat_failure(
        {
            "generation_mode": "native_model",
            "failure_stage": "answer_or_source_build",
        }
    ) == "answer_postprocessing"
