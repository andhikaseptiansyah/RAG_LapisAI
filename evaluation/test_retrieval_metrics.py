from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("evaluate_retrieval.py")
SPEC = importlib.util.spec_from_file_location("evaluate_retrieval", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def result(document: str, page: int) -> dict:
    return {"documentName": document, "page": page}


def test_document_metrics() -> None:
    ranked = [result("A.pdf", 1), result("B.pdf", 1), result("C.pdf", 1)]
    relevant = {"b.pdf"}
    metrics = MODULE.metrics_at_k(ranked, relevant, [1, 3], "document")
    assert metrics["hit@1"] == 0.0
    assert metrics["hit@3"] == 1.0
    assert metrics["precision@3"] == 1 / 3
    assert metrics["recall@3"] == 1.0
    assert MODULE.rank_of_first_relevant(ranked, relevant, "document") == 2


def test_page_metrics_and_deduplication() -> None:
    ranked = [
        result("A.pdf", 1),
        result("A.pdf", 1),
        result("A.pdf", 2),
        result("B.pdf", 1),
    ]
    unique = MODULE.dedupe_ranked_results(ranked, "page")
    assert len(unique) == 3
    relevant = {("a.pdf", "2")}
    assert MODULE.rank_of_first_relevant(unique, relevant, "page") == 2


if __name__ == "__main__":
    test_document_metrics()
    test_page_metrics_and_deduplication()
    print("Retrieval metric tests passed.")
