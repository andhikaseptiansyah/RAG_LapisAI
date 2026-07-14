"""Build a generation-evaluation dataset from the LapisAI API.

Important difference from the old script:
- /query is used to capture the raw retrieved chunks and full context.
- /chat is used to capture the final generated answer and displayed citations.
- Source keys such as documentName and excerpt are supported.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DIR = PROJECT_ROOT / "evaluation"
if str(EVALUATION_DIR) not in sys.path:
    sys.path.insert(0, str(EVALUATION_DIR))

from evaluate_retrieval import load_ground_truth as load_official_ground_truth  # noqa: E402

CHAT_URL = os.getenv("LAPISAI_CHAT_URL", "http://localhost:8000/chat")
QUERY_URL = os.getenv("LAPISAI_QUERY_URL", "http://localhost:8000/query")
TIMEOUT_SECONDS = int(os.getenv("LAPISAI_EVAL_TIMEOUT", "180"))


def load_ground_truth(path: Path) -> list[dict[str, Any]]:
    _, items = load_official_ground_truth(path.resolve())
    return items


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(url, json=payload, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected response from {url}: expected JSON object")
    return data


def normalize_source(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None

    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    document = (
        item.get("documentName")
        or item.get("document_name")
        or item.get("document")
        or item.get("file_name")
        or item.get("file")
        or item.get("source")
        or metadata.get("filename")
        or metadata.get("source")
        or metadata.get("document")
        or ""
    )
    page = (
        item.get("page")
        or item.get("page_number")
        or item.get("page_no")
        or metadata.get("page")
        or ""
    )

    if not document:
        return None

    return {"document": str(document), "page": str(page)}


def normalize_chunk(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None

    source = normalize_source(item)
    if source is None:
        return None

    content = (
        item.get("content")
        or item.get("page_content")
        or item.get("text")
        or item.get("excerpt")
        or ""
    )

    return {
        **source,
        "chunk_id": str(item.get("chunkId") or item.get("chunk_id") or ""),
        "content": str(content).strip(),
        "score": item.get("score", item.get("relevanceScore", 0)),
        "semantic_score": item.get("semanticScore", 0),
        "keyword_score": item.get("keywordScore", 0),
        "reranker_score": item.get("rerankerScore", 0),
        "evidence_score": item.get("evidenceScore", 0),
        "evidence_supported": item.get("evidenceSupported"),
    }


def build_context(chunks: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        content = str(chunk.get("content") or "").strip()
        if not content:
            continue
        blocks.append(
            f"[CONTEXT {index}]\n"
            f"Document: {chunk.get('document', '')}\n"
            f"Page: {chunk.get('page', '')}\n"
            f"Content: {content}"
        )
    return "\n\n".join(blocks)


def normalize_chat_citations(response: dict[str, Any]) -> list[dict[str, str]]:
    raw_sources = (
        response.get("sources")
        or response.get("source_documents")
        or response.get("retrieved_sources")
        or []
    )
    citations: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for item in raw_sources:
        source = normalize_source(item)
        if source is None:
            continue
        key = (source["document"], source["page"])
        if key in seen:
            continue
        seen.add(key)
        citations.append(source)

    return citations


def build_dataset(
    ground_truth: list[dict[str, Any]],
    output: Path,
    split: str,
    top_k: int,
) -> None:
    questions = ground_truth if split == "all" else [
        item for item in ground_truth if item.get("split") == split
    ]

    results: list[dict[str, Any]] = []
    print(f"Generate {len(questions)} answers...")

    for index, item in enumerate(questions, start=1):
        qid = str(item["id"])
        question = str(item["question"])
        print(f"[{index}/{len(questions)}] {qid}")

        try:
            query_response = post_json(
                QUERY_URL,
                {"query": question, "top_k": top_k},
            )
            raw_chunks = query_response.get("chunks") or []
            chunks = [
                normalized
                for raw in raw_chunks
                if (normalized := normalize_chunk(raw)) is not None
            ]

            chat_response = post_json(
                CHAT_URL,
                {"question": question, "top_k": top_k},
            )
            answer = str(
                chat_response.get("answer")
                or chat_response.get("result")
                or chat_response.get("response")
                or ""
            ).strip()
            citations = normalize_chat_citations(chat_response)

            results.append(
                {
                    "id": qid,
                    "question": question,
                    "expected_answer": str(item.get("expected_answer") or ""),
                    "expected_sources": list(item.get("references") or []),
                    "retrieved_context": build_context(chunks),
                    "retrieved_sources": [
                        {"document": chunk["document"], "page": chunk["page"]}
                        for chunk in chunks
                    ],
                    "retrieved_chunks": chunks,
                    "generated_answer": answer,
                    "citation": citations,
                    "system_confidence": chat_response.get("confidence", 0),
                }
            )
        except Exception as error:
            print(f"[ERROR] {qid}: {error}")
            results.append(
                {
                    "id": qid,
                    "question": question,
                    "expected_answer": str(item.get("expected_answer") or ""),
                    "expected_sources": list(item.get("references") or []),
                    "retrieved_context": "",
                    "retrieved_sources": [],
                    "retrieved_chunks": [],
                    "generated_answer": "Tidak ditemukan jawaban.",
                    "citation": [],
                    "system_confidence": 0,
                    "error": str(error),
                }
            )

    output.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("\n[SUKSES]")
    print(f"Tersimpan : {output}")
    print(f"Jumlah data : {len(results)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=EVALUATION_DIR / "ground_truth_qa.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "input_answers_official.json",
    )
    parser.add_argument(
        "--split",
        default="all",
        choices=["train", "development", "test", "all"],
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    build_dataset(
        load_ground_truth(args.ground_truth),
        args.output,
        args.split,
        max(1, args.top_k),
    )


if __name__ == "__main__":
    main()