from typing import Any

from api.cancellation import raise_if_cancelled
from api.answer_formatter import (
    build_refusal_answer,
    has_answerable_evidence,
    is_refusal_answer,
    top_confidence,
)
from api.grounding_validator import (
    prune_unsupported_claims,
    validate_grounded_answer,
)
from api.language import answer_matches_requested_language
from api.llm_shared import (
    build_language_repair_prompt,
    build_system_prompt,
    build_context,
    build_grounding_chunks,
    build_user_prompt,
    clean_model_answer,
    is_incomplete_answer,
)
from uploads.config import (
    ENABLE_GENERATION_GROUNDING_VALIDATION,
    GEMINI_API_KEY,
    GEMINI_MODEL,
)


def _gemini_chat(system_prompt: str, user_prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    from google import genai
    from google.genai import types

    raise_if_cancelled()
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

    raise_if_cancelled()
    print(f"[GEMINI] model={GEMINI_MODEL} status=success")
    return (response.text or "").strip()


def _scope_instruction(question: str, language: str) -> str:
    """Restrict Gemini to the fact type actually requested by the user."""
    normalized = str(question or "").casefold()
    is_english = str(language or "ID").upper() == "EN"

    if any(term in normalized for term in ("penyebab", "akar masalah", "root cause", "caused", "cause")):
        if is_english:
            return (
                "\n\nSCOPE CONTROL: Answer only the requested cause or root cause. "
                "Do not add remediation, corrective actions, prevention steps, impact, "
                "or recommendations unless the question explicitly asks for them."
            )
        return (
            "\n\nBATASAN JAWABAN: Jawab hanya penyebab atau akar masalah yang ditanyakan. "
            "Jangan tambahkan tindakan perbaikan, pencegahan, dampak, atau rekomendasi "
            "kecuali diminta secara eksplisit."
        )

    if any(term in normalized for term in ("kapan", "berapa lama", "seberapa cepat", "when", "how long")):
        if is_english:
            return (
                "\n\nSCOPE CONTROL: State the requested time or deadline and at most one "
                "brief explanation supported by the evidence. Do not add nearby SLA facts "
                "that the question did not request."
            )
        return (
            "\n\nBATASAN JAWABAN: Sebutkan waktu atau tenggat yang diminta dan paling banyak "
            "satu penjelasan singkat yang didukung bukti. Jangan tambahkan SLA lain yang "
            "tidak ditanyakan."
        )

    return ""


def _grounding_repair_prompt(
    original_prompt: str,
    previous_answer: str,
    grounding: Any,
    language: str,
) -> str:
    """Ask Gemini to rewrite only the unsupported parts without adding facts."""
    unsupported_claims = list(getattr(grounding, "unsupported_claims", ()) or ())
    unsupported_facts = list(getattr(grounding, "unsupported_facts", ()) or ())
    missing_requirements = list(
        getattr(grounding, "missing_answer_requirements", ()) or ()
    )
    reasons = list(getattr(grounding, "reasons", ()) or ())

    diagnostics: list[str] = []
    if reasons:
        diagnostics.append("Validation failures: " + ", ".join(reasons))
    if unsupported_claims:
        diagnostics.append(
            "Remove or rewrite these unsupported claims: "
            + " | ".join(unsupported_claims)
        )
    if unsupported_facts:
        diagnostics.append(
            "Remove these unsupported explicit facts: "
            + ", ".join(unsupported_facts)
        )
    if missing_requirements:
        diagnostics.append(
            "Still required by the question: "
            + ", ".join(missing_requirements)
        )

    language_instruction = (
        "Return English answer text only."
        if str(language or "ID").upper() == "EN"
        else "Keluarkan teks jawaban dalam Bahasa Indonesia saja."
    )

    return (
        f"{original_prompt}\n\n"
        "MANDATORY GROUNDING CORRECTION:\n"
        + ("\n".join(diagnostics) or "The previous answer was not fully grounded.")
        + "\nRewrite from the beginning using only facts explicitly present in the evidence. "
        "Keep the direct answer, remove every unsupported clause, and do not add a generic "
        "closing, recommendation, consequence, or corrective action unless requested. "
        f"{language_instruction}\n\n"
        f"PREVIOUS ANSWER TO REPLACE:\n{previous_answer or '(empty)'}"
    )


def _log_grounding(stage: str, answer: str, grounding: Any) -> None:
    """Print enough detail to diagnose why Gemini grounding failed."""
    print(
        "[GEMINI_GROUNDING_DEBUG] "
        f"stage={stage} "
        f"supported={getattr(grounding, 'supported', False)} "
        f"score={float(getattr(grounding, 'score', 0.0)):.3f}"
    )
    print(f"[GEMINI_GROUNDING_DEBUG] answer={answer!r}")
    print(
        "[GEMINI_GROUNDING_DEBUG] reasons="
        f"{list(getattr(grounding, 'reasons', ()) or ())!r}"
    )
    print(
        "[GEMINI_GROUNDING_DEBUG] unsupported_facts="
        f"{list(getattr(grounding, 'unsupported_facts', ()) or ())!r}"
    )
    print(
        "[GEMINI_GROUNDING_DEBUG] unsupported_claims="
        f"{list(getattr(grounding, 'unsupported_claims', ()) or ())!r}"
    )


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
        system_prompt = build_system_prompt(language)
        base_user_prompt = (
            build_user_prompt(question, context, language)
            + _scope_instruction(question, language)
        )

        raw_answer = _gemini_chat(system_prompt, base_user_prompt)
        llm_answer = clean_model_answer(raw_answer)

        if llm_answer and not answer_matches_requested_language(llm_answer, language):
            print("[GEMINI] answer language mismatch; requesting a language-only rewrite")
            repaired_raw_answer = _gemini_chat(
                system_prompt,
                build_language_repair_prompt(
                    question,
                    context,
                    llm_answer,
                    language,
                ),
            )
            llm_answer = clean_model_answer(repaired_raw_answer)

        if llm_answer and not answer_matches_requested_language(llm_answer, language):
            print("[GEMINI] answer rejected because output language is still incorrect")
            return ""

        if evaluation_mode:
            if not llm_answer:
                raise RuntimeError("Gemini returned an empty answer")
            return llm_answer

        if (
            not llm_answer
            or is_incomplete_answer(question, llm_answer)
            or is_refusal_answer(llm_answer)
        ):
            return ""

        if ENABLE_GENERATION_GROUNDING_VALIDATION:
            grounding = validate_grounded_answer(
                question,
                llm_answer,
                grounding_chunks,
            )

            if not grounding.supported:
                _log_grounding("initial", llm_answer, grounding)

                # First attempt: let Gemini rewrite only the unsupported clauses.
                repair_raw = _gemini_chat(
                    system_prompt,
                    _grounding_repair_prompt(
                        base_user_prompt,
                        llm_answer,
                        grounding,
                        language,
                    ),
                )
                repaired_answer = clean_model_answer(repair_raw)

                if (
                    repaired_answer
                    and answer_matches_requested_language(repaired_answer, language)
                    and not is_refusal_answer(repaired_answer)
                    and not is_incomplete_answer(question, repaired_answer)
                ):
                    repaired_grounding = validate_grounded_answer(
                        question,
                        repaired_answer,
                        grounding_chunks,
                    )
                    if repaired_grounding.supported:
                        print("[GEMINI] grounding repair accepted")
                        return repaired_answer
                    _log_grounding("repair", repaired_answer, repaired_grounding)

                # Second attempt: deterministic pruning from the same evidence
                # that Gemini actually saw.
                prune_source = repaired_answer or llm_answer
                pruned_answer = clean_model_answer(
                    prune_unsupported_claims(
                        question,
                        prune_source,
                        grounding_chunks,
                    )
                )

                if (
                    pruned_answer
                    and answer_matches_requested_language(pruned_answer, language)
                    and not is_incomplete_answer(question, pruned_answer)
                    and not is_refusal_answer(pruned_answer)
                ):
                    pruned_grounding = validate_grounded_answer(
                        question,
                        pruned_answer,
                        grounding_chunks,
                    )
                    if pruned_grounding.supported:
                        print("[GEMINI] removed unsupported clauses")
                        return pruned_answer
                    _log_grounding("pruned", pruned_answer, pruned_grounding)

                print("[GEMINI] native answer rejected by grounding validator")
                return ""

        return llm_answer

    except Exception as exc:
        if evaluation_mode:
            raise RuntimeError("Gemini native generation failed: " + str(exc)) from exc
        print(f"[GEMINI] native generation failed: {exc}")
        return ""
