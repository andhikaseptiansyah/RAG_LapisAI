from __future__ import annotations

import pytest

from api.answer_formatter import build_sources
from api.grounding_validator import validate_grounded_answer


def _chunks(document: str, *contents: str) -> list[dict]:
    return [
        {
            "chunkId": f"{document}-{index}",
            "chunkIndex": index,
            "documentName": document,
            "content": content,
            "metadata": {"filename": document, "content": content, "chunk_index": index},
            "score": 0.90,
            "baseScore": 0.85,
            "semanticScore": 0.80,
            "evidenceSupported": True,
            "evidenceScore": 0.90,
            "evidenceHardFailures": [],
            "evidenceHardContradictions": [],
            "answerabilityAccepted": True,
            "answerabilityEvidenceSelected": True,
            "answerabilityStrictlySupported": True,
            "answerabilityCoherentEvidence": True,
            "answerabilityRequiresCoherentEvidence": False,
            "contextSelected": True,
        }
        for index, content in enumerate(contents)
    ]


@pytest.mark.parametrize(
    ("question", "answer", "document", "evidence"),
    [
        (
            "Berapa maksimum sisa cuti tahunan yang boleh dibawa ke tahun berikutnya?",
            "Maksimum enam hari cuti yang tidak terpakai dapat dibawa ke tahun berikutnya.",
            "Policy_Leave.docx",
            ("A maximum of 6 unused leave days may be carried over to the next year.",),
        ),
        (
            "Berapa banyak tanggungan yang dicakup oleh asuransi kesehatan perusahaan?",
            "Asuransi kesehatan perusahaan mencakup karyawan dan hingga 3 orang tanggungan.",
            "FAQ_Benefits.txt",
            ("Employees and up to 3 dependents are covered by the company health insurance plan.",),
        ),
        (
            "Bagaimana cara membagikan kalender kepada rekan kerja?",
            "Gunakan opsi calendar sharing dan berikan akses lihat (view access) kepada rekan kerja terkait.",
            "FAQ_Email_Calendar.txt",
            ("Use the calendar sharing option and grant view access to the relevant coworkers.",),
        ),
        (
            "Di mana karyawan dapat menemukan slip gaji mereka?",
            "Slip gaji tersedia di HR portal pada bagian My Documents setelah tanggal 25.",
            "FAQ_HR.txt",
            ("Payslips are available in the HR portal under My Documents after the 25th.",),
        ),
        (
            "Pada tanggal berapa gaji karyawan dibayarkan setiap bulannya?",
            "Gaji dibayarkan pada tanggal 25 setiap bulan.",
            "FAQ_Payroll.txt",
            ("Salaries are paid on the 25th of each month.",),
        ),
        (
            "Kapan lembur yang telah disetujui akan dibayarkan?",
            "Lembur yang telah disetujui dibayarkan pada siklus payroll bulan berikutnya.",
            "FAQ_Payroll.txt",
            ("Approved overtime is paid in the next monthly payroll cycle.",),
        ),
        (
            "Berapa hari maksimal karyawan diperbolehkan bekerja dari rumah dalam seminggu?",
            "Karyawan diperbolehkan bekerja dari rumah maksimal 2 hari per minggu dengan persetujuan manajer.",
            "Policy_WFH.docx",
            ("Employees may work from home a maximum of 2 days per week, with manager approval.",),
        ),
        (
            "Bagaimana sikap perusahaan terhadap tindakan pelecehan di tempat kerja?",
            (
                "Perusahaan menerapkan kebijakan tanpa toleransi (zero tolerance) terhadap segala "
                "bentuk pelecehan, dan keluhan dapat dilaporkan secara rahasia ke HR atau melalui "
                "jalur whistleblower."
            ),
            "Policy_Anti_Harassment.docx",
            (
                "The company has zero tolerance for all forms of harassment.",
                "Complaints can be raised confidentially to HR or via the whistleblower channel.",
            ),
        ),
        (
            "Apa syarat yang harus dipenuhi sebelum perangkat pribadi digunakan untuk email kantor?",
            "Perangkat pribadi harus didaftarkan terlebih dahulu ke sistem mobile device management (MDM).",
            "Policy_BYOD.docx",
            ("Personal devices used for work email must be enrolled in the mobile device management (MDM) system.",),
        ),
        (
            "Apakah perusahaan berhak menghapus data dari perangkat pribadi karyawan?",
            (
                "Ya, perusahaan berhak melakukan remote wipe untuk menghapus data korporat dari "
                "perangkat yang telah terdaftar."
            ),
            "Policy_BYOD.docx",
            ("The company reserves the right to remotely wipe corporate data from enrolled devices.",),
        ),
        (
            "Bagaimana cara karyawan mengungkapkan potensi konflik kepentingan?",
            "Potensi konflik kepentingan harus diungkapkan secara tertulis kepada HR.",
            "Policy_Code_of_Conduct.docx",
            ("Any potential conflict of interest must be disclosed to HR in writing.",),
        ),
        (
            "Berapa hari cuti tahunan yang diberikan kepada karyawan?",
            "Karyawan berhak atas 12 hari cuti tahunan per tahun, yang terakumulasi setiap bulan.",
            "Policy_Leave.docx",
            ("Employees are entitled to 12 days of annual leave per year, accruing monthly.",),
        ),
        (
            "Kapan surat keterangan dokter diperlukan untuk cuti sakit?",
            "Surat keterangan dokter diperlukan jika cuti sakit lebih dari 2 hari berturut-turut.",
            "Policy_Leave.docx",
            ("Sick leave beyond 2 consecutive days requires a doctor's certificate.",),
        ),
        (
            "Apa saja persyaratan panjang dan kompleksitas kata sandi perusahaan?",
            (
                "Kata sandi harus terdiri dari minimal 12 karakter, mencakup huruf besar, huruf "
                "kecil, angka, dan simbol."
            ),
            "Policy_Password.docx",
            ("Passwords must be at least 12 characters and include upper case, lower case, a number, and a symbol.",),
        ),
        (
            "Siapa yang menyetujui pembelian dengan nilai di bawah IDR 10.000.000?",
            "Pembelian dengan nilai di bawah IDR 10.000.000 disetujui oleh manajer.",
            "Policy_Procurement_Threshold.docx",
            ("Below IDR 10,000,000: Manager approval.",),
        ),
        (
            "Siapa saja yang berhak mengajukan kerja jarak jauh (remote work)?",
            (
                "Seluruh karyawan tetap (confirmed employees) berhak bekerja jarak jauh, dengan "
                "persetujuan manajer."
            ),
            "Policy_WFH.docx",
            ("All confirmed employees are eligible for remote work, subject to manager approval.",),
        ),
    ],
)
def test_indonesian_answers_are_grounded_by_equivalent_english_evidence(
    question: str,
    answer: str,
    document: str,
    evidence: tuple[str, ...],
) -> None:
    chunks = _chunks(document, *evidence)
    decision = validate_grounded_answer(question, answer, chunks)

    assert decision.supported is True, decision.to_dict()
    assert build_sources(chunks, question=question, answer=answer)


@pytest.mark.parametrize(
    ("question", "answer", "evidence"),
    [
        (
            "Kapan surat keterangan dokter diperlukan untuk cuti sakit?",
            "Surat keterangan dokter diperlukan jika cuti sakit lebih dari 3 hari berturut-turut.",
            "Sick leave beyond 2 consecutive days requires a doctor's certificate.",
        ),
        (
            "Siapa yang menyetujui pembelian dengan nilai di bawah IDR 10.000.000?",
            "Pembelian dengan nilai di bawah IDR 10.000.000 disetujui oleh direktur.",
            "Below IDR 10,000,000: Manager approval.",
        ),
        (
            "Apakah perusahaan berhak menghapus data dari perangkat pribadi karyawan?",
            "Perusahaan berhak melakukan remote wipe karena cara ini lebih aman.",
            "The company reserves the right to remotely wipe corporate data from enrolled devices.",
        ),
    ],
)
def test_bilingual_bridge_still_rejects_unsupported_facts(
    question: str,
    answer: str,
    evidence: str,
) -> None:
    decision = validate_grounded_answer(
        question,
        answer,
        _chunks("Policy.docx", evidence),
    )
    assert decision.supported is False
