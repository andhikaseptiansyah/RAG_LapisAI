"""Dependency-light regression evaluation for answerability and source recall.

The script reads Chroma's SQLite metadata directly and runs BM25 over the actual
stored chunks. It intentionally skips embedding and cross-encoder model loading,
so it remains usable in CI. The purpose is to catch false refusals and source
loss after answerability/evidence changes, not to replace the full semantic and
reranker evaluation.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from rank_bm25 import BM25Okapi

from retrieval.answerability import assess_answerability
from retrieval.evidence_verifier import verify_chunks
from retrieval.query_expansion import expand_query

STOPWORDS = {
    "what", "is", "are", "the", "a", "an", "of", "to", "in", "on", "for",
    "how", "which", "when", "where", "who", "and", "or", "do", "does", "my",
    "i", "be", "with", "apa", "apakah", "berapa", "bagaimana", "yang", "dan",
    "atau", "di", "ke", "dari", "untuk", "dengan", "pada",
}


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9à-ÿ]+", str(text or "").casefold())
        if len(token) > 2 and token not in STOPWORDS
    ]


def load_chroma_records(db_path: Path, collection_name: str) -> list[dict[str, Any]]:
    connection = sqlite3.connect(db_path)
    try:
        collection = connection.execute(
            "SELECT id FROM collections WHERE name = ?",
            (collection_name,),
        ).fetchone()
        if not collection:
            raise ValueError(f"Collection not found: {collection_name}")

        segment = connection.execute(
            "SELECT id FROM segments WHERE collection = ? AND scope = 'METADATA'",
            (collection[0],),
        ).fetchone()
        if not segment:
            raise ValueError(f"Metadata segment not found: {collection_name}")

        rows = connection.execute(
            """
            SELECT e.id, e.embedding_id, m.key,
                   m.string_value, m.int_value, m.float_value, m.bool_value
            FROM embeddings e
            JOIN embedding_metadata m ON m.id = e.id
            WHERE e.segment_id = ?
            ORDER BY e.id, m.key
            """,
            (segment[0],),
        ).fetchall()
    finally:
        connection.close()

    grouped: dict[int, dict[str, Any]] = defaultdict(lambda: {"metadata": {}})
    for row_id, embedding_id, key, string_value, int_value, float_value, bool_value in rows:
        record = grouped[row_id]
        record["chunkId"] = embedding_id
        value: Any
        if string_value is not None:
            value = string_value
        elif int_value is not None:
            value = int_value
        elif float_value is not None:
            value = float_value
        elif bool_value is not None:
            value = bool(bool_value)
        else:
            value = None

        if key == "chroma:document":
            record["content"] = value or ""
        else:
            record["metadata"][key] = value

    return list(grouped.values())


def candidate_rows(
    question: str,
    records: list[dict[str, Any]],
    bm25: BM25Okapi,
    *,
    candidate_k: int = 8,
) -> list[dict[str, Any]]:
    raw_scores = bm25.get_scores(tokenize(expand_query(question)))
    maximum = max(raw_scores) if len(raw_scores) else 0.0
    ranked = sorted(range(len(records)), key=lambda index: raw_scores[index], reverse=True)

    question_tokens = set(tokenize(question))
    output: list[dict[str, Any]] = []
    for index in ranked[:candidate_k]:
        record = records[index]
        metadata = record.get("metadata") or {}
        keyword_score = float(raw_scores[index] / maximum) if maximum else 0.0
        text_tokens = set(tokenize(f"{metadata.get('filename', '')} {record.get('content', '')}"))
        exact_coverage = (
            len(question_tokens.intersection(text_tokens)) / len(question_tokens)
            if question_tokens else 0.0
        )

        # Match the production exact-token floors. The semantic/reranker stages
        # are intentionally absent from this CI-safe regression evaluator.
        final_score = keyword_score
        if exact_coverage >= 1.0:
            final_score = max(final_score, 0.86)
        elif exact_coverage >= 0.67:
            final_score = max(final_score, 0.78)

        output.append(
            {
                "chunkId": record.get("chunkId"),
                "documentName": metadata.get("filename", ""),
                "content": record.get("content", ""),
                "metadata": metadata,
                "score": round(final_score, 6),
                "baseScore": round(final_score, 6),
                "semanticScore": 0.0,
                "keywordScore": round(keyword_score, 6),
                "exactTokenCoverage": round(exact_coverage, 6),
            }
        )
    return output


def evaluate(
    csv_path: Path,
    db_path: Path,
    collection_name: str,
) -> dict[str, Any]:
    records = load_chroma_records(db_path, collection_name)
    corpus = [
        tokenize(f"{record.get('metadata', {}).get('filename', '')} {record.get('content', '')}")
        for record in records
    ]
    bm25 = BM25Okapi(corpus)

    details: list[dict[str, Any]] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        question = str(row.get("question") or "").strip()
        expected_source = Path(str(row.get("source_document") or "")).name.casefold()
        candidates = candidate_rows(question, records, bm25)
        verified = [
            candidate
            for candidate in verify_chunks(question, candidates, minimum_score=0.42)
            if not candidate.get("evidenceHardFailures")
        ]
        decision = assess_answerability(question, verified)
        top_sources = [
            Path(str(candidate.get("documentName") or "")).name.casefold()
            for candidate in verified[:5]
        ]
        source_rank = next(
            (index + 1 for index, source in enumerate(top_sources) if source == expected_source),
            None,
        )
        details.append(
            {
                "question": question,
                "expected_source": expected_source,
                "answerable": decision.answerable,
                "answerability_score": decision.score,
                "failed_checks": list(decision.failed_checks),
                "source_rank": source_rank,
                "top_sources": top_sources,
            }
        )

    total = len(details)
    summary = {
        "questions": total,
        "answerability_pass": sum(item["answerable"] for item in details),
        "answerability_rate": round(
            sum(item["answerable"] for item in details) / total if total else 0.0,
            6,
        ),
        "source_hit_at_1": sum(item["source_rank"] == 1 for item in details),
        "source_hit_at_3": sum(
            item["source_rank"] is not None and item["source_rank"] <= 3
            for item in details
        ),
        "source_hit_at_5": sum(
            item["source_rank"] is not None and item["source_rank"] <= 5
            for item in details
        ),
        "collection_records": len(records),
        "evaluation_mode": "sqlite_bm25_answerability_regression",
    }
    return {"summary": summary, "details": details}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "ground_truth_qa.csv",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=PROJECT_ROOT / "backend" / "chroma_db" / "chroma.sqlite3",
    )
    parser.add_argument(
        "--collection",
        default="knowledge_base_multilingual_v1",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = evaluate(args.csv, args.db, args.collection)
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
