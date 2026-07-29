from __future__ import annotations

from pathlib import Path

from evaluation.generation.build_generation_dataset import detect_language, load_ground_truth

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_official_csv_loads_30_answerable_questions() -> None:
    items = load_ground_truth(PROJECT_ROOT / "evaluation" / "ground_truth_qa.csv")
    assert len(items) == 30
    assert all(item["answerable"] for item in items)
    assert items[0]["id"] == "QA-001"
    assert items[-1]["id"] == "QA-030"


def test_language_detection_keeps_official_questions_in_english() -> None:
    assert detect_language("How long is the probation period for new employees?") == "EN"


def test_language_detection_supports_indonesian_queries() -> None:
    assert detect_language("Berapa lama masa percobaan untuk karyawan baru?") == "ID"
