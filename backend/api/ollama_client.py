import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from api.answer_formatter import (
    answer_text_only,
    build_generation_evidence,
    build_refusal_answer,
    build_safe_extractive_answer,
    has_answerable_evidence,
    is_refusal_answer,
    top_confidence,
)
from retrieval.requirements import (
    extract_evidence_requirements,
    requirement_satisfied,
)
from api.grounding_validator import prune_unsupported_claims, validate_grounded_answer
from api.language import answer_matches_requested_language
from api.llm_shared import build_language_repair_prompt
from uploads.config import ENABLE_GENERATION_GROUNDING_VALIDATION, MAX_GENERATION_CONTEXTS

# Ollama configuration is read from the project-root .env through uploads.config,
# which is imported by answer_formatter before these values are evaluated.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-custom:latest")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "640"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
OLLAMA_MAX_RETRIES = max(0, int(os.getenv("OLLAMA_MAX_RETRIES", "1")))

MAX_CONTEXT_CHARS_PER_CHUNK = 1400
MAX_CONTEXT_CHUNKS = MAX_GENERATION_CONTEXTS
MAX_ANSWER_CHARS = 1600


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _build_context(question: str, chunks: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks[:MAX_CONTEXT_CHUNKS], start=1):
        raw_content = _clean_text(chunk.get("content"))
        if not raw_content:
            continue
        content = _clean_text(
            build_generation_evidence(
                question,
                raw_content,
                max_chars=MAX_CONTEXT_CHARS_PER_CHUNK,
            )
        ) or raw_content
        if len(content) > MAX_CONTEXT_CHARS_PER_CHUNK:
            content = content[:MAX_CONTEXT_CHARS_PER_CHUNK].rsplit(" ", 1)[0] + "…"

        metadata = chunk.get("metadata") or {}
        name = (
            chunk.get("documentName")
            or chunk.get("document_name")
            or metadata.get("filename")
            or "-"
        )
        page = chunk.get("page", metadata.get("page")) or "-"
        blocks.append(
            f"[KONTEKS {index}]\n"
            f"Dokumen: {name}\n"
            f"Halaman/lokasi: {page}\n"
            f"Bukti: {content}"
        )
    return "\n\n".join(blocks)


