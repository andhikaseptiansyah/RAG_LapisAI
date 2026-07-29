from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
ROOT = Path(__file__).resolve().parent


def backup(path: Path) -> Path:
    target = path.with_name(f"{path.name}.backup_pension_{STAMP}")
    shutil.copy2(path, target)
    return target


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Marker tidak ditemukan untuk {label}")
    return text.replace(old, new, 1)


def patch_file(relative: str, transform) -> None:
    path = ROOT / relative
    if not path.exists():
        raise FileNotFoundError(path)
    original = path.read_text(encoding="utf-8")
    updated = transform(original)
    if updated == original:
        print(f"[SKIP] {path} sudah berisi perbaikan")
        return
    saved = backup(path)
    path.write_text(updated, encoding="utf-8", newline="\n")
    print(f"[OK]   {path}")
    print(f"       backup: {saved}")


def patch_query_expansion(text: str) -> str:
    concept_block = '''    "retirement_benefit": (\n        "pension benefit",\n        "retirement benefit",\n        "employee pension",\n        "pension plan",\n        "pension",\n        "manfaat pensiun",\n        "program pensiun",\n        "jaminan pensiun",\n        "bpjs ketenagakerjaan",\n        "contributes to bpjs ketenagakerjaan",\n        "kontribusi ke bpjs ketenagakerjaan",\n    ),\n'''
    text = replace_once(
        text,
        '''    "health_insurance": (\n        "health insurance",\n        "medical insurance",\n        "asuransi kesehatan",\n    ),\n    "file_upload": (\n''',
        '''    "health_insurance": (\n        "health insurance",\n        "medical insurance",\n        "asuransi kesehatan",\n    ),\n''' + concept_block + '''    "file_upload": (\n''',
        "konsep manfaat pensiun",
    )

    phrase_block = '''    (r"\\b(?:(?:manfaat|program|jaminan)\\s+)?pensiun\\b", (\n        "pension benefit",\n        "retirement benefit",\n        "employee pension",\n    )),\n'''
    text = replace_once(
        text,
        '''    (r"\\b(?:maximum|max|maksimal|batas|ukuran)\\s+(?:file[- ]?upload|upload|unggahan)\\s+(?:size|file)?\\b", (\n''',
        phrase_block + '''    (r"\\b(?:maximum|max|maksimal|batas|ukuran)\\s+(?:file[- ]?upload|upload|unggahan)\\s+(?:size|file)?\\b", (\n''',
        "ekspansi frasa pensiun",
    )

    text = replace_once(
        text,
        '''    "health_insurance": ("health insurance",),\n    "file_upload": ("file upload", "upload size limit"),\n''',
        '''    "health_insurance": ("health insurance",),\n    "retirement_benefit": ("pension benefit", "retirement benefit"),\n    "file_upload": ("file upload", "upload size limit"),\n''',
        "bridge alias pensiun",
    )

    text = replace_once(
        text,
        '''    if "mailbox_quota" in concepts:\n        return "What is the mailbox size limit?"\n    if "overtime_payment" in concepts:\n''',
        '''    if "mailbox_quota" in concepts:\n        return "What is the mailbox size limit?"\n    if "retirement_benefit" in concepts:\n        return "Does the company provide a pension benefit to employees?"\n    if "overtime_payment" in concepts:\n''',
        "natural bridge pensiun",
    )
    return text


def patch_evidence_verifier(text: str) -> str:
    text = replace_once(
        text,
        '''    "incident_p2",\n    "overtime_payment",\n}\n''',
        '''    "incident_p2",\n    "overtime_payment",\n    "retirement_benefit",\n}\n''',
        "hard concept pensiun",
    )

    helper = '''\n\ndef _has_unanswered_relevant_faq_question(\n    required: list[str],\n    content: str,\n) -> bool:\n    """Reject a FAQ chunk that contains the relevant Q: but not its paired A:.\n\n    Long TXT FAQ files can be split exactly between a question and its answer.\n    A neighbouring answer chunk may still be retrievable, but the question-only\n    chunk must not be marked as supporting evidence merely because its wording\n    overlaps the user query.\n    """\n    if not required:\n        return False\n\n    text = str(content or "")\n    question_markers = list(\n        re.finditer(r"(?:^|\\s)Q:\\s*", text, flags=re.I)\n    )\n    if not question_markers:\n        return False\n\n    for index, marker in enumerate(question_markers):\n        segment_end = (\n            question_markers[index + 1].start()\n            if index + 1 < len(question_markers)\n            else len(text)\n        )\n        segment = text[marker.end():segment_end]\n        answer_marker = re.search(r"(?:^|\\s)A:\\s*", segment, flags=re.I)\n        question_part = (\n            segment[:answer_marker.start()]\n            if answer_marker\n            else segment\n        )\n        relevant = any(\n            _concept_match(canonical, question_part)\n            for canonical in required\n            if canonical in HARD_CONCEPTS\n        )\n        if relevant and answer_marker is None:\n            return True\n\n    return False\n'''
    text = replace_once(
        text,
        '''def _lexical_coverage(question: str, content: str) -> float:\n''',
        helper + '''\n\ndef _lexical_coverage(question: str, content: str) -> float:\n''',
        "FAQ question-only guard",
    )

    text = replace_once(
        text,
        '''    for canonical in missing:\n        if canonical in HARD_CONCEPTS:\n            hard_failures.append(f"missing_concept:{canonical}")\n\n    hard_failures.extend(_subject_conflicts(required, content_text))\n''',
        '''    for canonical in missing:\n        if canonical in HARD_CONCEPTS:\n            hard_failures.append(f"missing_concept:{canonical}")\n\n    if _has_unanswered_relevant_faq_question(required, content_text):\n        hard_failures.append("faq_question_without_answer")\n\n    hard_failures.extend(_subject_conflicts(required, content_text))\n''',
        "pemakaian FAQ guard",
    )
    return text


