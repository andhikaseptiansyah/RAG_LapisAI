from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if not (ROOT / "api").is_dir():
    ROOT = Path.cwd()

OLLAMA_CLIENT = ROOT / "api" / "ollama_client.py"
TEST_FILE = ROOT / "tests" / "test_single_source_long_financial_answer.py"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def backup(path: Path) -> Path:
    destination = path.with_name(path.name + f".backup_remove_summary_{STAMP}")
    shutil.copy2(path, destination)
    print(f"       backup: {destination}")
    return destination


def remove_expansion_function(text: str) -> str:
    start_marker = "\ndef _expand_supported_multi_metric_answer("
    end_marker = "\ndef _is_likely_incomplete_answer("

    start = text.find(start_marker)
    if start < 0:
        return text

    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(
            "Batas akhir fungsi _expand_supported_multi_metric_answer() tidak ditemukan"
        )

    return text[:start] + "\n" + text[end:]


def remove_expansion_call(text: str) -> str:
    start_marker = (
        "\n    # Multi-part financial questions are easier to read with one concise summary"
    )
    end_marker = "\n    if is_refusal_answer(llm_answer):"

    start = text.find(start_marker)
    if start < 0:
        # Compatibility for variants where the comment was edited but the call remains.
        match = re.search(
            r"\n\s*expanded_candidate\s*=\s*_expand_supported_multi_metric_answer\(.*?"
            r"(?=\n\s*if is_refusal_answer\(llm_answer\):)",
            text,
            flags=re.S,
        )
        if not match:
            return text
        return text[: match.start()] + "\n" + text[match.end() :]

    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError("Batas akhir blok expanded_candidate tidak ditemukan")

    return text[:start] + text[end:]


def patch_ollama_client(text: str) -> str:
    patched = remove_expansion_function(text)
    patched = remove_expansion_call(patched)
    return patched


def patch_test(text: str) -> str:
    text = text.replace(
        "from api.ollama_client import _expand_supported_multi_metric_answer\n",
        "import api.ollama_client as ollama_client\n",
    )

    pattern = re.compile(
        r"\ndef test_financial_answer_gets_one_grounded_summary_sentence\(\):.*\Z",
        flags=re.S,
    )
    replacement = (
        "\n\ndef test_repetitive_multi_metric_expansion_is_removed():\n"
        "    assert not hasattr(ollama_client, '_expand_supported_multi_metric_answer')\n"
    )
    patched, count = pattern.subn(replacement, text, count=1)
    if count == 0 and "test_repetitive_multi_metric_expansion_is_removed" not in text:
        patched = text.rstrip() + replacement
    return patched


def patch_file(path: Path, transform) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    original = path.read_text(encoding="utf-8")
    patched = transform(original)
    if patched == original:
        print(f"[SKIP] {path} sudah tidak menambahkan ringkasan berulang")
        return
    backup(path)
    path.write_text(patched, encoding="utf-8")
    print(f"[OK]   {path}")


def main() -> None:
    patch_file(OLLAMA_CLIENT, patch_ollama_client)
    if TEST_FILE.exists():
        patch_file(TEST_FILE, patch_test)

    print(
        "\nPatch selesai. Kalimat ringkasan ketiga yang mengulang angka telah dihapus."
    )
    print("Restart backend, lalu jalankan test regresi.")


if __name__ == "__main__":
    main()
