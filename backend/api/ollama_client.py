import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from api.llm_shared import (
    SYSTEM_PROMPT,
    build_context,
    build_grounding_chunks,
    clean_model_answer,
    clean_text,
    fallback_answer,
)
from api.answer_formatter import build_refusal_answer, has_answerable_evidence, is_refusal_answer, top_confidence
from retrieval.requirements import (
    extract_evidence_requirements,
    requirement_satisfied,
)
from api.grounding_validator import prune_unsupported_claims, validate_grounded_answer
from uploads.config import ENABLE_GENERATION_GROUNDING_VALIDATION

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-custom:latest")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "640"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
OLLAMA_MAX_RETRIES = max(0, int(os.getenv("OLLAMA_MAX_RETRIES", "1")))


def _answer_requirements(question: str) -> list[Any]:
    return [
        requirement
        for requirement in extract_evidence_requirements(question)
        if requirement.key.startswith("answer_")
    ]


def _requirements_complete(question: str, answer: str) -> bool:
    requirements = _answer_requirements(question)
    return bool(requirements) and all(
        requirement_satisfied(requirement, [answer])
        for requirement in requirements
    )


def _requirement_instruction(question: str) -> str:
    descriptions = [requirement.description for requirement in _answer_requirements(question)]
    if not descriptions:
        return "Answer only the exact fact requested by the question."
    return "Required answer facts: " + "; ".join(descriptions) + "."


def _ollama_chat(
    system_prompt: str,
    user_prompt: str,
    *,
    num_predict: int | None = None,
) -> tuple[str, str]:
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "think": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": 0.0,
            "top_p": 0.80,
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": int(num_predict or OLLAMA_NUM_PREDICT),
        },
    }

    request = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
        data = json.loads(response.read().decode("utf-8"))

    message = data.get("message") or {}
    content = message.get("content") or data.get("response") or ""
    done_reason = str(data.get("done_reason") or "").strip().lower()
    return str(content).strip(), done_reason


def _question_expected_numeric_values(question: str) -> int:
    text = clean_text(question).lower()
    if not text:
        return 0

    repeated_how_many = len(re.findall(r"\bberapa\b", text))
    if repeated_how_many >= 2:
        return repeated_how_many

    metric_terms = {
        "pendapatan", "revenue", "margin", "persentase", "percentage",
        "laba", "profit", "biaya", "cost", "durasi", "lama", "jumlah",
        "total", "rate", "tingkat",
    }
    matched_metrics = sum(1 for term in metric_terms if term in text)

    if matched_metrics >= 2 and re.search(r"\b(?:dan|serta|and)\b", text):
        return 2
    return 1 if repeated_how_many == 1 else 0


def _answer_numeric_values(answer: str) -> list[str]:
    clean = clean_text(answer)
    matches = re.findall(
        r"(?:Rp\.?|IDR|USD|EUR)?\s*\d[\d.,]*(?:\s*(?:%|persen|percent|juta|miliar|billion|triliun|trillion|jam|hari|minggu|bulan|tahun))?",
        clean,
        flags=re.I,
    )
    values: list[str] = []
    seen: set[str] = set()
    for match in matches:
        value = clean_text(match).casefold()
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return values


def _is_likely_incomplete_answer(
    question: str,
    answer: str,
    done_reason: str = "",
) -> bool:
    clean_answer = clean_text(answer)
    if not clean_answer:
        return True

    if done_reason in {"length", "max_tokens", "token_limit"}:
        return True

    words = clean_answer.split()
    if len(words) < 6:
        if _requirements_complete(question, clean_answer):
            return False
        if re.search(
            r"(?:\b[A-Za-z][A-Za-z0-9_.-]{2,}\b|\b\d[\d.,]*(?:\s*%|\s*[A-Za-z]+)?)",
            clean_answer,
        ) and clean_answer[-1:] in ".!?":
            return False
        return True

    lower_answer = clean_answer.casefold()
    incomplete_endings = (
        ":", ",", ";", "-", " dan", " atau",
        " yaitu", " sebesar", " adalah", " dengan",
    )
    if lower_answer.endswith(incomplete_endings):
        return True

    expected_values = _question_expected_numeric_values(question)
    if expected_values >= 2 and len(_answer_numeric_values(clean_answer)) < expected_values:
        return True

    return False