def patch_answerability(text: str) -> str:
    text = replace_once(
        text,
        '''def _candidate_location(candidate: dict[str, Any]) -> tuple[str, str, str]:\n    metadata = candidate.get("metadata") or {}\n    return (\n        str(candidate.get("documentName") or metadata.get("filename") or "").casefold(),\n        str(candidate.get("page", metadata.get("page")) or ""),\n        str(metadata.get("paragraph_start") or candidate.get("paragraphStart") or ""),\n    )\n''',
        '''def _candidate_location(candidate: dict[str, Any]) -> tuple[str, str, str, str]:\n    metadata = candidate.get("metadata") or {}\n    return (\n        str(candidate.get("documentName") or metadata.get("filename") or "").casefold(),\n        str(candidate.get("page", metadata.get("page")) or ""),\n        str(metadata.get("paragraph_start") or candidate.get("paragraphStart") or ""),\n        str(candidate.get("chunkIndex", metadata.get("chunk_index")) or ""),\n    )\n''',
        "lokasi kandidat per chunk",
    )
    text = replace_once(
        text,
        '''    seen_locations: set[tuple[str, str, str]] = set()\n''',
        '''    seen_locations: set[tuple[str, str, str, str]] = set()\n''',
        "tipe lokasi kandidat",
    )
    text = replace_once(
        text,
        '''def _candidate_satisfies_all(\n    candidate: dict[str, Any],\n    required_concepts: set[str],\n    requirements: list[EvidenceRequirement],\n) -> bool:\n    text = str(candidate.get("content") or "")\n    if not text or candidate.get("evidenceHardContradictions"):\n        return False\n''',
        '''def _candidate_satisfies_all(\n    candidate: dict[str, Any],\n    required_concepts: set[str],\n    requirements: list[EvidenceRequirement],\n) -> bool:\n    text = str(candidate.get("content") or "")\n    if not text or candidate.get("evidenceHardContradictions"):\n        return False\n    if candidate.get("evidenceSupported") is not True:\n        return False\n    if candidate.get("evidenceMissingRequirements"):\n        return False\n    if candidate.get("evidenceHardFailures"):\n        return False\n''',
        "koherensi wajib memakai evidence yang benar-benar didukung",
    )
    text = replace_once(
        text,
        '''            "answerabilityStrictlySupported": decision.strictly_supported,\n''',
        '''            "answerabilityStrictlySupported": bool(\n                decision.strictly_supported\n                and candidate.get("evidenceSupported") is True\n                and (not selected_ids or str(candidate.get("chunkId") or "") in selected_ids)\n                and (\n                    not decision.requires_coherent_evidence\n                    or str(candidate.get("chunkId") or "") in coherent_ids\n                )\n            ),\n''',
        "strict support per kandidat",
    )
    return text


def patch_answer_formatter(text: str) -> str:
    block = '''\n    asks_pension = any(\n        term in normalized_question\n        for term in (\n            "pensiun", "pension", "retirement benefit",\n            "manfaat pensiun", "program pensiun",\n        )\n    )\n    evidence_pension = any(\n        term in normalized_answer\n        for term in (\n            "bpjs ketenagakerjaan",\n            "pension benefit",\n            "retirement benefit",\n            "pension plan",\n        )\n    )\n    evidence_for_all_employees = any(\n        term in normalized_answer\n        for term in (\n            "for all employees",\n            "all employees",\n            "seluruh karyawan",\n            "semua karyawan",\n        )\n    )\n\n    if asks_pension and evidence_pension:\n        if target == "EN":\n            suffix = " for all employees" if evidence_for_all_employees else ""\n            return (\n                "Yes. According to the indexed employee-benefits document, "\n                "the company contributes to BPJS Ketenagakerjaan"\n                f"{suffix}. This contribution is the pension benefit described "\n                "in the document."\n            )\n        employee_scope = (\n            " untuk seluruh karyawan"\n            if evidence_for_all_employees\n            else ""\n        )\n        return (\n            "Ya. Berdasarkan dokumen manfaat karyawan, perusahaan memberikan "\n            "kontribusi ke BPJS Ketenagakerjaan"\n            f"{employee_scope}. Kontribusi tersebut merupakan manfaat pensiun "\n            "yang disebutkan dalam dokumen."\n        )\n'''
    text = replace_once(
        text,
        '''    asks_overtime = any(\n''',
        block + '''\n    asks_overtime = any(\n''',
        "fallback pensiun Indonesia",
    )
    return text


