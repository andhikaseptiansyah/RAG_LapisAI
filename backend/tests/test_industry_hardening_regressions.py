from __future__ import annotations

import pytest

from api.answer_formatter import answer_text_only, build_sources
from api.grounding_validator import validate_grounded_answer


def _chunk(evidence: str, document: str = "Policy.docx", score: float = 0.90) -> dict:
    return {
        "chunkId": document,
        "documentName": document,
        "content": evidence,
        "metadata": {"filename": document, "content": evidence},
        "score": score,
        "baseScore": score,
        "semanticScore": score,
        "evidenceSupported": True,
        "evidenceScore": score,
        "evidenceHardFailures": [],
        "evidenceHardContradictions": [],
        "answerabilityAccepted": True,
        "answerabilityEvidenceSelected": True,
        "answerabilityStrictlySupported": True,
        "answerabilityCoherentEvidence": True,
        "answerabilityRequiresCoherentEvidence": False,
        "contextSelected": True,
    }


@pytest.mark.parametrize(
    ("question", "answer", "evidence"),
    [
        (
            "Berapa lama batas waktu IT untuk mencabut seluruh akses sistem karyawan yang keluar?",
            "IT harus mencabut seluruh akses sistem karyawan yang keluar dalam waktu 2 jam setelah waktu keluarnya karyawan.",
            "Departing employees must return all company assets. IT revokes all system access within 2 hours of the employee's exit time.",
        ),
        (
            "Pada tanggal berapa gaji karyawan dibayarkan setiap bulannya?",
            "Gaji karyawan dibayarkan pada tanggal 25 setiap bulannya. Jika tanggal 25 adalah hari libur, pembayaran dilakukan pada hari kerja sebelumnya.",
            "Salaries are paid on the 25th of each month. If the 25th is a holiday, payment is the prior working day.",
        ),
        (
            "Apa yang harus dilakukan jika laptop kantor hilang?",
            "Jika laptop kantor hilang, laporan segera ke IT agar perangkat dapat dihapus secara jarak jauh.",
            "What if I lose my laptop? Report it to IT immediately so the device can be remotely wiped.",
        ),
        (
            "Bagaimana sikap perusahaan terhadap tindakan pelecehan di tempat kerja?",
            "Perusahaan memiliki sikap nol toleransi terhadap tindakan pelecehan di tempat kerja.",
            "Nusantara Dynamics maintains a zero-tolerance stance on harassment of any kind.",
        ),
        (
            "Bagaimana cara karyawan mengungkapkan potensi konflik kepentingan?",
            "Karyawan harus mengungkapkan potensi konflik kepentingan dengan menulis secara langsung kepada HR.",
            "Any potential conflict of interest must be disclosed to HR in writing.",
        ),
        (
            "Berapa hari cuti tahunan yang diberikan kepada karyawan?",
            "Karyawan berhak mendapatkan 12 hari libur tahunan per tahun. Libur tahunan ini diperhitungkan secara bulanan.",
            "Employees are entitled to 12 days of annual leave per year, accruing monthly.",
        ),
        (
            "Siapa saja yang berhak mengajukan kerja jarak jauh (remote work)?",
            "Semua karyawan yang telah dikonfirmasi berhak mengajukan kerja jarak jauh, selama mendapatkan persetujuan atasan.",
            "All confirmed employees are eligible for remote work, subject to manager approval.",
        ),
    ],
)
def test_actual_rejected_bilingual_answers_are_grounded(
    question: str,
    answer: str,
    evidence: str,
) -> None:
    decision = validate_grounded_answer(question, answer, [_chunk(evidence)])
    assert decision.supported is True, decision.to_dict()


