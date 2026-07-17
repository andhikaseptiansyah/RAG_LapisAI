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
from uploads.config import ENABLE_GENERATION_GROUNDING_VALIDATION, GEMINI_API_KEY, GEMINI_MODEL


def _gemini_chat(system_prompt: str, user_prompt: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=system_prompt,
    )

    response = model.generate_content(
        user_prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.0,
            top_p=0.80,
            max_output_tokens=640,
        ),
    )

    return (response.text or "").strip()


def build_gemini_grounded_answer(
    question: str,
    chunks: list[dict[str, Any]],
    language: str = "ID",
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
        raw_answer = _gemini_chat(SYSTEM_PROMPT, user_prompt)
        llm_answer = clean_model_answer(raw_answer)

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
        print(f"[GEMINI] fallback to formatter: {exc}")
        return fallback_answer(question, grounding_chunks, language)

    if is_incomplete_answer(question, llm_answer):
        return fallback_answer(question, grounding_chunks, language)

    if not llm_answer:
        return fallback_answer(question, grounding_chunks, language)

    if is_refusal_answer(llm_answer):
        return fallback_answer(question, grounding_chunks, language)

    return llm_answer