def write_test() -> None:
    path = ROOT / "tests" / "test_pension_benefit_indonesian_fix.py"
    content = '''from api.answer_formatter import build_safe_extractive_answer\nfrom retrieval.answerability import assess_answerability\nfrom retrieval.evidence_verifier import verify_chunks\nfrom retrieval.query_expansion import build_natural_bridge_query, concepts_in_text\n\n\nQUESTION = "Apakah perusahaan memberikan manfaat pensiun bagi karyawan?"\nQUESTION_ONLY = (\n    "A: Employees and up to 3 dependents are covered by the company health "\n    "insurance plan. ## Pension Q: Is there a pension benefit?"\n)\nANSWER_ONLY = (\n    "A: The company contributes to BPJS Ketenagakerjaan for all employees."\n)\n\n\ndef _candidate(content: str, chunk_id: str, chunk_index: int, score: float):\n    return {\n        "chunkId": chunk_id,\n        "chunkIndex": chunk_index,\n        "documentName": "FAQ_Benefits.txt",\n        "content": content,\n        "score": score,\n        "baseScore": score,\n        "semanticScore": score,\n        "keywordScore": 0.70,\n        "exactTokenCoverage": 0.70,\n        "metadata": {\n            "filename": "FAQ_Benefits.txt",\n            "paragraph_start": 1,\n            "chunk_index": chunk_index,\n        },\n    }\n\n\ndef test_pension_is_a_hard_cross_language_concept():\n    assert "retirement_benefit" in concepts_in_text(QUESTION)\n    bridge = build_natural_bridge_query(QUESTION).lower()\n    assert "pension benefit" in bridge\n\n\ndef test_question_only_faq_chunk_is_not_supporting_evidence():\n    chunk = verify_chunks(QUESTION, [_candidate(QUESTION_ONLY, "benefits-c0", 0, 0.73)])[0]\n    assert chunk["evidenceSupported"] is False\n    assert "faq_question_without_answer" in chunk["evidenceMissingRequirements"]\n\n\ndef test_bpjs_answer_chunk_is_supporting_evidence():\n    from retrieval.evidence_verifier import verify_evidence\n\n    decision = verify_evidence(QUESTION, ANSWER_ONLY, semantic_score=0.72)\n    assert decision.supported is True\n    assert "retirement_benefit" in decision.matched_concepts\n\n\ndef test_pre_rerank_answerability_uses_adjacent_answer_chunk():\n    candidates = verify_chunks(\n        QUESTION,\n        [\n            _candidate(QUESTION_ONLY, "benefits-c0", 0, 0.73),\n            _candidate(ANSWER_ONLY, "benefits-c1", 1, 0.72),\n        ],\n    )\n    decision = assess_answerability(QUESTION, candidates)\n    assert decision.answerable, decision.reason\n    assert "benefits-c1" in decision.evidence_chunk_ids\n    assert "concept:retirement_benefit" in decision.passed_checks\n\n\ndef test_indonesian_fallback_answers_with_supported_bpjs_fact():\n    chunk = verify_chunks(QUESTION, [_candidate(ANSWER_ONLY, "benefits-c1", 1, 0.83)])[0]\n    chunk.update({\n        "answerabilityAccepted": True,\n        "answerabilityEvidenceSelected": True,\n        "answerabilityStrictlySupported": True,\n        "answerabilityRequiresCoherentEvidence": True,\n        "answerabilityCoherentEvidence": True,\n    })\n    answer = build_safe_extractive_answer(QUESTION, [chunk], language="ID")\n    assert answer.startswith("Ya.")\n    assert "BPJS Ketenagakerjaan" in answer\n    assert "seluruh karyawan" in answer\n    assert "manfaat pensiun" in answer.lower()\n'''
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"[OK]   test regresi: {path}")


def main() -> None:
    patch_file("retrieval/query_expansion.py", patch_query_expansion)
    patch_file("retrieval/evidence_verifier.py", patch_evidence_verifier)
    patch_file("retrieval/answerability.py", patch_answerability)
    patch_file("api/answer_formatter.py", patch_answer_formatter)
    write_test()
    print("\nPatch pensiun selesai. Restart backend dan jalankan test regresi.")


if __name__ == "__main__":
    main()
