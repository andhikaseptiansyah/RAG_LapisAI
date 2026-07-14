from __future__ import annotations

import json
from pathlib import Path

import api.follow_up_service as follow_up_service
from api.follow_up_service import build_dataset_follow_up_question

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "evaluation" / "ground_truth.json"


def _answerable_questions() -> set[str]:
    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    questions: set[str] = set()
    for item in payload.get("items") or []:
        if item.get("answerable") is not True:
            continue
        question = str(item.get("question") or "").strip()
        if question:
            questions.add(question)
        for variant in item.get("query_variants") or []:
            text = str(variant or "").strip()
            if text:
                questions.add(text)
    return questions


def test_indonesian_password_follow_up_is_grounded_and_related() -> None:
    original_verifier = follow_up_service._question_is_retrievable
    follow_up_service._question_is_retrievable = lambda question, documents: True
    try:
        follow_up = build_dataset_follow_up_question(
            question="Bagaimana prosedur reset password dan berapa lama prosesnya?",
            answer=(
                "Ajukan tiket ke IT Helpdesk melalui portal. "
                "Reset diproses maksimal 1x24 jam."
            ),
            sources=[
                {
                    "document_name": "FAQ_IT_Support.txt",
                    "score": 0.91,
                }
            ],
            language="ID",
        )
    finally:
        follow_up_service._question_is_retrievable = original_verifier

    assert follow_up
    assert follow_up in _answerable_questions()
    assert "password" in follow_up.casefold() or "kredensial" in follow_up.casefold()
    assert "natal" not in follow_up.casefold()
    assert "upah" not in follow_up.casefold()


def test_no_related_dataset_question_returns_none() -> None:
    original_verifier = follow_up_service._question_is_retrievable
    follow_up_service._question_is_retrievable = lambda question, documents: True
    try:
        follow_up = build_dataset_follow_up_question(
            question=(
                "Jika tanggal 25 Desember adalah Hari Raya Natal, pada hari apa "
                "karyawan akan menerima upah bulanan mereka?"
            ),
            answer=(
                "Jika tanggal pembayaran jatuh pada hari libur, gaji dibayarkan "
                "pada hari kerja sebelumnya."
            ),
            sources=[
                {
                    "document_name": "FAQ_Payroll.txt",
                    "score": 0.93,
                }
            ],
            language="ID",
        )
    finally:
        follow_up_service._question_is_retrievable = original_verifier

    # The only payroll benchmark is the question just answered. The system
    # must not fill the empty space with an unrelated recommendation.
    assert follow_up is None



def test_runtime_unanswerable_candidate_is_not_recommended() -> None:
    original_verifier = follow_up_service._question_is_retrievable
    follow_up_service._question_is_retrievable = lambda question, documents: False
    try:
        follow_up = build_dataset_follow_up_question(
            question="Bagaimana prosedur reset password dan berapa lama prosesnya?",
            answer="Ajukan tiket ke IT Helpdesk melalui portal.",
            sources=[{"document_name": "FAQ_IT_Support.txt", "score": 0.91}],
            language="ID",
        )
    finally:
        follow_up_service._question_is_retrievable = original_verifier

    assert follow_up is None

def test_refusal_without_sources_has_no_follow_up() -> None:
    follow_up = build_dataset_follow_up_question(
        question="Berapa anggaran kantor Jepang tahun 2027?",
        answer="Informasi tersebut tidak ditemukan.",
        sources=[],
        language="ID",
    )
    assert follow_up is None


if __name__ == "__main__":
    test_indonesian_password_follow_up_is_grounded_and_related()
    test_no_related_dataset_question_returns_none()
    test_runtime_unanswerable_candidate_is_not_recommended()
    test_refusal_without_sources_has_no_follow_up()
    print("Contextual dataset follow-up tests passed.")
