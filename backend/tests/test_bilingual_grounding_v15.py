from __future__ import annotations

import pytest

from api.answer_formatter import build_sources
from api.grounding_validator import validate_grounded_answer


def _chunk(evidence: str) -> dict:
    return {
        "chunkId": "evidence-1",
        "documentName": "Policy.docx",
        "content": evidence,
        "metadata": {"filename": "Policy.docx", "content": evidence},
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


@pytest.mark.parametrize(
    ("question", "answer", "evidence"),
    [
        (
            "Di mana karyawan dapat menemukan slip gaji mereka?",
            (
                "Slip gaji bisa diakses melalui portal HR pada menu My Documents "
                "sesudah tanggal 25."
            ),
            (
                "Payslips are available in the HR portal under My Documents "
                "after the 25th."
            ),
        ),
        (
            "Pada tanggal berapa gaji karyawan dibayarkan setiap bulannya?",
            "Gaji masuk setiap bulan pada tanggal 25.",
            "Salaries are paid on the 25th of each month.",
        ),
        (
            "Berapa hari maksimal karyawan diperbolehkan bekerja dari rumah dalam seminggu?",
            (
                "Izin kerja dari rumah dibatasi paling banyak dua hari dalam "
                "seminggu dan memerlukan persetujuan manajer."
            ),
            (
                "Employees may work from home a maximum of 2 days per week, "
                "with manager approval."
            ),
        ),
        (
            "Apa yang harus dilakukan jika laptop kantor hilang?",
            (
                "Laporkan segera ke IT agar perangkat dapat dihapus datanya dari "
                "jarak jauh (remote wipe)."
            ),
            "Report it to IT immediately so the device can be remotely wiped.",
        ),
        (
            "Apakah perusahaan berhak menghapus data dari perangkat pribadi karyawan?",
            (
                "Ya. Perusahaan dapat menghapus data korporat dari gawai pribadi "
                "yang terdaftar melalui remote wipe."
            ),
            (
                "The company reserves the right to remotely wipe corporate data "
                "from enrolled devices."
            ),
        ),
        (
            "Bagaimana cara karyawan mengungkapkan potensi konflik kepentingan?",
            (
                "Karyawan wajib menyampaikan potensi benturan kepentingan kepada "
                "HR secara tertulis."
            ),
            (
                "Any potential conflict of interest must be disclosed to HR in "
                "writing."
            ),
        ),
        (
            "Berapa hari cuti tahunan yang diberikan kepada karyawan?",
            (
                "Jatah cuti tahunan adalah 12 hari per tahun dan diakumulasi "
                "tiap bulan."
            ),
            (
                "Employees are entitled to 12 days of annual leave per year, "
                "accruing monthly."
            ),
        ),
        (
            "Berapa batas maksimum biaya hotel per malam untuk perjalanan dinas domestik?",
            (
                "Biaya hotel dibatasi maksimal IDR 800.000 per malam untuk "
                "perjalanan dinas domestik."
            ),
            (
                "Hotel cost is capped at IDR 800,000 per night for domestic "
                "travel."
            ),
        ),
        (
            "Siapa saja yang berhak mengajukan kerja jarak jauh (remote work)?",
            (
                "Semua pegawai tetap dapat mengajukan kerja jarak jauh setelah "
                "mendapat persetujuan manajer."
            ),
            (
                "All confirmed employees are eligible for remote work, subject "
                "to manager approval."
            ),
        ),
        (
            "What are the password requirements?",
            (
                "Passwords must contain at least 12 characters, including "
                "uppercase and lowercase letters, a number, and a symbol, and "
                "must be changed every 90 days."
            ),
            (
                "Passwords must be at least 12 characters and include upper "
                "case, lower case, a number, and a symbol. Passwords must be "
                "changed every 90 days."
            ),
        ),
    ],
)
def test_natural_bilingual_policy_answers_receive_valid_citations(
    question: str,
    answer: str,
    evidence: str,
) -> None:
    chunks = [_chunk(evidence)]
    decision = validate_grounded_answer(question, answer, chunks)

    assert decision.supported is True, decision.to_dict()
    assert build_sources(chunks, question=question, answer=answer)


@pytest.mark.parametrize(
    ("question", "answer", "evidence"),
    [
        (
            "Pada tanggal berapa gaji karyawan dibayarkan setiap bulannya?",
            "Gaji dibayarkan tanggal 24 setiap bulan.",
            "Salaries are paid on the 25th of each month.",
        ),
        (
            "Berapa hari maksimal karyawan boleh bekerja dari rumah?",
            (
                "Karyawan boleh bekerja dari rumah maksimal 3 hari per minggu "
                "dengan persetujuan manajer."
            ),
            (
                "Employees may work from home a maximum of 2 days per week, "
                "with manager approval."
            ),
        ),
        (
            "Apa yang harus dilakukan jika laptop kantor hilang?",
            "Laporkan segera ke HR agar perangkat dapat dihapus dari jarak jauh.",
            "Report it to IT immediately so the device can be remotely wiped.",
        ),
        (
            "Bagaimana cara mengungkapkan konflik kepentingan?",
            "Konflik kepentingan disampaikan secara lisan kepada HR.",
            (
                "Any potential conflict of interest must be disclosed to HR in "
                "writing."
            ),
        ),
        (
            "Berapa batas maksimum biaya hotel per malam?",
            "Biaya hotel maksimal IDR 900.000 per malam.",
            "Hotel cost is capped at IDR 800,000 per night.",
        ),
        (
            "What are the password requirements?",
            "Passwords need 8 characters and must change every 60 days.",
            (
                "Passwords must be at least 12 characters and include upper "
                "case, lower case, a number, and a symbol. Passwords must be "
                "changed every 90 days."
            ),
        ),
        (
            "Apakah perusahaan boleh melakukan remote wipe?",
            (
                "Perusahaan berhak melakukan remote wipe karena cara ini lebih "
                "aman."
            ),
            (
                "The company reserves the right to remotely wipe corporate data "
                "from enrolled devices."
            ),
        ),
    ],
)
def test_bilingual_policy_bridge_rejects_wrong_or_invented_details(
    question: str,
    answer: str,
    evidence: str,
) -> None:
    decision = validate_grounded_answer(question, answer, [_chunk(evidence)])
    assert decision.supported is False
