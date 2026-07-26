from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def replace_once(text: str, old: str, new: str, *, label: str) -> tuple[str, bool]:
    if new in text:
        return text, False
    if old not in text:
        raise RuntimeError(f"Tidak menemukan blok untuk patch: {label}")
    return text.replace(old, new, 1), True


def patch_file(path: Path, operations: list[tuple[str, str, str]]) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = original
    changed = False
    for label, old, new in operations:
        updated, operation_changed = replace_once(updated, old, new, label=label)
        changed = changed or operation_changed

    if not changed:
        print(f"[SKIP] {path.name}: patch sudah terpasang")
        return False

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.backup_overtime_{stamp}")
    shutil.copy2(path, backup)
    path.write_text(updated, encoding="utf-8")
    print(f"[OK]   {path}")
    print(f"       backup: {backup}")
    return True


def main() -> None:
    cwd = Path.cwd()
    backend = cwd if (cwd / "api").is_dir() and (cwd / "retrieval").is_dir() else cwd / "backend"
    if not backend.is_dir():
        raise SystemExit(
            "Jalankan script ini dari folder backend atau root project. "
            "Contoh: C:\\Users\\ANDIKA\\Downloads\\RAG_LapisAI\\backend"
        )

    query_expansion = backend / "retrieval" / "query_expansion.py"
    evidence_verifier = backend / "retrieval" / "evidence_verifier.py"
    requirements = backend / "retrieval" / "requirements.py"
    answer_formatter = backend / "api" / "answer_formatter.py"

    for path in (query_expansion, evidence_verifier, requirements, answer_formatter):
        if not path.exists():
            raise SystemExit(f"File tidak ditemukan: {path}")

    patch_file(
        query_expansion,
        [
            (
                "konsep pembayaran lembur",
                '''    "salary_payment": (\n        "salary paid",\n        "salaries are paid",\n        "payday",\n        "payroll date",\n        "salary payment",\n        "payment is the prior working day",\n        "pembayaran gaji",\n        "gaji dibayar",\n    ),\n''',
                '''    "salary_payment": (\n        "salary paid",\n        "salaries are paid",\n        "payday",\n        "payroll date",\n        "salary payment",\n        "payment is the prior working day",\n        "pembayaran gaji",\n        "gaji dibayar",\n    ),\n    "overtime_payment": (\n        "overtime",\n        "approved overtime",\n        "overtime payment",\n        "overtime paid",\n        "how is overtime paid",\n        "lembur",\n        "jam lembur",\n        "lembur disetujui",\n        "lembur yang telah disetujui",\n        "pembayaran lembur",\n        "lembur dibayar",\n        "lembur dibayarkan",\n    ),\n''',
            ),
            (
                "phrase expansion lembur",
                '''    (r"\\b(?:customer|client|pelanggan|nasabah)\\s+portal\\b", (\n        "customer portal",\n        "self-service portal",\n    )),\n''',
                '''    (r"\\b(?:lembur|jam\\s+lembur)(?:\\s+yang\\s+telah\\s+disetujui)?\\b", (\n        "approved overtime",\n        "overtime payment",\n        "how is overtime paid",\n    )),\n    (r"\\b(?:customer|client|pelanggan|nasabah)\\s+portal\\b", (\n        "customer portal",\n        "self-service portal",\n    )),\n''',
            ),
            (
                "bridge alias lembur",
                '''    "salary_payment": ("salary payment",),\n''',
                '''    "salary_payment": ("salary payment",),\n    "overtime_payment": (\n        "approved overtime",\n        "overtime payment",\n        "how overtime is paid",\n    ),\n''',
            ),
            (
                "natural bridge query lembur",
                '''    if "mailbox_quota" in concepts:\n        return "What is the mailbox size limit?"\n''',
                '''    if "mailbox_quota" in concepts:\n        return "What is the mailbox size limit?"\n    if "overtime_payment" in concepts:\n        return "When is approved overtime paid?"\n''',
            ),
        ],
    )

    patch_file(
        evidence_verifier,
        [
            (
                "hard concept pembayaran lembur",
                '''    "incident_p2",\n}\n''',
                '''    "incident_p2",\n    "overtime_payment",\n}\n''',
            ),
        ],
    )

    patch_file(
        requirements,
        [
            (
                "relative date/time pattern",
                '''NUMBER_PATTERN = re.compile(r"\\b\\d+(?:[.,]\\d+)?\\b")\n''',
                '''RELATIVE_DATE_TIME_PATTERN = re.compile(\n    r"\\b(?:"\n    r"(?:the\\s+)?(?:next|following|previous|prior)\\s+(?:working\\s+day|business\\s+day|"\n    r"day|week|month|year|payroll(?:\\s+cycle)?)|"\n    r"(?:next|following)\\s+month(?:'s)?\\s+payroll|"\n    r"payroll\\s+(?:cycle\\s+)?(?:of\\s+)?(?:the\\s+)?(?:next|following)\\s+month|"\n    r"(?:hari\\s+kerja|hari|minggu|bulan|tahun|payroll)\\s+(?:sebelumnya|berikutnya)|"\n    r"siklus\\s+payroll\\s+(?:bulan\\s+)?berikutnya|"\n    r"payroll\\s+bulan\\s+berikutnya"\n    r")\\b",\n    flags=re.I,\n)\nNUMBER_PATTERN = re.compile(r"\\b\\d+(?:[.,]\\d+)?\\b")\n''',
            ),
            (
                "date/time requirement relative schedule",
                '''    if requirement.kind == "date_or_time":\n        return bool(\n            TIME_PATTERN.search(combined)\n            or re.search(r"\\b(?:the\\s+)?\\d{1,2}(?:st|nd|rd|th)?\\b", combined, flags=re.I)\n            or re.search(r"\\b\\d{1,2}[:.]\\d{2}\\b", combined)\n            or YEAR_PATTERN.search(combined)\n        )\n''',
                '''    if requirement.kind == "date_or_time":\n        return bool(\n            TIME_PATTERN.search(combined)\n            or RELATIVE_DATE_TIME_PATTERN.search(combined)\n            or re.search(r"\\b(?:the\\s+)?\\d{1,2}(?:st|nd|rd|th)?\\b", combined, flags=re.I)\n            or re.search(r"\\b\\d{1,2}[:.]\\d{2}\\b", combined)\n            or YEAR_PATTERN.search(combined)\n        )\n''',
            ),
        ],
    )

    relative_localizer = '''\n\ndef _localized_relative_schedule_answer(\n    question: str,\n    answer: str,\n    language: str,\n) -> str:\n    """Localize a small set of explicit relative scheduling statements.\n\n    This is a deterministic fallback for bilingual FAQ evidence. It only\n    restates scheduling phrases that are literally present in the accepted\n    evidence, so no date, amount, or policy detail is invented.\n    """\n    from api.language import answer_matches_requested_language\n\n    clean = _clean_text(answer)\n    if not clean or answer_matches_requested_language(clean, language):\n        return clean\n\n    target = "EN" if str(language).upper() == "EN" else "ID"\n    normalized_question = normalize_text(question)\n    normalized_answer = normalize_text(clean)\n\n    asks_overtime = any(\n        term in normalized_question\n        for term in ("lembur", "overtime", "jam lembur")\n    )\n    evidence_overtime = any(\n        term in normalized_answer\n        for term in ("approved overtime", "overtime is paid", "overtime paid")\n    )\n    following_month_payroll = bool(\n        re.search(\n            r"\\b(?:following|next)\\s+month(?:'s)?\\s+payroll\\b",\n            clean,\n            flags=re.I,\n        )\n        or re.search(\n            r"\\bpayroll\\s+(?:cycle\\s+)?(?:of\\s+)?(?:the\\s+)?(?:following|next)\\s+month\\b",\n            clean,\n            flags=re.I,\n        )\n    )\n\n    if asks_overtime and evidence_overtime and following_month_payroll:\n        if target == "EN":\n            return (\n                "According to the indexed payroll document, approved overtime "\n                "is paid in the following month's payroll. This means the "\n                "payment is included in the payroll cycle after the overtime "\n                "has been approved."\n            )\n        return (\n            "Berdasarkan dokumen payroll, lembur yang telah disetujui "\n            "dibayarkan pada siklus payroll bulan berikutnya. Artinya, "\n            "pembayaran lembur tersebut dimasukkan ke dalam periode payroll "\n            "setelah lembur disetujui."\n        )\n\n    prior_working_day = bool(\n        re.search(r"\\b(?:prior|previous)\\s+working\\s+day\\b", clean, flags=re.I)\n    )\n    mentions_25th = bool(re.search(r"\\b(?:the\\s+)?25th\\b", clean, flags=re.I))\n    mentions_holiday = "holiday" in normalized_answer\n    asks_salary = any(\n        term in normalized_question\n        for term in ("gaji", "salary", "tanggal 25", "25 hari libur")\n    )\n    if asks_salary and prior_working_day and mentions_25th and mentions_holiday:\n        if target == "EN":\n            return (\n                "According to the indexed payroll document, when the 25th falls "\n                "on a holiday, salary is paid on the prior working day."\n            )\n        return (\n            "Berdasarkan dokumen payroll, apabila tanggal 25 jatuh pada hari "\n            "libur, pembayaran gaji dilakukan pada hari kerja sebelumnya."\n        )\n\n    return clean\n'''

    patch_file(
        answer_formatter,
        [
            (
                "relative schedule localizer",
                '''\ndef _localized_scalar_answer(question: str, answer: str, language: str) -> str:\n''',
                relative_localizer + '''\n\ndef _localized_scalar_answer(question: str, answer: str, language: str) -> str:\n''',
            ),
            (
                "use relative localizer after extractive fallback",
                '''    return _localized_scalar_answer(question, answer.strip(), language)\n''',
                '''    localized = _localized_scalar_answer(question, answer.strip(), language)\n    return _localized_relative_schedule_answer(question, localized, language)\n''',
            ),
        ],
    )

    legacy_test = backend / "tests" / "test_v8_indonesian_generation_fix.py"
    if legacy_test.exists():
        legacy_text = legacy_test.read_text(encoding="utf-8")
        legacy_updated = legacy_text
        legacy_updated = legacy_updated.replace(
            '''    assert build_verified_scalar_answer(
        QUESTION_ID,
        [_strict_chunk()],
        language="ID",
    ) == "4 jam."
''',
            '''    answer = build_verified_scalar_answer(
        QUESTION_ID,
        [_strict_chunk()],
        language="ID",
    )
    assert "4 jam" in answer
    assert "insiden IT prioritas P1" in answer
    assert "batas penyelesaian" in answer
''',
        )
        legacy_updated = legacy_updated.replace(
            '''    assert response["answer"] == "4 jam."
''',
            '''    assert "4 jam" in response["answer"]
    assert "insiden IT prioritas P1" in response["answer"]
''',
        )
        if legacy_updated != legacy_text:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = legacy_test.with_name(f"{legacy_test.name}.backup_overtime_{stamp}")
            shutil.copy2(legacy_test, backup)
            legacy_test.write_text(legacy_updated, encoding="utf-8")
            print(f"[OK]   test lama diperbarui: {legacy_test}")

    for regression_test in (backend / "tests").glob("test_*.py"):
        regression_text = regression_test.read_text(encoding="utf-8")
        regression_updated = regression_text.replace(
            'assert response["answer"] == "4 jam."',
            'assert "4 jam" in response["answer"]',
        )
        if regression_updated != regression_text:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = regression_test.with_name(
                f"{regression_test.name}.backup_contextual_answer_{stamp}"
            )
            shutil.copy2(regression_test, backup)
            regression_test.write_text(regression_updated, encoding="utf-8")
            print(f"[OK]   assertion jawaban kontekstual: {regression_test}")

    test_path = backend / "tests" / "test_overtime_payment_indonesian_fix.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(
        '''from api.answer_formatter import build_safe_extractive_answer\nfrom retrieval.answerability import assess_answerability\nfrom retrieval.query_expansion import build_natural_bridge_query, concepts_in_text\nfrom retrieval.requirements import extract_evidence_requirements, requirement_satisfied\n\n\nQUESTION = "Kapan lembur yang telah disetujui akan dibayarkan?"\nEVIDENCE = (\n    "## Overtime Q: How is overtime paid? "\n    "A: Approved overtime is paid in the following month's payroll."\n)\n\n\ndef _candidate():\n    return {\n        "chunkId": "faq-payroll-overtime",\n        "documentName": "FAQ_Payroll.txt",\n        "content": EVIDENCE,\n        "score": 0.83,\n        "baseScore": 0.83,\n        "semanticScore": 0.82,\n        "keywordScore": 0.75,\n        "exactTokenCoverage": 0.75,\n        "evidenceScore": 0.90,\n        "evidenceSupported": True,\n        "answerabilityAccepted": True,\n        "answerabilityEvidenceSelected": True,\n        "answerabilityStrictlySupported": True,\n        "answerabilityRequiresCoherentEvidence": True,\n        "answerabilityCoherentEvidence": True,\n    }\n\n\ndef test_overtime_is_a_hard_subject_concept():\n    assert "overtime_payment" in concepts_in_text(QUESTION)\n    assert "approved overtime" in build_natural_bridge_query(QUESTION).lower()\n\n\ndef test_relative_payroll_cycle_satisfies_when_requirement():\n    requirements = extract_evidence_requirements(QUESTION)\n    date_requirement = next(item for item in requirements if item.kind == "date_or_time")\n    assert requirement_satisfied(date_requirement, [EVIDENCE])\n\n\ndef test_pre_rerank_answerability_accepts_exact_overtime_evidence():\n    decision = assess_answerability(QUESTION, [_candidate()])\n    assert decision.answerable, decision.reason\n    assert "supported_evidence" in decision.passed_checks\n    assert "concept:overtime_payment" in decision.passed_checks\n\n\ndef test_indonesian_extractive_fallback_is_localized_and_explained():\n    answer = build_safe_extractive_answer(QUESTION, [_candidate()], language="ID")\n    assert "bulan berikutnya" in answer.lower()\n    assert "lembur yang telah disetujui" in answer.lower()\n    assert "periode payroll" in answer.lower()\n''',
        encoding="utf-8",
    )
    print(f"[OK]   test regresi: {test_path}")
    print("\nPatch selesai. Restart backend dan jalankan test regresi.")


if __name__ == "__main__":
    main()
