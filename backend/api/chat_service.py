from __future__ import annotations

import time
from typing import Any

from api.answer_formatter import (
    answer_text_only,
    build_refusal_answer,
    build_small_talk_answer,
    build_sources,
    is_refusal_answer,
    is_small_talk,
    top_confidence,
)
from api.follow_up_service import build_dataset_follow_up_question
from api.ollama_client import build_ollama_grounded_answer
from retrieval.hybrid_search import hybrid_search


def run_chat(
    question: str,
    *,
    top_k: int = 5,
    language: str = "ID",
) -> dict[str, Any]:
    """Run one chat turn and return the canonical backend response payload.

    The answer field only contains the natural-language answer. Citations and
    confidence are always returned in separate fields.
    """
    started_at = time.perf_counter()
    normalized_language = (language or "ID").upper()

    if is_small_talk(question):
        answer = answer_text_only(
            build_small_talk_answer(question, language=normalized_language)
        )
        return {
            "answer": answer,
            "confidence": 1.0,
            "sources": [],
            "follow_up_question": None,
            "response_time_ms": int(round((time.perf_counter() - started_at) * 1000)),
            "model": "system-small-talk",
        }

    chunks = hybrid_search(question, top_k=top_k)
    confidence = round(top_confidence(chunks, question=question), 4)
    sources = build_sources(chunks, question=question)

    # A document answer is only allowed when retrieval produced both a calibrated
    # confidence and at least one reliable, structured source.
    if confidence <= 0.0 or not sources:
        return {
            "answer": build_refusal_answer(normalized_language),
            "confidence": 0.0,
            "sources": [],
            "follow_up_question": None,
            "response_time_ms": int(round((time.perf_counter() - started_at) * 1000)),
            "model": "retrieval-refusal",
        }

    answer = answer_text_only(
        build_ollama_grounded_answer(
            question,
            chunks,
            language=normalized_language,
        )
    )

    # If the model itself cannot support an answer, do not expose stale sources
    # or a positive confidence value.
    if not answer or is_refusal_answer(answer):
        answer = build_refusal_answer(normalized_language)
        confidence = 0.0
        sources = []

    follow_up_question = None
    if confidence > 0 and sources:
        follow_up_question = build_dataset_follow_up_question(
            question=question,
            answer=answer,
            sources=sources,
            language=normalized_language,
        )

    return {
        "answer": answer,
        "confidence": confidence,
        "sources": sources,
        "follow_up_question": follow_up_question,
        "response_time_ms": int(round((time.perf_counter() - started_at) * 1000)),
        "model": "ollama-rag" if confidence > 0 else "retrieval-refusal",
    }
