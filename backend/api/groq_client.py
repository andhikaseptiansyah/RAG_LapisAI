import time
from typing import Any

import requests

from api.answer_formatter import build_refusal_answer, has_answerable_evidence, is_refusal_answer, top_confidence
from api.grounding_validator import prune_unsupported_claims, validate_grounded_answer
from api.llm_shared import (
    SYSTEM_PROMPT,
    build_context,
    build_grounding_chunks,
    build_user_prompt,
    clean_model_answer,
    is_incomplete_answer,
)
from uploads.config import (
    ENABLE_GENERATION_GROUNDING_VALIDATION,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MAX_RETRIES,
    GROQ_MODEL,
    GROQ_TIMEOUT_SECONDS,
)


def _groq_chat(system_prompt: str, user_prompt: str) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    endpoint = GROQ_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.0,
        "top_p": 0.80,
        "max_completion_tokens": 640,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    last_error: Exception | None = None
    for attempt in range(GROQ_MAX_RETRIES + 1):
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=GROQ_TIMEOUT_SECONDS,
            )
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < GROQ_MAX_RETRIES:
                    retry_after = response.headers.get("retry-after")
                    try:
                        delay = float(retry_after) if retry_after else min(2**attempt, 8)
                    except ValueError:
                        delay = min(2**attempt, 8)
                    time.sleep(max(0.0, delay))
                    continue

            response.raise_for_status()
            data = response.json()
            answer = str(data["choices"][0]["message"].get("content") or "").strip()
            response_model = str(data.get("model") or GROQ_MODEL)
            request_id = response.headers.get("x-request-id") or response.headers.get("x-groq-request-id") or "-"
            print(f"[GROQ] status={response.status_code} model={response_model} request_id={request_id}")
            return answer
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            last_error = exc
            if attempt < GROQ_MAX_RETRIES:
                time.sleep(min(2**attempt, 8))
                continue
            break

    raise RuntimeError(f"Groq request failed after retries: {last_error}")


def build_groq_grounded_answer(
    question: str,
    chunks: list[dict[str, Any]],
    language: str = "ID",
    evaluation_mode: bool = False,
) -> str:
    confidence = top_confidence(chunks, question=question)
    if confidence <= 0 or not has_answerable_evidence(chunks):
        return build_refusal_answer(language)

    grounding_chunks = build_grounding_chunks(question, chunks)
    context = build_context(question, grounding_chunks)
    if not context:
        return build_refusal_answer(language)

    try:
        raw_answer = _groq_chat(SYSTEM_PROMPT, build_user_prompt(question, context, language))
        llm_answer = clean_model_answer(raw_answer)
        if evaluation_mode:
            if not llm_answer:
                raise RuntimeError("Groq returned an empty answer")
            return llm_answer

        if not llm_answer or is_incomplete_answer(question, llm_answer) or is_refusal_answer(llm_answer):
            return ""

        if ENABLE_GENERATION_GROUNDING_VALIDATION:
            grounding = validate_grounded_answer(question, llm_answer, grounding_chunks)
            if not grounding.supported:
                pruned_answer = clean_model_answer(
                    prune_unsupported_claims(question, llm_answer, grounding_chunks)
                )
                if pruned_answer:
                    pruned_grounding = validate_grounded_answer(
                        question, pruned_answer, grounding_chunks
                    )
                    if (
                        pruned_grounding.supported
                        and not is_incomplete_answer(question, pruned_answer)
                        and not is_refusal_answer(pruned_answer)
                    ):
                        return pruned_answer
                print("[GROQ] native answer rejected by grounding validator")
                return ""
        return llm_answer
    except Exception as exc:
        if evaluation_mode:
            raise RuntimeError("Groq native generation failed: " + str(exc)) from exc
        print(f"[GROQ] native generation failed: {exc}")
        return ""
