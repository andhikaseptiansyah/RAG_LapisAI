from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def backup(path: Path) -> Path:
    target = path.with_name(f"{path.name}.backup_alias_punctuation_{STAMP}")
    shutil.copy2(path, target)
    return target


def patch_query_expansion() -> None:
    path = ROOT / "retrieval" / "query_expansion.py"
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    original = path.read_text(encoding="utf-8")
    if "ALIAS_PUNCTUATION_BOUNDARY_V1" in original:
        print(f"[SKIP] Perbaikan sudah terpasang: {path}")
        return

    old = '''    normalized = normalize_text(text)\n    if not normalized:\n        return False\n\n    padded = f" {normalized} "\n    for alias in aliases:\n        candidate = normalize_text(alias)\n        if candidate and f" {candidate} " in padded:\n            return True\n    return False\n'''

    new = '''    normalized = normalize_text(text)\n    if not normalized:\n        return False\n\n    # ALIAS_PUNCTUATION_BOUNDARY_V1\n    # Concept aliases are ordinary phrases, not paths or version identifiers.\n    # Convert punctuation to word separators before boundary matching. Without\n    # this, an alias at the end of a sentence such as ``customer portal.`` does\n    # not match ``customer portal`` because normalize_text deliberately keeps\n    # periods for URLs, filenames, and version-like values.\n    phrase_text = re.sub(r"[^a-z0-9à-ÿ%]+", " ", normalized)\n    phrase_text = re.sub(r"\\s+", " ", phrase_text).strip()\n    padded = f" {phrase_text} "\n\n    for alias in aliases:\n        candidate = normalize_text(alias)\n        candidate = re.sub(r"[^a-z0-9à-ÿ%]+", " ", candidate)\n        candidate = re.sub(r"\\s+", " ", candidate).strip()\n        if candidate and f" {candidate} " in padded:\n            return True\n    return False\n'''

    if old not in original:
        # Fallback for small formatting differences: replace only the function.
        pattern = re.compile(
            r"def contains_alias\(text: str, aliases: Iterable\[str\]\) -> bool:\n"
            r"(?P<body>(?:    .*\n|\n)+?)"
            r"(?=\ndef |\Z)",
            flags=re.M,
        )
        match = pattern.search(original)
        if not match:
            raise RuntimeError(
                "Fungsi contains_alias() tidak ditemukan. Jangan menimpa file secara manual; "
                "unggah query_expansion.py terbaru untuk diperiksa."
            )
        function_text = match.group(0)
        doc_end = function_text.find('    normalized = normalize_text(text)')
        if doc_end < 0:
            raise RuntimeError("Struktur contains_alias() tidak dikenali.")
        replacement = function_text[:doc_end] + new
        updated = original[: match.start()] + replacement + original[match.end() :]
    else:
        updated = original.replace(old, new, 1)

    saved = backup(path)
    path.write_text(updated, encoding="utf-8", newline="\n")
    print(f"[OK]   {path}")
    print(f"       backup: {saved}")


def write_regression_test() -> None:
    path = ROOT / "tests" / "test_customer_portal_root_cause_fix.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = '''from retrieval.answerability import assess_answerability\nfrom retrieval.evidence_verifier import verify_evidence\nfrom retrieval.query_expansion import CONCEPT_ALIASES, concepts_in_text, contains_alias\n\n\nQUESTION = "Apa penyebab utama gangguan portal pelanggan pada 14 Oktober 2025?"\nEVIDENCE = (\n    "Nusantara Dynamics Incident Postmortem - October 2025. "\n    "The 14 October 2025 outage lasted 3 hours 20 minutes, affecting the customer portal. "\n    "The root cause was an expired TLS certificate on the API gateway."\n)\n\n\ndef _chunk(content: str, decision):\n    return {\n        "chunkId": "incident-postmortem-1",\n        "content": content,\n        "score": 0.84,\n        "baseScore": 0.80,\n        "semanticScore": 0.90,\n        "evidenceSupported": decision.supported,\n        "evidenceScore": decision.score,\n        "evidenceHardFailures": list(decision.hard_failures),\n        "metadata": {\n            "filename": "Report_Incident_Postmortem.pdf",\n            "page": 1,\n            "paragraph_start": 1,\n            "paragraph_end": 8,\n        },\n    }\n\n\ndef test_alias_matches_before_sentence_punctuation():\n    assert contains_alias(\n        "The outage affected the customer portal.",\n        CONCEPT_ALIASES["customer_portal"],\n    )\n    assert "customer_portal" in concepts_in_text(\n        "The outage affected the customer portal."\n    )\n\n\ndef test_short_alias_does_not_match_inside_an_unrelated_word():\n    assert not contains_alias("corporate policy", ("rpo",))\n\n\ndef test_customer_portal_root_cause_passes_evidence_and_answerability():\n    evidence = verify_evidence(QUESTION, EVIDENCE, semantic_score=0.90)\n    assert evidence.supported is True\n    assert "customer_portal" in evidence.matched_concepts\n    assert not evidence.hard_failures\n\n    answerability = assess_answerability(QUESTION, [_chunk(EVIDENCE, evidence)])\n    assert answerability.answerable is True\n    assert answerability.strictly_supported is True\n    assert "concept:customer_portal" in answerability.passed_checks\n\n\ndef test_negative_upload_size_question_still_has_no_storage_answer():\n    question = "What is the maximum file-upload size in the customer portal?"\n    evidence = verify_evidence(question, EVIDENCE, semantic_score=0.90)\n    # Portal matching is fixed, but the unrelated postmortem still lacks the\n    # requested file-upload concept and storage value. The safety gate remains.\n    assert evidence.supported is False\n    assert any(\n        item in evidence.hard_failures\n        for item in ("missing_concept:file_upload", "missing_numeric_value")\n    )\n'''
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"[OK]   test regresi: {path}")


def main() -> None:
    patch_query_expansion()
    write_regression_test()
    print("\nPatch selesai. Jalankan test lalu restart backend.")


if __name__ == "__main__":
    main()
