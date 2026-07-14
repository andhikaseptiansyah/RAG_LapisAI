from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.grounding_validator import validate_grounded_answer


def chunks(content: str) -> list[dict]:
    return [
        {
            "chunkId": "source-1",
            "content": content,
            "score": 0.82,
            "baseScore": 0.72,
            "evidenceSupported": True,
            "evidenceHardFailures": [],
            "answerabilityEvidenceSelected": True,
        }
    ]


def test_supported_bilingual_numeric_answer_passes() -> None:
    result = validate_grounded_answer(
        "Berapa pendapatan FY2025 dan margin laba bersihnya?",
        "Pendapatan FY2025 sebesar IDR 158 miliar dengan margin laba bersih 14%.",
        chunks("Full-year 2025 revenue was IDR 158 billion, with a 14% net profit margin."),
    )
    assert result.supported, result


def test_hallucinated_amount_is_rejected() -> None:
    result = validate_grounded_answer(
        "Berapa tunjangan home-office?",
        "Tunjangan home-office adalah IDR 2,000,000.",
        chunks("Employees receive a one-time home-office allowance of IDR 1,500,000."),
    )
    assert not result.supported
    assert result.unsupported_facts


def test_hallucinated_system_identifier_is_rejected() -> None:
    result = validate_grounded_answer(
        "Bagaimana reset password?",
        "Ajukan tiket melalui SAP dan proses selesai dalam 24 jam.",
        chunks("Raise a ticket through the IT Helpdesk portal; resets are processed within 1x24 hours."),
    )
    assert not result.supported
    assert "SAP" in result.unsupported_facts


def test_missing_requested_percentage_is_rejected() -> None:
    result = validate_grounded_answer(
        "Berapa pendapatan FY2025 dan margin laba bersihnya?",
        "Pendapatan FY2025 adalah IDR 158 miliar.",
        chunks("Full-year 2025 revenue was IDR 158 billion, with a 14% net profit margin."),
    )
    assert not result.supported
    assert "answer_percentage" in result.missing_answer_requirements


def test_same_number_with_wrong_unit_is_rejected() -> None:
    result = validate_grounded_answer(
        "Berapa lama penyimpanan log?",
        "Log disimpan selama 50 hari.",
        chunks("The standard mailbox quota is 50 GB."),
    )
    assert not result.supported
    assert any("50 days" in fact for fact in result.unsupported_facts)


def test_explicit_scenario_number_from_question_is_allowed() -> None:
    result = validate_grounded_answer(
        "Jika klaim diajukan setelah 12 hari, apakah masih memenuhi batas 10 hari?",
        "Klaim setelah 12 hari tidak memenuhi kebijakan karena batasnya 10 hari.",
        chunks("Expense claims must be submitted within 10 days."),
    )
    assert result.supported, result


def test_multi_separator_currency_amount_is_checked_as_one_fact() -> None:
    result = validate_grounded_answer(
        "Berapa tunjangan home-office?",
        "Tunjangan home-office adalah IDR 2,000,000.",
        chunks("Employees receive a one-time home-office allowance of IDR 1,500,000."),
    )
    assert not result.supported
    assert "idr 2000000" in result.unsupported_facts


def test_money_condition_does_not_require_money_in_answer() -> None:
    result = validate_grounded_answer(
        "What approval is needed for a purchase above IDR 50 million?",
        "Director approval plus three vendor quotations.",
        chunks(
            "Purchases above IDR 50 million require Director approval and three vendor quotations."
        ),
    )
    assert result.supported, result
