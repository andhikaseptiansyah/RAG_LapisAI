from __future__ import annotations

import pytest

from api import chat_service
from retrieval.answerability import apply_answerability_gate
from retrieval.evidence_verifier import verify_chunks, verify_evidence
from retrieval.query_expansion import (
    build_natural_bridge_query,
    concepts_in_text,
    expand_query,
)


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


@pytest.mark.parametrize(
    ("question", "evidence", "expected_concept"),
    [
        (
            "How long are audit logs retained?",
            "Audit and compliance logs are retained for seven years.",
            "audit_retention",
        ),
        (
            "What are the four information-classification levels?",
            "Information classification levels are Public, Internal, Confidential, and Restricted.",
            "classification_levels",
        ),
        (
            "Bagaimana cara memperbarui data rekening bank di sistem HR?",
            "Employees submit updated bank details through the HR portal; the change applies next payroll cycle.",
            "bank_account_update",
        ),
        (
            "Apa yang harus dilakukan jika laptop kantor hilang?",
            "If a company laptop is lost or stolen, report it to IT immediately so it can be remotely wiped.",
            "lost_company_device",
        ),
        (
            "Siapa yang menanggung biaya lisensi software untuk keperluan kerja?",
            "The cost of approved business software licenses is paid from the IT budget.",
            "software_license",
        ),
        (
            "Apa syarat sebelum perangkat pribadi digunakan untuk email kantor?",
            "Personal devices must be registered in mobile device management before accessing corporate email.",
            "byod",
        ),
        (
            "What documents or details should a new employee bring on the first day?",
            "A valid ID, a tax ID (NPWP), and bank account details.",
            "onboarding_documents",
        ),
        (
            "Kapan surat keterangan dokter diperlukan untuk cuti sakit?",
            "A doctor's certificate is required when sick leave exceeds two consecutive days.",
            "medical_certificate",
        ),
    ],
)
def test_known_bilingual_false_refusals_have_explicit_subject_evidence(
    question: str,
    evidence: str,
    expected_concept: str,
) -> None:
    decision = verify_evidence(question, evidence, semantic_score=0.90)
    assert decision.supported is True, decision.reason
    assert expected_concept in decision.matched_concepts


def test_employee_onboarding_rejects_vendor_onboarding_context() -> None:
    question = "What documents or details should a new employee bring on the first day?"
    vendor_evidence = (
        "Vendor onboarding requires a tax ID and bank account details before "
        "the first purchase order is issued."
    )

    decision = verify_evidence(question, vendor_evidence, semantic_score=0.95)

    assert decision.supported is False
    assert "missing_concept:onboarding_documents" in decision.hard_failures
    assert "conflicting_concept:vendor_onboarding" in decision.hard_failures


def test_query_expansion_does_not_append_expected_onboarding_or_classification_answers() -> None:
    onboarding = expand_query(
        "What documents should a new employee bring on the first day?"
    ).casefold()
    classification = expand_query(
        "What are the information-classification levels?"
    ).casefold()

    assert "tax id" not in onboarding
    assert "npwp" not in onboarding
    assert "public internal confidential restricted" not in classification


def test_business_tool_license_wording_is_supported() -> None:
    decision = verify_evidence(
        "Siapa yang menanggung biaya lisensi software untuk keperluan kerja?",
        "Approved business-tool licenses are covered by the IT budget.",
        semantic_score=0.90,
    )

    assert decision.supported is True, decision.reason
    assert "software_license" in decision.matched_concepts


def test_generic_password_question_selects_adjacent_complete_policy_evidence() -> None:
    question = "What are the password requirements?"
    expanded = expand_query(question).casefold()
    assert {"password", "password_complexity", "password_rotation"}.issubset(
        set(concepts_in_text(question))
    )
    assert "12 characters" not in expanded
    assert "90 days" not in expanded

    candidates = verify_chunks(
        question,
        [
            {
                "chunkId": "password-0",
                "chunkIndex": 0,
                "documentName": "Policy_Password.docx",
                "content": (
                    "Passwords must be at least 12 characters and include upper case, "
                    "lower case, a number, and a symbol."
                ),
                "score": 0.88,
                "baseScore": 0.78,
                "semanticScore": 0.85,
            },
            {
                "chunkId": "password-1",
                "chunkIndex": 1,
                "documentName": "Policy_Password.docx",
                "content": "Passwords must be changed every 90 days.",
                "score": 0.83,
                "baseScore": 0.70,
                "semanticScore": 0.82,
            },
        ],
    )

    gated = apply_answerability_gate(question, candidates)
    assert {item["chunkId"] for item in gated} == {"password-0", "password-1"}
    assert all(item["answerabilityStrictlySupported"] is True for item in gated)