def _build_grounding_chunks(
    question: str,
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build chunks containing exactly the evidence shown to Ollama.

    The grounding validator, extractive fallback, source response, and
    evaluator must inspect the same compact passage. Validation against a
    larger raw chunk can incorrectly approve facts that were not present in
    the model prompt.
    """

    grounded_chunks: list[dict[str, Any]] = []

    for chunk in chunks[:MAX_CONTEXT_CHUNKS]:
        raw_content = _clean_text(
            chunk.get("content")
        )

        if not raw_content:
            continue

        excerpt = _clean_text(
            build_generation_evidence(
                question,
                raw_content,
                max_chars=MAX_CONTEXT_CHARS_PER_CHUNK,
            )
        ) or raw_content

        if len(excerpt) > MAX_CONTEXT_CHARS_PER_CHUNK:
            excerpt = (
                excerpt[:MAX_CONTEXT_CHARS_PER_CHUNK]
                .rsplit(" ", 1)[0]
                .strip()
                + "?"
            )

        cloned_chunk = dict(chunk)
        cloned_chunk["content"] = excerpt

        metadata = dict(
            chunk.get("metadata") or {}
        )
        metadata["content"] = excerpt
        cloned_chunk["metadata"] = metadata

        grounded_chunks.append(cloned_chunk)

    return grounded_chunks


def _clean_model_answer(answer: str) -> str:
    text = answer_text_only(answer)
    if len(text) > MAX_ANSWER_CHARS:
        text = text[:MAX_ANSWER_CHARS].rsplit(" ", 1)[0].strip() + "…"
    return text


def _fallback_answer(question: str, chunks: list[dict[str, Any]], language: str) -> str:
    answer = _clean_model_answer(
        build_safe_extractive_answer(question, chunks, language=language)
    )
    if not answer or is_refusal_answer(answer):
        return build_refusal_answer(language)
    return answer


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
    """Call Ollama once and return (answer_text, done_reason).

    Qwen3 thinking is explicitly disabled so the output budget is used for the
    visible answer. The done_reason is retained to detect token-limit truncation.
    """
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
    """Estimate how many numeric values the question explicitly asks for."""
    text = _clean_text(question).lower()
    if not text:
        return 0

    # Repeated "berapa" is the strongest signal: "berapa total ... dan berapa ...".
    repeated_how_many = len(re.findall(r"\bberapa\b", text))
    if repeated_how_many >= 2:
        return repeated_how_many

    metric_terms = {
        "pendapatan",
        "revenue",
        "margin",
        "persentase",
        "percentage",
        "laba",
        "profit",
        "biaya",
        "cost",
        "durasi",
        "lama",
        "jumlah",
        "total",
        "rate",
        "tingkat",
    }
    matched_metrics = sum(1 for term in metric_terms if term in text)

    # A conjunction between multiple metric terms usually requests multiple values.
    if matched_metrics >= 2 and re.search(r"\b(?:dan|serta|and)\b", text):
        return 2
    return 1 if repeated_how_many == 1 else 0


def _answer_numeric_values(answer: str) -> list[str]:
    """Extract distinct answer quantities such as IDR 158 billion and 14%."""
    clean = _clean_text(answer)
    matches = re.findall(
        r"(?:Rp\.?|IDR|USD|EUR)?\s*\d[\d.,]*(?:\s*(?:%|persen|percent|juta|miliar|billion|triliun|trillion|jam|hari|minggu|bulan|tahun))?",
        clean,
        flags=re.I,
    )
    values: list[str] = []
    seen: set[str] = set()
    for match in matches:
        value = _clean_text(match).casefold()
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return values


def _is_likely_incomplete_answer(
    question: str,
    answer: str,
    done_reason: str = "",
) -> bool:
    """Detect a blank, visibly cut, or materially incomplete model answer."""
    clean_answer = _clean_text(answer)
    if not clean_answer:
        return True

    if done_reason in {"length", "max_tokens", "token_limit"}:
        return True

    words = clean_answer.split()
    if len(words) < 6:
        # Short factual answers are valid for questions such as "What database?",
        # "What mailbox limit?", or "When is payday?". Only treat a short answer
        # as incomplete when it fails an explicit answer-type requirement and does
        # not contain a substantive identifier or quantity.
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
        ":",
        ",",
        ";",
        "-",
        " dan",
        " atau",
        " yaitu",
        " sebesar",
        " adalah",
        " dengan",
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
        "Answer every requested part and retain relevant supporting details that are explicitly stated, but "
        "do not add assumptions, identifiers, numbers, conditions, exceptions, causal reasons, benefits, or "
        "implications that are absent from the evidence. Use a connected 2-to-4-sentence paragraph when the "
        "evidence supports it; otherwise stop after the supported fact. Do not add filler or a generic closing.\n\n"
        f"PREVIOUS ANSWER TO REPLACE:\n{previous_answer or '(empty)'}"
    )


def build_ollama_grounded_answer(
    question: str,
    chunks: list[dict[str, Any]],
    language: str = "ID",
    evaluation_mode: bool = False,
) -> str:
    """Generate only the answer text.

    Source metadata and confidence are intentionally excluded here. They are
    assembled by the chat service into separate response fields.
    """
    confidence = top_confidence(chunks, question=question)
    bundle_answerable = has_answerable_evidence(chunks)

    if confidence <= 0 and not bundle_answerable:
        return build_refusal_answer(language)

    grounding_chunks = _build_grounding_chunks(question, chunks)
    context = _build_context(question, grounding_chunks)
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

    language_rule = (
        "MANDATORY OUTPUT LANGUAGE: English only. Translate Indonesian evidence into natural English. "
        if is_english
        else (
            "MANDATORY OUTPUT LANGUAGE: Bahasa Indonesia only. Translate English evidence into natural "
            "Bahasa Indonesia. Do not copy English sentences except proper names, product names, codes, "
            "and acronyms. "
        )
    )
    system_prompt = (
        language_rule
        + "You are a strict enterprise Retrieval-Augmented Generation assistant. "
        "Use only the supplied evidence. Do not use outside knowledge. "
        "Start with the direct answer. Use the evidence facts, but translate ordinary wording into the "
        "mandatory output language. When useful supporting details exist, continue with a coherent paragraph "
        "of 2 to 4 informative sentences. Explain only definitions, relationships, scope, conditions, or "
        "consequences explicitly stated in the evidence. Prefer complementary facts from two or more evidence "
        "blocks when relevant. If only one fact is supported, stop instead of padding the answer. "
        "Do not add an introduction, recommendation, citation, confidence, heading, label, assumption, "
        "example, outside inference, repetition, or a generic closing sentence. "
        "Never replace a supported answer with a refusal. "
        "Do not combine details from different evidence blocks into one claim unless the question explicitly "
        "requires both details."
    )

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
            "Translate any Indonesian evidence needed for the answer. Start with the direct answer, then "
            "write 2 to 4 connected sentences when the evidence supports relevant explanation. Use multiple "
            "evidence blocks when they add complementary facts. Do not repeat facts, add filler, or infer "
            "anything absent from the evidence. Output answer text only. ENGLISH ONLY."
        )
    else:
        user_prompt = (
            f"PERTANYAAN:\n{question}\n\n"
            f"BUKTI:\n{context}\n\n"
            f"{requirement_instruction}\n"
            f"{completeness_instruction}"
            "Terjemahkan bukti berbahasa Inggris yang diperlukan. Mulai dengan jawaban langsung, lalu tulis "
            "2 sampai 4 kalimat yang saling terhubung jika bukti mendukung penjelasan relevan. Gabungkan "
            "beberapa blok bukti bila masing-masing menambahkan fakta yang saling melengkapi. Jangan "
            "mengulang fakta, menambah basa-basi, atau menyimpulkan hal yang tidak ada dalam bukti. "
            "Jangan menyalin kalimat bahasa Inggris kecuali nama diri, "
            "nama produk, kode, dan akronim. Keluarkan teks jawaban saja. BAHASA INDONESIA SAJA."
        )

    try:
        raw_answer, done_reason = _ollama_chat(system_prompt, user_prompt)
        llm_answer = _clean_model_answer(raw_answer)

        if llm_answer and not answer_matches_requested_language(llm_answer, language):
            print("[OLLAMA] answer language mismatch; requesting a language-only rewrite")
            raw_answer, done_reason = _ollama_chat(
                system_prompt,
                build_language_repair_prompt(
                    question,
                    context,
                    llm_answer,
                    language,
                ),
                num_predict=max(OLLAMA_NUM_PREDICT, 800),
            )
            llm_answer = _clean_model_answer(raw_answer)

        # Use the first language-correct native model response for cross-provider evaluation.
        # Production mode keeps the existing retry/grounding/fallback guards.
        if evaluation_mode:
            if not llm_answer:
                raise RuntimeError("Ollama returned an empty answer")
            if not answer_matches_requested_language(llm_answer, language):
                raise RuntimeError("Ollama returned an answer in the wrong language")
            return llm_answer

        retry_count = 0
        while retry_count < OLLAMA_MAX_RETRIES:
            incomplete = _is_likely_incomplete_answer(question, llm_answer, done_reason)
            wrong_language = bool(
                llm_answer
                and not answer_matches_requested_language(llm_answer, language)
            )
            grounding = (
                validate_grounded_answer(question, llm_answer, grounding_chunks)
                if ENABLE_GENERATION_GROUNDING_VALIDATION and llm_answer and not wrong_language
                else None
            )
            if (
                not incomplete
                and not wrong_language
                and (grounding is None or grounding.supported)
            ):
                break

            retry_count += 1
            raw_answer, done_reason = _ollama_chat(
                system_prompt,
                _repair_prompt(
                    user_prompt,
                    llm_answer,
                    reasons=(
                        grounding.reasons
                        if grounding is not None
                        else (("wrong_output_language",) if wrong_language else ("incomplete_answer",))
                    ),
                    unsupported_facts=grounding.unsupported_facts if grounding is not None else (),
                    unsupported_claims=grounding.unsupported_claims if grounding is not None else (),
                    missing_requirements=(
                        grounding.missing_answer_requirements if grounding is not None else ()
                    ),
                ),
                num_predict=max(OLLAMA_NUM_PREDICT, 800),
            )
            llm_answer = _clean_model_answer(raw_answer)

    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, Exception) as exc:
        if evaluation_mode:
            raise RuntimeError("Ollama native generation failed: " + str(exc)) from exc
        # Keep the application usable when Ollama is offline or a model call fails.
        print(f"[OLLAMA] native generation failed: {exc}")
        return ""

    # Do not return a visibly incomplete fragment. The deterministic formatter
    # extracts the strongest supported sentences from the same retrieved chunks.
    if _is_likely_incomplete_answer(question, llm_answer, done_reason):
        print(
            "[OLLAMA] incomplete answer after retry; returning control to chat service "
            f"(done_reason={done_reason or 'unknown'})"
        )
        return ""

    if not llm_answer:
        return ""

    if not answer_matches_requested_language(llm_answer, language):
        print("[OLLAMA] answer rejected because output language is still incorrect")
        return ""

    if ENABLE_GENERATION_GROUNDING_VALIDATION:
        grounding = validate_grounded_answer(question, llm_answer, grounding_chunks)
        if not grounding.supported:
            # Preserve the supported part of a useful answer before falling back.
            # This removes hallucinated explanatory tails without converting an
            # answerable question into a refusal.
            pruned_answer = _clean_model_answer(
                prune_unsupported_claims(question, llm_answer, chunks)
            )
            if pruned_answer:
                pruned_grounding = validate_grounded_answer(question, pruned_answer, chunks)
                if (
                    pruned_grounding.supported
                    and not _is_likely_incomplete_answer(question, pruned_answer)
                    and not is_refusal_answer(pruned_answer)
                    and answer_matches_requested_language(pruned_answer, language)
                ):
                    print(
                        "[GROUNDING] removed unsupported clauses: "
                        + ", ".join(grounding.reasons)
                    )
                    return pruned_answer

            print(
                "[GROUNDING] generated answer rejected; returning control to chat service: "
                + ", ".join(grounding.reasons)
            )
            return ""

    if is_refusal_answer(llm_answer):
        # Retrieval and answerability already established evidence. A model-level
        # refusal is therefore treated as a generation failure, not as proof that
        # the corpus lacks an answer.
        return ""

    return llm_answer
