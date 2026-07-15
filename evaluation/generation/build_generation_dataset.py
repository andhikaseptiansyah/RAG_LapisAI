"""Build the official generation-evaluation dataset from one /chat request.

Source-locked mode prevents false hallucination labels caused by retrieving the
answer with /chat and then retrieving a different context with /query.
The answer, citations, and judge context all come from the same chat response.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DIR = PROJECT_ROOT / "evaluation"
CHAT_URL = os.getenv("LAPISAI_CHAT_URL", "http://localhost:8000/chat")
HEALTH_URL = os.getenv("LAPISAI_HEALTH_URL", "http://localhost:8000/health")
TIMEOUT_SECONDS = int(os.getenv("LAPISAI_EVAL_TIMEOUT", "180"))
CONTEXT_MODE = "source_locked_single_pass"


def detect_language(text: str) -> str:
    tokens = set(re.findall(r"[a-zA-ZÀ-ÿ]+", str(text or "").casefold()))
    indonesian = {
        "apa", "apakah", "berapa", "bagaimana", "kapan", "siapa", "dimana",
        "yang", "untuk", "dengan", "karyawan", "hari", "bulan", "harus",
    }
    return "ID" if len(tokens & indonesian) >= 2 else "EN"


def load_ground_truth(path: Path) -> list[dict[str, Any]]:
    if path.suffix.casefold() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        required = {"question", "expected_answer", "source_document"}
        if not rows:
            raise ValueError(f"Ground-truth CSV is empty: {path}")
        missing = required - set(rows[0])
        if missing:
            raise ValueError("Missing CSV columns: " + ", ".join(sorted(missing)))
        return [
            {
                "id": f"QA-{index:03d}",
                "split": "all",
                "question": str(row["question"]).strip(),
                "answerable": True,
                "expected_answer": str(row["expected_answer"]).strip(),
                "expected_answer_keywords": [],
                "references": [
                    {
                        "document": str(row["source_document"]).strip(),
                        "page": "",
                    }
                ],
            }
            for index, row in enumerate(rows, start=1)
        ]

    payload = json.loads(path.read_text(encoding="utf-8"))
    items = list(payload.get("items") or [])
    if not items:
        raise ValueError(f"Ground-truth JSON contains no items: {path}")
    return items


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(url, json=payload, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected response from {url}: expected JSON object")
    return data


def preflight() -> None:
    try:
        response = requests.get(HEALTH_URL, timeout=10)
        response.raise_for_status()
    except Exception as error:
        raise RuntimeError(
            "LapisAI backend is not reachable. Start Uvicorn on port 8000 before "
            f"running generation evaluation. Health check failed: {error}"
        ) from error


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


def normalize_generation_context(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None

    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    text = str(
        item.get("text")
        or item.get("content")
        or item.get("excerpt")
        or item.get("page_content")
        or ""
    ).strip()
    document_name = str(
        item.get("document_name")
        or item.get("documentName")
        or item.get("document")
        or metadata.get("filename")
        or ""
    ).strip()
    page = item.get("page", metadata.get("page"))
    chunk_id = str(
        item.get("chunk_id")
        or item.get("chunkId")
        or metadata.get("chunk_id")
        or ""
    )

    if not text:
        return None

    return {
        "text": text,
        "document_name": document_name,
        "page": page,
        "chunk_id": chunk_id,
    }


def contexts_from_chat(response: dict[str, Any]) -> list[dict[str, Any]]:
    raw_contexts = response.get("generation_contexts") or []
    contexts = [
        normalized
        for item in raw_contexts
        if (normalized := normalize_generation_context(item)) is not None
    ]
    if contexts:
        return contexts

    # Backward-compatible fallback. This still remains source-locked because the
    # excerpts are returned by the same /chat response, not a second retrieval.
    raw_sources = response.get("sources") or []
    return [
        normalized
        for item in raw_sources
        if (normalized := normalize_generation_context(item)) is not None
    ]


def build_context(contexts: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, context in enumerate(contexts, start=1):
        text = str(context.get("text") or "").strip()
        if not text:
            continue
        blocks.append(
            f"[CONTEXT {index}]\n"
            f"Document: {context.get('document_name', '')}\n"
            f"Page: {context.get('page', '') or ''}\n"
            f"Evidence: {text}"
        )
    return "\n\n".join(blocks)


def retrieved_sources_from_contexts(
    contexts: list[dict[str, Any]],
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for context in contexts:
        document = str(context.get("document_name") or "").strip()
        page = str(context.get("page") or "")
        if not document:
            continue
        key = (document, page)
        if key in seen:
            continue
        seen.add(key)
        output.append({"document": document, "page": page})
    return output


def build_dataset(
    ground_truth: list[dict[str, Any]],
    output: Path,
    split: str,
    top_k: int,
) -> None:
    questions = ground_truth if split == "all" else [
        item for item in ground_truth if item.get("split") == split
    ]
    if not questions:
        raise ValueError(f"No questions found for split={split}")

    preflight()
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    print(f"Generate {len(questions)} answers in {CONTEXT_MODE} mode...")

    for index, item in enumerate(questions, start=1):
        qid = str(item["id"])
        question = str(item["question"])
        language = detect_language(question)
        print(f"[{index}/{len(questions)}] {qid} ({language})")

        try:
            chat_response = post_json(
                CHAT_URL,
                {
                    "question": question,
                    "top_k": top_k,
                    "language": language,
                },
            )
            answer = str(
                chat_response.get("answer")
                or chat_response.get("result")
                or chat_response.get("response")
                or ""
            ).strip()
            if not answer:
                raise RuntimeError("The chat endpoint returned an empty answer.")

            contexts = contexts_from_chat(chat_response)
            if not contexts:
                raise RuntimeError(
                    "The chat endpoint returned an answer without generation contexts. "
                    "Install the source-locked backend patch and restart Uvicorn."
                )

            retrieved_context = build_context(contexts)
            if not retrieved_context:
                raise RuntimeError("Generation contexts contained no usable evidence text.")

            citations = normalize_chat_citations(chat_response)
            retrieved_sources = retrieved_sources_from_contexts(contexts)

            results.append(
                {
                    "id": qid,
                    "question": question,
                    "language": language,
                    "answerable": bool(item.get("answerable", True)),
                    "expected_answer": str(item.get("expected_answer") or ""),
                    "expected_sources": list(item.get("references") or []),
                    "retrieved_context": retrieved_context,
                    "retrieved_sources": retrieved_sources,
                    "retrieved_chunks": [
                        {
                            "document": context["document_name"],
                            "page": str(context.get("page") or ""),
                            "chunk_id": context.get("chunk_id", ""),
                            "content": context["text"],
                            "generation_context": True,
                        }
                        for context in contexts
                    ],
                    "generation_contexts": contexts,
                    "generated_answer": answer,
                    "citation": citations,
                    "system_confidence": chat_response.get("confidence", 0),
                    "evaluation_context_mode": CONTEXT_MODE,
                }
            )
        except Exception as error:
            message = f"{qid}: {error}"
            errors.append(message)
            print(f"[ERROR] {message}")

    if errors:
        error_preview = "\n".join(f"- {item}" for item in errors[:10])
        raise RuntimeError(
            f"Generation dataset aborted: {len(errors)}/{len(questions)} requests failed.\n"
            f"{error_preview}\nNo misleading evaluation file was written."
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("\n[SUCCESS]")
    print(f"Saved       : {output}")
    print(f"Answers     : {len(results)}")
    print(f"Context mode: {CONTEXT_MODE}")
    print(
        f"Languages   : EN={sum(r['language'] == 'EN' for r in results)}, "
        f"ID={sum(r['language'] == 'ID' for r in results)}"
    )


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
        load_ground_truth(args.ground_truth.resolve()),
        args.output.resolve(),
        args.split,
        max(1, args.top_k),
    )


if __name__ == "__main__":
    main()