def _repair_prompt(
    original_user_prompt: str,
    previous_answer: str,
    *,
    reasons: tuple[str, ...] = (),
    unsupported_facts: tuple[str, ...] = (),
    unsupported_claims: tuple[str, ...] = (),
    missing_requirements: tuple[str, ...] = (),
) -> str:
    diagnostics: list[str] = []
    if reasons:
        diagnostics.append("Validation failures: " + ", ".join(reasons))
    if unsupported_facts:
        diagnostics.append("Unsupported facts that must be removed: " + ", ".join(unsupported_facts))
    if unsupported_claims:
        diagnostics.append("Unsupported claims that must be removed: " + " | ".join(unsupported_claims))
    if missing_requirements:
        diagnostics.append("Requested answer types still missing: " + ", ".join(missing_requirements))
    diagnostic_text = "\n".join(diagnostics) or "The previous answer was incomplete or insufficiently grounded."
    return (
        f"{original_user_prompt}\n\n"
        "MANDATORY CORRECTION:\n"
        f"{diagnostic_text}\n"
        "Rewrite the answer from the beginning. Use only facts explicitly stated in the evidence. "
        "Answer every requested part, but do not add explanations, assumptions, identifiers, numbers, "
        "conditions, exceptions, causal reasons, benefits, or implications that are absent from the evidence. "
        "Do not defend or explain the answer. Keep it concise.\n\n"
        f"PREVIOUS ANSWER TO REPLACE:\n{previous_answer or '(empty)'}"
    )


def build_ollama_grounded_answer(
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

    is_english = language.upper() == "EN"
    requirement_instruction = _requirement_instruction(question)
    bundle_missing = {
        key
        for chunk in chunks
        for key in (chunk.get("contextBundleMissingRequirements") or [])
    }
    evidence_complete = bundle_answerable and not bundle_missing

    completeness_instruction = (
        "The evidence bundle has already passed answerability checks. Do not state that information is missing. "
        if evidence_complete
        else "If one requested part is absent, answer the supported part and name only the missing part. "
    )

    if is_english:
        user_prompt = (
            f"QUESTION:\n{question}\n\n"
            f"EVIDENCE:\n{context}\n\n"
            f"{requirement_instruction}\n"
            f"{completeness_instruction}"
            "Write the shortest complete answer in English. Output answer text only."
        )
    else:
        user_prompt = (
            f"PERTANYAAN:\n{question}\n\n"
            f"BUKTI:\n{context}\n\n"
            f"{requirement_instruction}\n"
            f"{completeness_instruction}"
            "Tulis jawaban lengkap yang paling singkat dalam Bahasa Indonesia. Keluarkan teks jawaban saja."
        )

    try:
        raw_answer, done_reason = _ollama_chat(SYSTEM_PROMPT, user_prompt)
        llm_answer = clean_model_answer(raw_answer)

        retry_count = 0
        while retry_count < OLLAMA_MAX_RETRIES:
            incomplete = _is_likely_incomplete_answer(question, llm_answer, done_reason)
            grounding = (
                validate_grounded_answer(question, llm_answer, grounding_chunks)
                if ENABLE_GENERATION_GROUNDING_VALIDATION and llm_answer
                else None
            )
            if not incomplete and (grounding is None or grounding.supported):
                break

            retry_count += 1
            raw_answer, done_reason = _ollama_chat(
                SYSTEM_PROMPT,
                _repair_prompt(
                    user_prompt,
                    llm_answer,
                    reasons=grounding.reasons if grounding is not None else ("incomplete_answer",),
                    unsupported_facts=grounding.unsupported_facts if grounding is not None else (),
                    unsupported_claims=grounding.unsupported_claims if grounding is not None else (),
                    missing_requirements=(
                        grounding.missing_answer_requirements if grounding is not None else ()
                    ),
                ),
                num_predict=max(OLLAMA_NUM_PREDICT, 800),
            )
            llm_answer = clean_model_answer(raw_answer)

    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, Exception) as exc:
        print(f"[OLLAMA] fallback to formatter: {exc}")
        return fallback_answer(question, grounding_chunks, language)

    if _is_likely_incomplete_answer(question, llm_answer, done_reason):
        print(
            "[OLLAMA] incomplete answer after retry; using grounded formatter "
            f"(done_reason={done_reason or 'unknown'})"
        )
        return fallback_answer(question, grounding_chunks, language)

    if not llm_answer:
        return fallback_answer(question, grounding_chunks, language)

    if ENABLE_GENERATION_GROUNDING_VALIDATION:
        grounding = validate_grounded_answer(question, llm_answer, grounding_chunks)
        if not grounding.supported:
            pruned_answer = clean_model_answer(
                prune_unsupported_claims(question, llm_answer, chunks)
            )
            if pruned_answer:
                pruned_grounding = validate_grounded_answer(question, pruned_answer, chunks)
                if (
                    pruned_grounding.supported
                    and not _is_likely_incomplete_answer(question, pruned_answer)
                    and not is_refusal_answer(pruned_answer)
                ):
                    print(
                        "[GROUNDING] removed unsupported clauses: "
                        + ", ".join(grounding.reasons)
                    )
                    return pruned_answer

            print(
                "[GROUNDING] generated answer rejected; using extractive fallback: "
                + ", ".join(grounding.reasons)
            )
            return fallback_answer(question, grounding_chunks, language)

    if is_refusal_answer(llm_answer):
        return fallback_answer(question, grounding_chunks, language)

    return llm_answer
