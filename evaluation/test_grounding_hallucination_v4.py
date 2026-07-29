from api.grounding_validator import prune_unsupported_claims, validate_grounded_answer


def row(content: str) -> dict:
    return {
        "chunkId": "source",
        "content": content,
        "score": 0.9,
        "baseScore": 0.9,
        "evidenceScore": 0.9,
        "evidenceSupported": True,
        "answerabilityAccepted": True,
        "answerabilityEvidenceSelected": True,
        "contextSelected": True,
        "metadata": {"filename": "source.pdf", "page": 1},
    }


def test_supported_fact_with_unsupported_causal_tail_is_rejected() -> None:
    chunks = [row("The platform uses PostgreSQL as its primary database.")]
    result = validate_grounded_answer(
        "What database does the platform use?",
        "The platform uses PostgreSQL because it is more scalable and reliable.",
        chunks,
    )
    assert result.supported is False
    assert any("scalable" in claim for claim in result.unsupported_claims)


def test_pruning_keeps_supported_fact_and_removes_causal_tail() -> None:
    chunks = [row("The platform uses PostgreSQL as its primary database.")]
    answer = prune_unsupported_claims(
        "What database does the platform use?",
        "The platform uses PostgreSQL because it is more scalable and reliable.",
        chunks,
    )
    assert "PostgreSQL" in answer
    assert "scalable" not in answer
    assert validate_grounded_answer(
        "What database does the platform use?", answer, chunks
    ).supported


def test_supported_multi_part_values_still_pass_after_clause_split() -> None:
    chunks = [row("The recovery time objective (RTO) is 4 hours and the recovery point objective (RPO) is 1 hour.")]
    result = validate_grounded_answer(
        "What are the RTO and RPO?",
        "The RTO is 4 hours and the RPO is 1 hour.",
        chunks,
    )
    assert result.supported is True, result


def test_unsupported_exclusive_qualifier_is_rejected() -> None:
    chunks = [row("Employees may work from home up to two days per week with manager approval.")]
    result = validate_grounded_answer(
        "How many days per week can employees work from home?",
        "Employees may work from home only two days per week.",
        chunks,
    )
    assert result.supported is False


def test_supported_short_answer_remains_valid() -> None:
    chunks = [row("The platform uses PostgreSQL as its primary database.")]
    result = validate_grounded_answer(
        "What database does the platform use?", "PostgreSQL.", chunks
    )
    assert result.supported is True, result
