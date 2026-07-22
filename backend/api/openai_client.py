from typing import Any

from api.llm_shared import (
    SYSTEM_PROMPT,
    build_context,
    build_grounding_chunks,
    build_user_prompt,
    clean_model_answer,
    fallback_answer,
    is_incomplete_answer,
)
from api.grounding_validator import prune_unsupported_claims, validate_grounded_answer
from api.answer_formatter import build_refusal_answer, has_answerable_evidence, is_refusal_answer, top_confidence
from uploads.config import ENABLE_GENERATION_GROUNDING_VALIDATION, OPENAI_API_KEY, OPENAI_MODEL


def _openai_chat(system_prompt: str, user_prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.0,
        top_p=0.80,
        max_tokens=640,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    return (response.choices[0].message.content or "").strip()


def build_openai_grounded_answer(
    question: str,
    chunks: list[dict[str, Any]],
    language: str = "ID",
    evaluation_mode: bool = False,
) -> str:
    confidence = top_confidence(chunks, question=question)
    bundle_answerable = has_answerable_evidence(chunks)

    if confidence <= 0 and not bundle_answerable:
        return build_refusal_answer(language)

    grounding_chunks = build_grounding_chunks(question, chunks)
    context = build_context(question, grounding_chunks)
    if not context:
        return build_refusal_answer(language)

    user_prompt = build_user_prompt(question, context, language)

    try:
        raw_answer = _openai_chat(SYSTEM_PROMPT, user_prompt)
        llm_answer = clean_model_answer(raw_answer)

        # Evaluation mode must compare the actual provider output. Do not
        # replace it with the shared deterministic extractive formatter,
        # otherwise different providers can appear 100% identical.
        if evaluation_mode:
            if not llm_answer:
                raise RuntimeError("OpenAI returned an empty answer")
            return llm_answer

        if ENABLE_GENERATION_GROUNDING_VALIDATION and llm_answer:
            grounding = validate_grounded_answer(question, llm_answer, grounding_chunks)
            if not grounding.supported:
                pruned_answer = clean_model_answer(
                    prune_unsupported_claims(question, llm_answer, chunks)
                )
                if pruned_answer:
                    pruned_grounding = validate_grounded_answer(question, pruned_answer, chunks)
                    if (
                        pruned_grounding.supported
                        and not is_incomplete_answer(question, pruned_answer)
                        and not is_refusal_answer(pruned_answer)
                    ):
                        return pruned_answer
                return fallback_answer(question, grounding_chunks, language)

    except Exception as exc:
        if evaluation_mode:
            raise RuntimeError("OpenAI native generation failed: " + str(exc)) from exc
        print(f"[OPENAI] fallback to formatter: {exc}")
        return fallback_answer(question, grounding_chunks, language)

    if is_incomplete_answer(question, llm_answer):
        return fallback_answer(question, grounding_chunks, language)

    if not llm_answer:
        return fallback_answer(question, grounding_chunks, language)

    if is_refusal_answer(llm_answer):
        return fallback_answer(question, grounding_chunks, language)

    return llm_answer
