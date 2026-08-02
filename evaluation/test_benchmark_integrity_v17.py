import hashlib
from pathlib import Path

from evaluation.audit_benchmark_leakage import (
    _is_active_python_file,
    _searchable_python,
)
from evaluation.generation.compare_models import verify_artifact_manifest


def test_leakage_audit_ignores_comments_but_keeps_runtime_strings(
    tmp_path: Path,
) -> None:
    source = tmp_path / "active.py"
    source.write_text(
        '# Example answer: 50 GB.\n'
        'BRIDGE = "How quickly must a P1 IT incident be resolved?"\n',
        encoding="utf-8",
    )

    searchable = _searchable_python(source)
    assert "50 gb" not in searchable
    assert "how quickly must a p1 it incident be resolved" in searchable


def test_leakage_audit_excludes_archived_python_copies(tmp_path: Path) -> None:
    backup = tmp_path / "module.backup_20260802.py"
    backup.write_text("VALUE = 1\n", encoding="utf-8")

    assert _is_active_python_file(backup) is False


def test_artifact_manifest_detects_a_stale_raw_answer_file(tmp_path: Path) -> None:
    raw = tmp_path / "answers.json"
    raw.write_text("[]\n", encoding="utf-8")
    original = raw.read_bytes()
    summary = {
        "reproducibility": {
            "files": [
                {
                    "path": str(raw),
                    "sha256": hashlib.sha256(original).hexdigest(),
                    "bytes": len(original),
                }
            ]
        }
    }

    assert verify_artifact_manifest(summary)["status"] == "verified"
    raw.write_text('[{"id":"changed"}]\n', encoding="utf-8")
    result = verify_artifact_manifest(summary)
    assert result["status"] == "failed"
    assert result["mismatched_files"][0]["path"] == str(raw)
