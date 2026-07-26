from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sys

PATCH_TAG = "GROUNDING_ID_NATIVE_V1"


def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    raise SystemExit(1)


def locate_backend() -> Path:
    here = Path.cwd().resolve()
    candidates = [here, here / "backend", Path(__file__).resolve().parent]
    for candidate in candidates:
        if (candidate / "api" / "grounding_validator.py").is_file():
            return candidate
    fail(
        "Folder backend tidak ditemukan. Jalankan script ini dari folder "
        "RAG_LapisAI\\backend."
    )


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(path.name + f".backup_grounding_{stamp}")
    shutil.copy2(path, target)
    return target


def patch_grounding(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if PATCH_TAG in text:
        print(f"[SKIP] Patch sudah ada: {path}")
        return False

    aliases_anchor = (
        "GROUNDING_CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {\n"
        "    **CONCEPT_ALIASES,\n"
    )
    aliases_replacement = (
        "GROUNDING_CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {\n"
        "    **CONCEPT_ALIASES,\n"
        f"    # {PATCH_TAG}: natural Indonesian grounding aliases.\n"
        "    \"processing_time\": tuple(dict.fromkeys((\n"
        "        *CONCEPT_ALIASES.get(\"processing_time\", ()),\n"
        "        \"jangka waktu\",\n"
        "        \"jangka waktu tersebut\",\n"
        "        \"merupakan batas penyelesaian\",\n"
        "        \"batas penyelesaian yang ditetapkan\",\n"
        "        \"batas waktu penyelesaian yang ditetapkan\",\n"
        "        \"waktu yang ditetapkan\",\n"
        "        \"target waktu yang ditetapkan\",\n"
        "        \"completion deadline\",\n"
        "        \"defined resolution limit\",\n"
        "    ))),\n"
        "    \"incident_p1\": tuple(dict.fromkeys((\n"
        "        *CONCEPT_ALIASES.get(\"incident_p1\", ()),\n"
        "        \"insiden prioritas p1\",\n"
        "        \"insiden it prioritas p1\",\n"
        "        \"insiden ti prioritas p1\",\n"
        "        \"insiden it prioritas 1\",\n"
        "        \"insiden ti prioritas 1\",\n"
        "        \"p1 priority incident\",\n"
        "    ))),\n"
        "    \"incident_p2\": tuple(dict.fromkeys((\n"
        "        *CONCEPT_ALIASES.get(\"incident_p2\", ()),\n"
        "        \"insiden prioritas p2\",\n"
        "        \"insiden it prioritas p2\",\n"
        "        \"insiden ti prioritas p2\",\n"
        "        \"insiden it prioritas 2\",\n"
        "        \"insiden ti prioritas 2\",\n"
        "        \"p2 priority incident\",\n"
        "    ))),\n"
    )
    if aliases_anchor not in text:
        fail("Anchor GROUNDING_CONCEPT_ALIASES tidak ditemukan.")
    text = text.replace(aliases_anchor, aliases_replacement, 1)

    preamble_anchor = (
        "CONDITIONAL_COMMA_PREFIX = re.compile(\n"
        "    r\"^\\s*(?:if|when|once|before|after|unless|provided\\s+that|\"\n"
        "    r\"jika|ketika|apabila|bila|sebelum|setelah)\\b\",\n"
        "    flags=re.I,\n"
        ")\n"
    )
    preamble_replacement = preamble_anchor + (
        "GROUNDING_PREAMBLE = re.compile(\n"
        "    r\"^\\s*(?:\"\n"
        "    r\"berdasarkan\\s+(?:ketentuan\\s+pada\\s+)?(?:dokumen|sumber)(?:\\s+yang\\s+tersedia)?\"\n"
        "    r\"|menurut\\s+(?:dokumen|sumber)\"\n"
        "    r\"|according\\s+to\\s+(?:the\\s+)?(?:document|source|evidence)\"\n"
        "    r\"|based\\s+on\\s+(?:the\\s+)?(?:document|source|evidence)\"\n"
        "    r\")\\s*[:,]?\\s*\",\n"
        "    flags=re.I,\n"
        ")\n"
    )
    if preamble_anchor not in text:
        fail("Anchor CONDITIONAL_COMMA_PREFIX tidak ditemukan.")
    text = text.replace(preamble_anchor, preamble_replacement, 1)

    atomic_anchor = (
        "        sentence = _clean(raw_sentence).lstrip(\"-? \")\n\n"
        "        if not sentence:\n"
        "            continue\n"
    )
    atomic_replacement = (
        "        sentence = _clean(raw_sentence).lstrip(\"-? \")\n"
        "        # Attribution is presentation text, not an independent factual claim.\n"
        "        # Removing it before comma splitting prevents false rejection of\n"
        "        # sentences such as 'Berdasarkan dokumen, ...'.\n"
        "        sentence = GROUNDING_PREAMBLE.sub(\"\", sentence).strip()\n\n"
        "        if not sentence:\n"
        "            continue\n"
    )
    if atomic_anchor not in text:
        fail("Anchor _atomic_claims tidak ditemukan.")
    text = text.replace(atomic_anchor, atomic_replacement, 1)

    old_reference = (
        "def _claim_reference_units(claim: str, evidence_units: list[str]) -> list[str]:\n"
        "    claim_fact_keys = {key for key, _, _ in _fact_entries(claim)}\n"
        "    if not claim_fact_keys:\n"
        "        return list(evidence_units)\n"
        "    return [\n"
        "        unit\n"
        "        for unit in evidence_units\n"
        "        if claim_fact_keys.issubset({key for key, _, _ in _fact_entries(unit)})\n"
        "    ]\n"
    )
    new_reference = '''_INCIDENT_CODE_PATTERN = re.compile(
    r"\\b(?:p(?P<pnum>[1-4])|priority\\s+(?P<priority>[1-4])|"
    r"prioritas\\s+(?P<prioritas>[1-4]))\\b",
    flags=re.I,
)


def _incident_relation_is_coherent(claim: str, unit: str) -> bool:
    """Bind an incident priority to the quantity in its own local row.

    PDF extraction can flatten P1 and P2 SLA rows into one passage. The quantity
    must occur after the requested priority code and before the next code, so a P2
    value cannot accidentally be attached to P1, or vice versa.
    """
    claim_entries = _fact_entries(claim)
    claim_codes = [
        key.split(":", 1)[1].casefold()
        for key, _, _ in claim_entries
        if key.startswith("identifier:P")
    ]
    claim_quantities = {
        key for key, _, _ in claim_entries
        if key.startswith("quantity:")
    }
    if len(claim_codes) != 1 or not claim_quantities:
        return True

    requested_code = claim_codes[0]
    mentions = list(_INCIDENT_CODE_PATTERN.finditer(unit))
    if not mentions:
        return True

    for index, mention in enumerate(mentions):
        number = (
            mention.group("pnum")
            or mention.group("priority")
            or mention.group("prioritas")
        )
        if f"p{number}" != requested_code:
            continue
        end = mentions[index + 1].start() if index + 1 < len(mentions) else len(unit)
        local_row = unit[mention.start():end]
        local_keys = {key for key, _, _ in _fact_entries(local_row)}
        if claim_quantities.issubset(local_keys):
            return True
    return False


def _claim_reference_units(claim: str, evidence_units: list[str]) -> list[str]:
    claim_fact_keys = {key for key, _, _ in _fact_entries(claim)}
    if not claim_fact_keys:
        return list(evidence_units)

    matched = [
        unit
        for unit in evidence_units
        if claim_fact_keys.issubset({key for key, _, _ in _fact_entries(unit)})
        and _incident_relation_is_coherent(claim, unit)
    ]
    if not matched:
        return []

    # Prefer precise evidence units while retaining flattened PDF rows when no
    # shorter sentence contains all required facts.
    shortest = min(len(unit) for unit in matched)
    return [unit for unit in matched if len(unit) <= shortest + 160]
'''
    if old_reference not in text:
        fail("Fungsi _claim_reference_units tidak sesuai versi yang didukung.")
    text = text.replace(old_reference, new_reference, 1)

    backup_path = backup(path)
    path.write_text(text, encoding="utf-8")
    print(f"[OK]   {path}")
    print(f"       backup: {backup_path}")
    return True


def write_test(backend: Path) -> Path:
    test_path = backend / "tests" / "test_grounding_indonesian_native_fix.py"
    test_path.write_text(
        '''from api.grounding_validator import prune_unsupported_claims, validate_grounded_answer


QUESTION = "Seberapa cepat insiden IT P1 harus diselesaikan?"
EVIDENCE = (
    "Incidents are classified as P1 (critical), P2 (high), P3 (medium), P4 (low). "
    "P1 incidents must be acknowledged within 15 minutes and resolved within 4 hours. "
    "P2 within 1 hour and 8 business hours respectively. "
    "If a P1 is not resolved within 2 hours, it is escalated to the Head of Infrastructure."
)


def chunk():
    return {
        "content": EVIDENCE,
        "answerabilityEvidenceSelected": True,
        "contextSelected": True,
        "evidenceHardFailures": [],
    }


def test_accepts_natural_indonesian_grounded_answer():
    answer = (
        "Berdasarkan ketentuan pada dokumen, insiden IT prioritas P1 harus "
        "diselesaikan dalam waktu 4 jam. Jangka waktu tersebut merupakan "
        "batas penyelesaian yang ditetapkan untuk insiden IT prioritas P1."
    )
    decision = validate_grounded_answer(QUESTION, answer, [chunk()])
    assert decision.supported, decision


def test_prunes_unsupported_explanation_but_keeps_supported_fact():
    answer = (
        "Insiden IT prioritas P1 harus diselesaikan dalam waktu 4 jam. "
        "Ketentuan ini dibuat untuk meningkatkan kepuasan pelanggan."
    )
    pruned = prune_unsupported_claims(QUESTION, answer, [chunk()])
    assert "4 jam" in pruned
    assert "kepuasan pelanggan" not in pruned


def test_rejects_cross_priority_relation_swap():
    answer = "Insiden IT prioritas P2 harus diselesaikan dalam waktu 4 jam."
    decision = validate_grounded_answer(QUESTION, answer, [chunk()])
    assert not decision.supported
    assert "unsupported_claims" in decision.reasons
''',
        encoding="utf-8",
    )
    print(f"[OK]   test regresi: {test_path}")
    return test_path


def main() -> None:
    backend = locate_backend()
    changed = patch_grounding(backend / "api" / "grounding_validator.py")
    write_test(backend)
    print("\nPatch grounding selesai.")
    print("Jalankan:")
    print("  python -m pytest tests/test_grounding_indonesian_native_fix.py tests/test_v8_indonesian_generation_fix.py -q")
    print("Lalu restart backend.")
    if not changed:
        print("Tidak ada perubahan tambahan karena patch sudah terpasang.")


if __name__ == "__main__":
    main()
