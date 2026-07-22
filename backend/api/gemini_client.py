from typing import Any

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
from uploads.config import ENABLE_GENERATION_GROUNDING_VALIDATION, GEMINI_API_KEY, GEMINI_MODEL


def _gemini_chat(system_prompt: str, user_prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    from google import genai
    from google.genai import types

    with genai.Client(api_key=GEMINI_API_KEY) as client:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.0,
                top_p=0.80,
                max_output_tokens=640,
            ),
        )
    print(f"[GEMINI] model={GEMINI_MODEL} status=success")
    return (response.text or "").strip()


def build_gemini_grounded_answer(
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
        raw_answer = _gemini_chat(SYSTEM_PROMPT, build_user_prompt(question, context, language))
        llm_answer = clean_model_answer(raw_answer)
        if evaluation_mode:
            if not llm_answer:
                raise RuntimeError("Gemini returned an empty answer")
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
                print("[GEMINI] native answer rejected by grounding validator")
                return ""
        return llm_answer
    except Exception as exc:
        if evaluation_mode:
            raise RuntimeError("Gemini native generation failed: " + str(exc)) from exc
        print(f"[GEMINI] native generation failed: {exc}")
        return ""