@pytest.mark.parametrize(
    ("question", "answer", "evidence", "document"),
    [
        (
            "Untuk pengeluaran sebesar berapa bukti pembayaran asli wajib disertakan?",
            "Bukti pembayaran asli wajib disertakan untuk setiap pengeluaran yang melebihi IDR 150.000.",
            "Original receipts are required for any single expense above IDR 150,000.",
            "SOP_Expense_Reimbursement.pdf",
        ),
        (
            "Berapa kuota ukuran mailbox standar untuk karyawan?",
            "Kuota ukuran mailbox standar untuk karyawan adalah 50 GB.",
            "Q: What is my mailbox size limit? A: The standard mailbox quota is 50 GB.",
            "FAQ_Email_Calendar.txt",
        ),
        (
            "Berapa biaya penggantian kartu akses karyawan yang hilang?",
            "Biaya penggantian kartu akses karyawan yang hilang adalah IDR 50.000. "
            "Penggantian kartu akses dapat dilakukan dengan mengajukan permohonan di meja depan.",
            "Nusantara Dynamics Facilities FAQ. ## Access Card "
            "Q: How do I get a replacement access card? "
            "A: Request one at the front desk; a replacement fee of IDR 50,000 applies. "
            "## Parking Q: Is parking available? "
            "A: Yes, employee parking is available in Basement 2.",
            "FAQ_Facilities.txt",
        ),
        (
            "Bagaimana cara memperbarui data rekening bank di sistem HR?",
            "Cara memperbarui data rekening bank di sistem HR adalah dengan mengajukan "
            "perubahan melalui portal HR; perubahan tersebut berlaku mulai dari siklus "
            "pembayaran berikutnya.",
            "Nusantara Dynamics HR FAQ. ## Payslip "
            "Q: Where do I find my payslip? "
            "A: Payslips are available in the HR portal under My Documents after the 25th. "
            "## Update Bank Q: How do I update my bank account? "
            "A: Submit the change in the HR portal; changes apply from the next payroll cycle.",
            "FAQ_HR.txt",
        ),
        (
            "Apa syarat yang harus dipenuhi sebelum perangkat pribadi digunakan untuk email kantor?",
            "Sebelum perangkat pribadi digunakan untuk email kantor, perangkat tersebut harus "
            "terdaftar dalam sistem manajemen perangkat mobile (MDM).",
            "Personal devices used for work email must be enrolled in the mobile device "
            "management (MDM) system.",
            "Policy_BYOD.docx",
        ),
    ],
)
def test_new_native_answers_pass_strict_citation_validation(
    question: str,
    answer: str,
    evidence: str,
    document: str,
) -> None:
    chunks = [_chunk(evidence, document)]
    decision = validate_grounded_answer(
        question,
        answer,
        chunks,
        minimum_claim_support=0.50,
    )
    assert decision.supported is True, decision.to_dict()
    assert decision.support_score >= 0.50

    sources = build_sources(chunks, question=question, answer=answer, limit=3)
    assert [source["document_name"] for source in sources] == [document]
    assert sources[0]["citation_answer_coverage"] == 1.0


@pytest.mark.parametrize(
    ("answer", "evidence"),
    [
        (
            "Bukti pembayaran asli wajib disertakan untuk pengeluaran di bawah IDR 150.000.",
            "Original receipts are required for any single expense above IDR 150,000.",
        ),
        (
            "Kuota ukuran mailbox standar untuk karyawan adalah 500 GB.",
            "Q: What is my mailbox size limit? A: The standard mailbox quota is 50 GB.",
        ),
        (
            "Kartu akses pengganti dapat diminta di Basement 2.",
            "## Access Card Q: How do I get a replacement access card? "
            "A: Request one at the front desk; a replacement fee of IDR 50,000 applies. "
            "## Parking Q: Is parking available? A: Yes, employee parking is available in Basement 2.",
        ),
        (
            "Penggantian kartu akses dilakukan dengan mengajukan permohonan ke IT Helpdesk.",
            "Q: How do I get a replacement access card? "
            "A: Request one at the front desk; a replacement fee of IDR 50,000 applies.",
        ),
        (
            "Perubahan rekening berlaku mulai dari siklus pembayaran saat ini.",
            "Q: How do I update my bank account? "
            "A: Submit the change in the HR portal; changes apply from the next payroll cycle.",
        ),
        (
            "Perangkat pribadi tidak perlu terdaftar dalam sistem manajemen perangkat mobile (MDM).",
            "Personal devices used for work email must be enrolled in the mobile device "
            "management (MDM) system.",
        ),
    ],
)
def test_new_bilingual_bridges_reject_conflicting_facts_and_relations(
    answer: str,
    evidence: str,
) -> None:
    decision = validate_grounded_answer(
        "",
        answer,
        [_chunk(evidence)],
        minimum_claim_support=0.50,
    )
    assert decision.supported is False, decision.to_dict()


def test_faq_bounding_preserves_standalone_rule_before_first_pair() -> None:
    evidence = (
        "If the 25th is a holiday, payment is the prior working day. "
        "## Overtime Q: How is overtime paid? "
        "A: Approved overtime is paid in the following month's payroll."
    )
    answer = "If the 25th falls on a holiday, salary is paid on the prior working day."
    decision = validate_grounded_answer(
        "When is salary paid if the 25th falls on a holiday?",
        answer,
        [_chunk(evidence, "FAQ_Payroll.txt")],
        minimum_claim_support=0.50,
    )
    assert decision.supported is True, decision.to_dict()


