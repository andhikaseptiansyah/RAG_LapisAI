from api.grounding_validator import validate_grounded_answer


def _chunk():
    return {
        "content": (
            "Full-year 2025 revenue was IDR 158 billion. "
            "Net profit margin was 14%."
        ),
        "answerabilityEvidenceSelected": True,
        "contextSelected": True,
        "evidenceHardFailures": [],
    }


def test_indonesian_financial_metrics_are_grounded():
    decision = validate_grounded_answer(
        "Berapa pendapatan tahun 2025 dan margin laba bersih perusahaan?",
        (
            "Pendapatan tahun 2025 perusahaan adalah IDR 158 miliar. "
            "Margin laba bersih perusahaan adalah 14%."
        ),
        [_chunk()],
    )
    assert decision.supported is True
    assert decision.unsupported_claims == ()
    assert decision.unsupported_facts == ()


def test_wrong_margin_value_is_still_rejected():
    decision = validate_grounded_answer(
        "Berapa pendapatan tahun 2025 dan margin laba bersih perusahaan?",
        (
            "Pendapatan tahun 2025 perusahaan adalah IDR 158 miliar. "
            "Margin laba bersih perusahaan adalah 15%."
        ),
        [_chunk()],
    )
    assert decision.supported is False
    assert "15%" in decision.unsupported_facts


def test_unsupported_explanation_is_still_rejected():
    decision = validate_grounded_answer(
        "Berapa margin laba bersih perusahaan?",
        "Margin laba bersih perusahaan adalah 14% karena efisiensi operasional.",
        [_chunk()],
    )
    assert decision.supported is False
    assert any("efisiensi operasional" in item for item in decision.unsupported_claims)
