from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from retrieval.evidence_verifier import verify_evidence
from retrieval.query_expansion import concepts_in_text, expand_query


def assert_supported(question: str, content: str) -> None:
    decision = verify_evidence(question, content)
    assert decision.supported, decision


def assert_rejected(question: str, content: str) -> None:
    decision = verify_evidence(question, content)
    assert not decision.supported, decision


def main() -> None:
    expanded = expand_query(
        "Bagaimana cara mereset kata sandi dan berapa lama prosesnya?"
    ).lower()
    assert "password reset" in expanded
    assert "it helpdesk" in expanded
    assert "processed within" in expanded

    exact_ui_question = (
        "Jika saya lupa password untuk masuk ke sistem internal, apa prosedur "
        "reset yang harus dilakukan dan berapa lama maksimal prosesnya?"
    )
    exact_expanded = expand_query(exact_ui_question).lower()
    assert "forgot password" in exact_expanded
    assert "password reset" in exact_expanded
    assert "it helpdesk" in exact_expanded
    assert "processed within" in exact_expanded
    assert "password_reset" in concepts_in_text(exact_ui_question)

    # Regression: short aliases must not match inside unrelated words.
    assert "rpo" not in concepts_in_text("corporate policy")
    assert "rto" not in concepts_in_text("corporate policy")

    assert_supported(
        "Bagaimana cara mereset kata sandi dan berapa lama prosesnya?",
        "How do I reset my password? Raise a ticket to the IT Helpdesk via "
        "the portal; resets are processed within 1x24 hours.",
    )
    assert_supported(
        exact_ui_question,
        "How do I reset my password? Raise a ticket to the IT Helpdesk via "
        "the portal; resets are processed within 1x24 hours.",
    )
    assert_rejected(
        "Bagaimana cara mereset kata sandi dan berapa lama prosesnya?",
        "Passwords must contain 12 characters, uppercase, lowercase, a number, "
        "and a symbol. Passwords rotate every 90 days.",
    )

    offboarding_question = (
        "Berapa lama batas waktu IT untuk mencabut seluruh akses sistem "
        "karyawan yang keluar?"
    )
    assert_supported(
        offboarding_question,
        "Access Revocation: IT revokes all system access within 2 hours of "
        "the departing employee's exit time.",
    )
    assert_rejected(
        offboarding_question,
        "Access rights are reviewed every 6 months. Dormant accounts are disabled.",
    )

    assert_rejected(
        "Berapa lama cuti melahirkan yang diberikan perusahaan?",
        "Annual leave is 12 days per year and unused leave may be carried over.",
    )
    assert_rejected(
        "Apakah perusahaan memberikan subsidi makan siang di kantin?",
        "The domestic meal per diem is IDR 250,000 per day for business travel.",
    )
    assert_rejected(
        "Berapa pendapatan resmi perusahaan untuk tahun penuh 2026?",
        "Full-year 2025 revenue was IDR 158 billion.",
    )
    assert_rejected(
        "Berapa persen pengurangan konsumsi air di kantor Cikarang pada 2025?",
        "The Cikarang office reduced electricity consumption by 9% in 2025.",
    )
    assert_rejected(
        "Versi minimum macOS apa yang didukung untuk laptop perusahaan?",
        "Submit a request for a new laptop through the IT Service Desk.",
    )

    print("Retrieval improvement tests passed.")


if __name__ == "__main__":
    main()