def test_faq_pair_keeps_software_access_subject_bound_to_its_answer() -> None:
    evidence = (
        "## Request Q: How do I get access to a software tool? "
        "A: Request it via the IT Service Desk; the system owner approves. "
        "## License Q: Who pays for software licenses? "
        "A: Approved business-tool licenses are covered by the IT budget."
    )
    answer = (
        "Sistem pemilik menyetujui permintaan akses ke sebuah aplikasi atau software. "
        "Permintaan akses harus diajukan melalui IT Service Desk untuk mendapatkan persetujuan."
    )
    chunks = [_chunk(evidence, "FAQ_Software_Access.txt")]
    decision = validate_grounded_answer(
        "Siapa yang menyetujui permintaan akses ke sebuah aplikasi atau software?",
        answer,
        chunks,
        minimum_claim_support=0.50,
    )
    assert decision.supported is True, decision.to_dict()
    assert build_sources(chunks, question="software access", answer=answer)


@pytest.mark.parametrize(
    ("question", "answer", "evidence"),
    [
        (
            "Who approves this purchase?",
            "A director must approve the purchase.",
            "The department head must approve the purchase.",
        ),
        (
            "How is the conflict disclosed?",
            "The conflict may be disclosed verbally to HR.",
            "The conflict must be disclosed to HR in writing.",
        ),
        (
            "Does a director approve this purchase?",
            "A director approves the purchase.",
            "The department head approves the purchase.",
        ),
    ],
)
def test_semantic_bridge_rejects_conflicts_and_question_leakage(
    question: str,
    answer: str,
    evidence: str,
) -> None:
    assert not validate_grounded_answer(question, answer, [_chunk(evidence)]).supported


def test_answer_text_removes_filename_narration() -> None:
    answer = (
        "The department head approves the purchase. "
        "This is explicitly stated in Policy_Procurement_Threshold.docx."
    )
    assert answer_text_only(answer) == "The department head approves the purchase."


def test_citation_selects_the_locally_bound_procurement_tier() -> None:
    question = "Who approves a purchase valued between IDR 10 million and IDR 50 million?"
    answer = (
        "The purchase valued between IDR 10 million and IDR 50 million "
        "requires approval from the department head."
    )
    chunks = [
        _chunk(
            "Purchases up to IDR 10,000,000 require manager approval. "
            "Purchases above IDR 50,000,000 require Director approval.",
            "SOP_Procurement.pdf",
            0.95,
        ),
        _chunk(
            "Tiers. Below IDR 10,000,000: manager. "
            "IDR 10-50 million: department head. "
            "Above IDR 50,000,000: Director.",
            "Policy_Procurement_Threshold.docx",
            0.85,
        ),
    ]
    sources = build_sources(chunks, question=question, answer=answer, limit=3)
    assert [source["document_name"] for source in sources] == [
        "Policy_Procurement_Threshold.docx"
    ]

    tier_evidence = [chunks[1]]
    assert validate_grounded_answer(
        question,
        "Department head approval is required.",
        tier_evidence,
    ).supported
    assert not validate_grounded_answer(
        question,
        "Director approval is required.",
        tier_evidence,
    ).supported


def test_citation_requires_the_source_that_supports_every_vpn_claim() -> None:
    question = "Aplikasi apa yang digunakan untuk koneksi VPN dan apakah MFA diwajibkan?"
    answer = (
        "Aplikasi yang digunakan untuk koneksi VPN adalah WireGuard. "
        "MFA diwajibkan untuk akses VPN."
    )
    chunks = [
        _chunk(
            "MFA is mandatory for all email and VPN access.",
            "Policy_Password.docx",
            0.95,
        ),
        _chunk(
            "Employees connect using the WireGuard client. "
            "MFA VPN access requires multi-factor authentication.",
            "TECH_VPN_Setup.txt",
            0.85,
        ),
    ]
    sources = build_sources(chunks, question=question, answer=answer, limit=3)
    assert sources[0]["document_name"] == "TECH_VPN_Setup.txt"
    assert sources[0]["citation_answer_coverage"] == 1.0


def test_compact_and_expanded_money_values_bind_to_the_same_tier() -> None:
    question = "What approval is needed for a purchase above IDR 50 million?"
    evidence = (
        "Purchases up to IDR 10,000,000 require manager approval. "
        "Purchases above IDR 50,000,000 require Director approval."
    )
    chunks = [_chunk(evidence)]
    assert validate_grounded_answer(
        question,
        "Director approval is required.",
        chunks,
    ).supported
    assert not validate_grounded_answer(
        question,
        "Manager approval is required.",
        chunks,
    ).supported
