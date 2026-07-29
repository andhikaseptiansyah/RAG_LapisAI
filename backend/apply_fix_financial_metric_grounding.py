from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def _find_backend_root(start: Path) -> Path:
    candidates = [start, *start.parents]
    for candidate in candidates:
        if (candidate / "api" / "grounding_validator.py").is_file():
            return candidate
        if (candidate / "backend" / "api" / "grounding_validator.py").is_file():
            return candidate / "backend"
    raise SystemExit(
        "Folder backend tidak ditemukan. Letakkan script ini di folder backend "
        "atau jalankan dari root project."
    )


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(path.name + f".backup_financial_grounding_{stamp}")
    shutil.copy2(path, backup)
    return backup


def main() -> None:
    backend = _find_backend_root(Path.cwd().resolve())
    target = backend / "api" / "grounding_validator.py"
    text = target.read_text(encoding="utf-8")
    original = text

    alias_marker = (
        "    # GROUNDING_ID_NATIVE_V1: natural Indonesian grounding aliases.\n"
    )
    alias_block = '''    # FINANCIAL_METRIC_GROUNDING_V1: bilingual net-profit-margin aliases.\n    # These aliases validate equivalent wording only; they do not add facts or\n    # retrieval hits.\n    "net_profit_margin": (\n        "net profit margin",\n        "the net profit margin",\n        "company net profit margin",\n        "company's net profit margin",\n        "net margin",\n        "margin laba bersih",\n        "margin laba bersih perusahaan",\n        "marjin laba bersih",\n        "marjin laba bersih perusahaan",\n        "margin keuntungan bersih",\n        "marjin keuntungan bersih",\n    ),\n'''

    if '"net_profit_margin": (' not in text:
        if alias_marker not in text:
            raise SystemExit(
                "Marker GROUNDING_ID_NATIVE_V1 tidak ditemukan. "
                "File grounding_validator.py mungkin berbeda versi."
            )
        text = text.replace(alias_marker, alias_marker + alias_block, 1)

    old_percent = '''PERCENT_PATTERN = re.compile(\n    rf"\\b{NUMBER_CORE}\\s*(?:%|persen|percent|percentage)\\b",\n    flags=re.I,\n)'''
    fixed_percent = '''PERCENT_PATTERN = re.compile(\n    rf"\\b{NUMBER_CORE}\\s*(?:%(?=$|[\\s.,;:!?\\)\\]}}])|(?:persen|percent|percentage)\\b)",\n    flags=re.I,\n)'''

    if old_percent in text:
        text = text.replace(old_percent, fixed_percent, 1)

    if text == original:
        print("Patch sudah terpasang. Tidak ada perubahan yang diperlukan.")
    else:
        backup = _backup(target)
        target.write_text(text, encoding="utf-8")
        print(f"[OK]   {target}")
        print(f"       backup: {backup}")

    tests_dir = backend / "tests"
    tests_dir.mkdir(exist_ok=True)
    test_file = tests_dir / "test_financial_metric_grounding_fix.py"
    test_file.write_text(
        '''from api.grounding_validator import validate_grounded_answer\n\n\ndef _chunk():\n    return {\n        "content": (\n            "Full-year 2025 revenue was IDR 158 billion. "\n            "Net profit margin was 14%."\n        ),\n        "answerabilityEvidenceSelected": True,\n        "contextSelected": True,\n        "evidenceHardFailures": [],\n    }\n\n\ndef test_indonesian_financial_metrics_are_grounded():\n    decision = validate_grounded_answer(\n        "Berapa pendapatan tahun 2025 dan margin laba bersih perusahaan?",\n        (\n            "Pendapatan tahun 2025 perusahaan adalah IDR 158 miliar. "\n            "Margin laba bersih perusahaan adalah 14%."\n        ),\n        [_chunk()],\n    )\n    assert decision.supported is True\n    assert decision.unsupported_claims == ()\n    assert decision.unsupported_facts == ()\n\n\ndef test_wrong_margin_value_is_still_rejected():\n    decision = validate_grounded_answer(\n        "Berapa pendapatan tahun 2025 dan margin laba bersih perusahaan?",\n        (\n            "Pendapatan tahun 2025 perusahaan adalah IDR 158 miliar. "\n            "Margin laba bersih perusahaan adalah 15%."\n        ),\n        [_chunk()],\n    )\n    assert decision.supported is False\n    assert "15%" in decision.unsupported_facts\n\n\ndef test_unsupported_explanation_is_still_rejected():\n    decision = validate_grounded_answer(\n        "Berapa margin laba bersih perusahaan?",\n        "Margin laba bersih perusahaan adalah 14% karena efisiensi operasional.",\n        [_chunk()],\n    )\n    assert decision.supported is False\n    assert any("efisiensi operasional" in item for item in decision.unsupported_claims)\n''',
        encoding="utf-8",
    )
    print(f"[OK]   test regresi: {test_file}")
    print("\nPatch selesai. Restart backend setelah test lulus.")


if __name__ == "__main__":
    main()
