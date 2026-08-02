import hashlib

from evaluation.generation.compare_models import (
    comparison_output_stem,
    dataset_signature,
    derived_scores,
)
from evaluation.generation.build_generation_dataset import (
    classify_chat_failure,
    evaluation_credentials,
    load_retrieval_snapshot,
    snapshot_candidate_payload,
    validate_snapshot_contract,
)
from evaluation.generation.build_retrieval_snapshot import expected_document_names
from evaluation.generation.dataset_utils import parse_source_documents
from evaluation.generation.evaluate_generation import (
    detect_abstention,
    ranked_retrieval_metrics,
    source_metrics,
    validate_answer_records,
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


def test_blank_evaluation_password_falls_back_to_bootstrap(monkeypatch):
    monkeypatch.setenv("LAPISAI_EVAL_USERNAME", "admin")
    monkeypatch.setenv("LAPISAI_EVAL_PASSWORD", "   ")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "bootstrap-admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "local-test-password")

    assert evaluation_credentials() == ("admin", "local-test-password")


def test_explicit_evaluation_credentials_override_bootstrap(monkeypatch):
    monkeypatch.setenv("LAPISAI_EVAL_USERNAME", "evaluation-admin")
    monkeypatch.setenv("LAPISAI_EVAL_PASSWORD", "evaluation-password")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "bootstrap-admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "bootstrap-password")

    assert evaluation_credentials() == (
        "evaluation-admin",
        "evaluation-password",
    )


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


def test_composite_is_incomplete_when_only_some_answers_are_judged():
    result = derived_scores(
        {
            "token_f1": 0.8,
            "keyword_coverage": 0.9,
            "answer_relevance_1_to_5": 4.5,
            "faithfulness_1_to_5": 4.5,
            "hallucination_rate": 0.0,
            "judge_coverage": 0.75,
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
    assert result["score_status"] == "INCOMPLETE_JUDGE_COVERAGE"


def test_dataset_hash_signature_supports_windows_paths():
    signature = dataset_signature(
        {
            "reproducibility": {
                "files": [
                    {
                        "path": r"C:\project\evaluation\datasets\qna_english_user.csv",
                        "sha256": "ABC123",
                    }
                ]
            }
        }
    )
    assert signature == (("evaluation/datasets/qna_english_user.csv", "abc123"),)
    assert comparison_output_stem(1) == "comparison_1_model"
    assert comparison_output_stem(3) == "comparison_3_models"


def test_answer_input_rejects_duplicate_and_unknown_ids():
    ground_truth = {
        "EN-001": {"id": "EN-001"},
        "EN-002": {"id": "EN-002"},
    }
    try:
        validate_answer_records(
            [{"id": "EN-001"}, {"id": "EN-001"}],
            ground_truth,
        )
    except ValueError as error:
        assert "duplicate IDs" in str(error)
    else:
        raise AssertionError("Duplicate answer IDs must be rejected")

    try:
        validate_answer_records(
            [{"id": "EN-001"}, {"id": "EN-999"}],
            ground_truth,
        )
    except RuntimeError as error:
        assert "Missing=['EN-002']" in str(error)
        assert "extra=['EN-999']" in str(error)
    else:
        raise AssertionError("Unknown answer IDs must be rejected")


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
    assert classify_chat_failure(
        {
            "generation_mode": "retrieval_refusal",
            "failure_stage": "evaluation_snapshot_contract",
        }
    ) == "pipeline_contract"
    assert classify_chat_failure(
        {
            # Compatibility payloads used to overwrite a late failure's mode.
            # The precise stage must remain authoritative.
            "generation_mode": "retrieval_refusal",
            "retrieval_mode": "refused",
            "failure_stage": "citation_validation_failed",
        }
    ) == "answer_postprocessing"
    assert classify_chat_failure(
        {
            "generation_mode": "native_model",
            "failure_stage": "native_model_refusal",
        }
    ) == "generation_output"
    assert classify_chat_failure(
        {
            "generation_mode": "native_model",
            "failure_stage": "native_answer_empty",
        }
    ) == "generation_or_provider"
    assert classify_chat_failure(
        {
            "generation_mode": "wrong_output_language",
            "failure_stage": "wrong_output_language",
        }
    ) == "generation_or_provider"


def test_interchangeable_sources_use_or_semantics_for_metrics():
    alternatives = [
        {
            "document": "FAQ_Remote_Work.txt",
            "acceptable_alternative": True,
        },
        {
            "document": "Policy_WFH.docx",
            "acceptable_alternative": True,
        },
    ]
    source_result = source_metrics(
        [{"document": "Policy_WFH.docx"}],
        alternatives,
        [{"document": "Policy_WFH.docx"}],
        answerable=True,
    )
    ranked_result = ranked_retrieval_metrics(
        [{"document": "Policy_WFH.docx"}],
        alternatives,
        answerable=True,
        top_k=5,
    )

    assert source_result["context_recall"] == 1.0
    assert source_result["citation_precision"] == 1.0
    assert source_result["citation_recall"] == 1.0
    assert source_result["citation_f1"] == 1.0
    assert ranked_result["recall_at_k"] == 1.0
    assert ranked_result["top1_accuracy"] == 1.0
    assert ranked_result["ndcg_at_k"] == 1.0


def test_double_pipe_parses_only_explicit_source_alternatives():
    assert parse_source_documents(
        "FAQ_Remote_Work.txt || Policy_WFH.docx"
    ) == ["FAQ_Remote_Work.txt", "Policy_WFH.docx"]
    assert parse_source_documents("Policy_WFH.docx") == ["Policy_WFH.docx"]


def test_readiness_uses_unique_expected_source_documents_only():
    questions = [
        {"references": [{"document": "Policy.PDF", "page": "1"}]},
        {"references": [{"document": "policy.pdf", "page": "2"}]},
        {"references": []},
        {"references": [{"document": "Guide.docx", "page": ""}]},
    ]

    assert expected_document_names(questions) == ["Guide.docx", "Policy.PDF"]


def test_snapshot_payload_preserves_strict_and_coherent_gate_state():
    candidate = {
        "chunk_id": "chunk-1",
        "content_sha256": "a" * 64,
        "score": 0.91,
        "evidence_supported": False,
        "evidence_score": 0.66,
        "evidence_hard_failures": [],
        "evidence_hard_contradictions": [],
        "answerability_accepted": True,
        "answerability_strictly_supported": True,
        "answerability_evidence_selected": True,
        "answerability_requires_coherent_evidence": True,
        "answerability_coherent_evidence": True,
    }
    payload = snapshot_candidate_payload(
        candidate,
        {
            "retrieval_mode": "natural_language_bridge_raw",
            "retrieval_query": "What is the policy?",
        },
        "Apa kebijakannya?",
    )

    assert payload["evidenceSupported"] is False
    assert payload["answerabilityStrictlySupported"] is True
    assert payload["answerabilityCoherentEvidence"] is True
    assert payload["snapshotRetrievalQuery"] == "What is the policy?"


def test_snapshot_contract_rejects_a_changed_question():
    question = "What is the policy?"
    ground_truth = [
        {
            "id": "EN-001",
            "question": question,
            "language": "EN",
            "answerable": True,
        }
    ]
    snapshot = {
        "EN-001": {
            "id": "EN-001",
            "question": "What was the policy?",
            "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
            "language": "EN",
            "answerable": True,
            "ranked_candidates": [],
        }
    }

    try:
        validate_snapshot_contract(ground_truth, snapshot)
    except ValueError as error:
        assert "question changed" in str(error)
    else:
        raise AssertionError("A changed snapshot question must be rejected")
