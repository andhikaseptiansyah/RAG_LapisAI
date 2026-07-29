"""Patch keyword normalization consistently for LapisAI evaluation.

Run from the project root:
    python .\fix_eval_keyword_normalization.py
"""
from __future__ import annotations

import shutil
from pathlib import Path

PROJECT_ROOT = Path.cwd()
TARGETS = {
    PROJECT_ROOT / "evaluation" / "validate_user_100_setup.py": "normalize_metric_text",
    PROJECT_ROOT / "evaluation" / "generation" / "evaluate_generation.py": "normalize_answer",
}

OLD_LINE = '    value = value.replace("none resulting", "no resulting")\n'
NEW_LINES = (
    '    # Canonicalize equivalent negative phrases so keyword scoring is fair.\n'
    '    value = __import__("re").sub(r"\\bnone\\s+resulting\\s+in\\b", "no", value)\n'
    '    value = __import__("re").sub(r"\\b(?:did|does)\\s+not\\s+result\\s+in\\b", "no", value)\n'
)
ANCHOR = '    value = value.replace("upper case", "uppercase").replace("lower case", "lowercase")\n'


def patch(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    original = path.read_text(encoding="utf-8")
    if 'r"\\bnone\\s+resulting\\s+in\\b"' in original:
        print(f"SUDAH BENAR: {path.relative_to(PROJECT_ROOT)}")
        return

    if OLD_LINE in original:
        updated = original.replace(OLD_LINE, NEW_LINES, 1)
    elif ANCHOR in original:
        updated = original.replace(ANCHOR, ANCHOR + NEW_LINES, 1)
    else:
        raise RuntimeError(
            f"Lokasi normalisasi tidak ditemukan di {path}. "
            "Jangan lanjutkan evaluasi sebelum file diperiksa."
        )

    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(updated, encoding="utf-8")
    print(f"DIPERBAIKI: {path.relative_to(PROJECT_ROOT)}")
    print(f"BACKUP    : {backup.relative_to(PROJECT_ROOT)}")


def main() -> None:
    missing = [path for path in TARGETS if not path.exists()]
    if missing:
        joined = "\n".join(f"- {path}" for path in missing)
        raise SystemExit(
            "Jalankan script ini dari root project RAG_LapisAI-main.\n"
            f"File yang tidak ditemukan:\n{joined}"
        )

    for path in TARGETS:
        patch(path)

    print("\nPatch selesai.")
    print(r"Jalankan: python .\evaluation\validate_user_100_setup.py --dataset-only")


if __name__ == "__main__":
    main()
