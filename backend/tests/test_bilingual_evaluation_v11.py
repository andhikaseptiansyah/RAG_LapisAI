from __future__ import annotations

import pytest

from api import chat_service
from retrieval.evidence_verifier import verify_evidence
from retrieval.query_expansion import build_natural_bridge_query


def _candidate(*, chunk_id: str, score: float, strict: bool) -> dict:
    return {
        "chunkId": chunk_id,
        "documentName": f"{chunk_id}.txt",
        "content": "supporting evidence",
        "score": score,
        "baseScore": score,
        "evidenceSupported": strict,
        "answerabilityAccepted": True,
        "answerabilityEvidenceSelected": strict,
        "answerabilityStrictlySupported": strict,
        "answerabilityCoherentEvidence": strict,
        "answerabilityRequiresCoherentEvidence": True,
        "evidenceHardFailures": [],
        "evidenceHardContradictions": [],
    }


def test_primary_retrieval_returns_only_strict_generation_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    non_strict = _candidate(chunk_id="wrong-high", score=0.99, strict=False)
    strict = _candidate(chunk_id="correct-lower", score=0.78, strict=True)

    monkeypatch.setattr(
        chat_service,
        "hybrid_search",
        lambda *args, **kwargs: [non_strict, strict],
    )

    candidates, mode, query = chat_service._retrieve_with_language_fallback(
        "What are the password requirements?",
        top_k=5,
    )

    assert mode == "original"
    assert query == "What are the password requirements?"
    assert [item["chunkId"] for item in candidates] == ["correct-lower"]


@pytest.mark.parametrize(
    ("question", "expected_bridge"),
    [
        ("Bagaimana cara membagikan kalender kepada rekan kerja?", "share a calendar"),
        ("Berapa biaya penggantian kartu akses karyawan yang hilang?", "replacement fee"),
        ("Di mana lokasi parkir karyawan tersedia?", "employee parking"),
        ("Bagaimana cara memperbarui data rekening bank di sistem HR?", "update bank account"),
        ("Apa saja yang harus dibawa karyawan baru pada hari pertama kerja?", "first day"),
        ("Pada tanggal berapa gaji karyawan dibayarkan setiap bulannya?", "salaries paid"),
        ("Apa yang harus dilakukan karyawan jika menerima email mencurigakan?", "suspicious email"),
        ("Apa yang harus dilakukan jika laptop kantor hilang?", "company laptop is lost"),
        ("Siapa yang menyetujui permintaan akses ke sebuah aplikasi atau software?", "approves"),
        ("Berapa tunjangan satu kali untuk perlengkapan kerja dari rumah?", "home-office allowance"),
        ("Apakah perusahaan berhak menghapus data dari perangkat pribadi karyawan?", "remotely wipe"),
        ("Berapa lama siklus penggantian kata sandi dan apakah kata sandi lama boleh dipakai ulang?", "previous passwords"),
    ],
)
def test_indonesian_enterprise_intents_receive_answer_free_english_bridge(
    question: str,
    expected_bridge: str,
) -> None:
    bridge = build_natural_bridge_query(question)
    assert expected_bridge.casefold() in bridge.casefold()
    assert bridge != question


def test_indonesian_password_reset_morphology_is_supported() -> None:
    question = "Bagaimana cara mereset kata sandi dan berapa lama prosesnya?"
    evidence = (
        "Untuk mereset kata sandi, ajukan tiket ke IT Helpdesk melalui portal. "
        "Proses selesai dalam waktu satu hari."
    )
    decision = verify_evidence(question, evidence, semantic_score=0.85)
    assert decision.supported is True
    assert "password_reset" in decision.matched_concepts


def test_indonesian_access_revocation_morphology_is_supported() -> None:
    question = "Berapa lama batas waktu IT untuk mencabut seluruh akses sistem karyawan yang keluar?"
    evidence = (
        "Saat offboarding, IT mencabut seluruh akses sistem karyawan dalam waktu dua jam."
    )
    decision = verify_evidence(question, evidence, semantic_score=0.85)
    assert decision.supported is True
    assert "access_revocation" in decision.matched_concepts
