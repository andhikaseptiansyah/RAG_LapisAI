import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from api.answer_formatter import (
    answer_text_only,
    build_grounded_answer,
    build_refusal_answer,
    is_refusal_answer,
    top_confidence,
)

# Ollama configuration is read from the project-root .env through uploads.config,
# which is imported by answer_formatter before these values are evaluated.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-custom:latest")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "640"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
OLLAMA_MAX_RETRIES = max(0, int(os.getenv("OLLAMA_MAX_RETRIES", "1")))

MAX_CONTEXT_CHARS_PER_CHUNK = 1400
MAX_CONTEXT_CHUNKS = 4
MAX_ANSWER_CHARS = 1400


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _build_context(chunks: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks[:MAX_CONTEXT_CHUNKS], start=1):
        content = _clean_text(chunk.get("content"))
        if not content:
            continue
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
        score = chunk.get("score") or 0
        blocks.append(
            f"[KONTEKS {index}]\n"
            f"Dokumen: {name}\n"
            f"Halaman/lokasi: {page}\n"
            f"Skor: {score}\n"
            f"Isi: {content}"
        )
    return "\n\n".join(blocks)


def _clean_model_answer(answer: str) -> str:
    text = answer_text_only(answer)
    if len(text) > MAX_ANSWER_CHARS:
        text = text[:MAX_ANSWER_CHARS].rsplit(" ", 1)[0].strip() + "…"
    return text


def _fallback_answer(question: str, chunks: list[dict[str, Any]], language: str) -> str:
    answer = _clean_model_answer(
        build_grounded_answer(question, chunks, language=language)
    )
    if not answer or is_refusal_answer(answer):
        return build_refusal_answer(language)
    return answer


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
            "temperature": 0.1,
            "top_p": 0.85,
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


def _repair_prompt(original_user_prompt: str, previous_answer: str) -> str:
    return (
        f"{original_user_prompt}\n\n"
        "INSTRUKSI PERBAIKAN WAJIB:\n"
        "Jawaban sebelumnya tidak lengkap atau terpotong. Tulis ulang dari awal, "
        "bukan melanjutkan fragmen sebelumnya. Jawab seluruh bagian pertanyaan "
        "dengan fakta dari konteks. Bila pertanyaan meminta beberapa angka atau "
        "metrik, tuliskan semuanya secara eksplisit dalam satu jawaban lengkap. "
        "Jangan hanya menulis judul, pembuka, atau label.\n\n"
        f"JAWABAN SEBELUMNYA YANG TIDAK LENGKAP:\n{previous_answer or '(kosong)'}"
    )


def build_ollama_grounded_answer(
    question: str,
    chunks: list[dict[str, Any]],
    language: str = "ID",
) -> str:
    """Generate only the answer text.

    Source metadata and confidence are intentionally excluded here. They are
    assembled by the chat service into separate response fields.
    """
    confidence = top_confidence(chunks, question=question)

    if confidence <= 0:
        return build_refusal_answer(language)

    context = _build_context(chunks)
    if not context:
        return build_refusal_answer(language)

    is_english = language.upper() == "EN"
    system_prompt = (
        "You are a strict Retrieval-Augmented Generation assistant. "
        "Answer ONLY using the provided context. "
        "Do not use outside knowledge. Do not invent facts. "
        "If the answer is not clearly supported by the context, say it is not found. "
        "Answer every requested part before stopping. "
        "When the question asks for multiple values or metrics, include every requested value explicitly. "
        "Keep the answer concise, complete, and useful. "
        "Match every constraint in the question: actor, condition, date, amount, duration, and requested outcome. "
        "Do not replace the requested metric with a related metric, for example first response instead of final resolution. "
        "When several contexts are needed, combine only the explicitly supported facts. "
        "Do not write citations, source lists, confidence values, headings, labels, or model names."
    )

    if is_english:
        user_prompt = (
            f"QUESTION:\n{question}\n\n"
            f"CONTEXT:\n{context}\n\n"
            "Write a complete answer in English. Use one short paragraph or at most five bullet points. "
            "Answer all parts of the question and include every requested value. "
            "Only include facts explicitly supported by the context."
        )
    else:
        user_prompt = (
            f"PERTANYAAN:\n{question}\n\n"
            f"KONTEKS DOKUMEN:\n{context}\n\n"
            "Tulis jawaban lengkap dalam Bahasa Indonesia. Gunakan satu paragraf pendek atau maksimal lima poin. "
            "Jawab semua bagian pertanyaan dan tuliskan setiap nilai yang diminta. "
            "Hanya tulis fakta yang jelas ada di konteks dokumen. Jangan mengarang."
        )

    try:
        raw_answer, done_reason = _ollama_chat(system_prompt, user_prompt)
        llm_answer = _clean_model_answer(raw_answer)

        retry_count = 0
        while (
            _is_likely_incomplete_answer(question, llm_answer, done_reason)
            and retry_count < OLLAMA_MAX_RETRIES
        ):
            retry_count += 1
            raw_answer, done_reason = _ollama_chat(
                system_prompt,
                _repair_prompt(user_prompt, llm_answer),
                num_predict=max(OLLAMA_NUM_PREDICT, 800),
            )
            llm_answer = _clean_model_answer(raw_answer)

    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, Exception) as exc:
        # Keep the application usable when Ollama is offline or a model call fails.
        print(f"[OLLAMA] fallback to formatter: {exc}")
        return _fallback_answer(question, chunks, language)

    # Do not return a visibly incomplete fragment. The deterministic formatter
    # extracts the strongest supported sentences from the same retrieved chunks.
    if _is_likely_incomplete_answer(question, llm_answer, done_reason):
        print(
            "[OLLAMA] incomplete answer after retry; using grounded formatter "
            f"(done_reason={done_reason or 'unknown'})"
        )
        return _fallback_answer(question, chunks, language)

    if not llm_answer or is_refusal_answer(llm_answer):
        return build_refusal_answer(language)

    return llm_answer
