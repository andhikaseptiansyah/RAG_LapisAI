from evaluation.generation.compare_models import derived_scores
from evaluation.generation.evaluate_generation import ranked_retrieval_metrics


def test_ranked_retrieval_metrics_document_level():
    metrics = ranked_retrieval_metrics(
        [
            {"document": "Wrong.pdf"},
            {"document": "Expected.pdf"},
            {"document": "Expected.pdf"},
        ],
        [{"document": "Expected.pdf", "page": ""}],
        answerable=True,
        top_k=5,
    )
    assert metrics["precision_at_k"] == 0.2
    assert metrics["recall_at_k"] == 1.0
    assert metrics["hit_at_k"] == 1.0
    assert metrics["mrr"] == 0.5
    assert metrics["first_relevant_rank"] == 2.0


def test_composite_score_uses_quality_not_latency():
    base = {
        "token_f1": 0.8,
        "keyword_coverage": 0.9,
        "answer_relevance_1_to_5": 4.5,
        "faithfulness_1_to_5": 4.5,
        "citation_accuracy": 1.0,
        "hallucination_rate": 0.0,
        "recall_at_k": 1.0,
        "hit_at_k": 1.0,
        "mrr": 1.0,
        "false_refusal_rate": 0.0,
        "unanswerable_safety_rate": 1.0,
        "generation_failure_rate": 0.0,
        "average_response_time_ms": 999999,
    }
    score = derived_scores(base)
    assert score["overall_score"] > 90
    assert score["retrieval_score"] == 100.0
