import re
from difflib import SequenceMatcher
from typing import Any

from uploads.config import (
    MIN_ANSWER_CONFIDENCE,
    MIN_SOURCE_CONFIDENCE,
    SOURCE_EXCERPT_MAX_CHARS,
    MAX_SOURCE_CITATIONS,
)
from retrieval.requirements import (
    extract_evidence_requirements,
    requirement_satisfied,
)

# Confidence dipisahkan antara gerbang jawaban dan gerbang sumber.
# Nilainya dimuat melalui uploads.config supaya project-root .env selalu dibaca
# sebelum threshold digunakan, terlepas dari urutan import modul FastAPI.
EXACT_DEFINITION_CONFIDENCE = 0.90
EXACT_TOKEN_CONFIDENCE = 0.84
MAX_BULLETS = 2
MAX_SENTENCE_CHARS = 220
MAX_TOTAL_ANSWER_CHARS = 850

STOPWORDS = {
    "apa", "apakah", "bagaimana", "gimana", "jelaskan", "sebutkan", "siapa", "kapan",
    "dimana", "di", "ke", "dari", "yang", "dan", "atau", "untuk", "dengan", "dalam",
    "ini", "itu", "tersebut", "dokumen", "file", "nya", "adalah", "pada", "tentang",
    "tolong", "ringkas", "buat", "kan", "dong", "coba", "bahasa", "indonesia",
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are",
    "what", "how", "who", "when", "where", "why", "explain", "describe", "document",
}

DEFINITION_PATTERNS = [
    r"\bapa\s+itu\s+([A-Za-z0-9_.\-]+)",
    r"\bapa\s+yang\s+dimaksud\s+dengan\s+([A-Za-z0-9_.\-]+)",
    r"\bwhat\s+is\s+([A-Za-z0-9_.\-]+)",
    r"\bwhat\s+does\s+([A-Za-z0-9_.\-]+)\s+mean",
]

NOISE_KEYWORDS = [
    "daftar pustaka", "references", "gambar ", "tabel ", "issn", "vol ",
    "halaman barang", "menambahkan barang", "pencarian barang",
]

INVENTORY_DATA_TERMS = {
    "kode aset": "Kode aset",
    "nama barang": "Nama barang",
    "merk": "Merk",
    "merek": "Merek",
    "tipe": "Tipe",
    "lokasi barang": "Lokasi barang",
    "lokasi": "Lokasi barang",
    "owner": "Pemilik alat / owner",
    "pemilik alat": "Pemilik alat / owner",
    "jumlah barang": "Jumlah barang",
    "jumlah": "Jumlah barang",
    "barang masuk": "Data barang masuk",
    "barang keluar": "Data barang keluar",
    "stok": "Stok / persediaan",
    "persediaan": "Stok / persediaan",
}

INVENTORY_QUESTION_HINTS = {
    "data", "barang", "gudang", "inventori", "inventory", "pencatatan",
    "aset", "masuk", "keluar", "persediaan", "subjek", "bahan",
}


SMALL_TALK_GREETINGS = {
    "hai", "hi", "halo", "hallo", "hello", "helo", "hey", "hei",
    "pagi", "siang", "sore", "malam", "selamat pagi", "selamat siang",
    "selamat sore", "selamat malam", "assalamualaikum", "assalamu alaikum",
}

SMALL_TALK_THANKS = {
    "makasih", "terima kasih", "terimakasih", "thanks", "thank you", "tq",
    "sip", "oke makasih", "ok makasih",
}

SMALL_TALK_IDENTITY = {
    "siapa kamu", "kamu siapa", "ini apa", "apa itu lapisai", "lapisai itu apa",
    "what are you", "who are you",
}

SMALL_TALK_HELP = {
    "kamu bisa apa", "bisa bantu apa", "apa yang bisa kamu lakukan", "cara pakai",
    "how to use", "what can you do",
}


def _normalize_small_talk(text: str) -> str:
    value = str(text or "").strip().lower()
    value = re.sub(r"[?!.,;:]+", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def is_small_talk(text: str) -> bool:
    """Deteksi sapaan/obrolan ringan supaya tidak dilempar ke retrieval dokumen."""
    normalized = _normalize_small_talk(text)
    if not normalized:
        return False

    exact_phrases = (
        SMALL_TALK_GREETINGS
        | SMALL_TALK_THANKS
        | SMALL_TALK_IDENTITY
        | SMALL_TALK_HELP
    )

    if normalized in exact_phrases:
        return True

    # Toleransi untuk sapaan pendek seperti "hai kak" / "halo min".
    greeting_prefixes = ("hai ", "hi ", "halo ", "hallo ", "hello ", "hey ")
    if len(normalized) <= 24 and normalized.startswith(greeting_prefixes):
        return True

    # Jangan anggap pertanyaan dokumen sebagai small talk walau diawali halo.
    document_terms = {"dokumen", "file", "pdf", "jurnal", "data", "barang", "gudang", "jitek"}
    if any(term in normalized for term in document_terms):
        return False

    return False


def build_small_talk_answer(text: str, language: str = "ID") -> str:
    normalized = _normalize_small_talk(text)
    is_english = language.upper() == "EN"

    if normalized in SMALL_TALK_THANKS:
        if is_english:
            return (
                "Answer:\n"
                "You're welcome. Ask me anything about the uploaded documents whenever you're ready.\n\n"
                "Model: system-small-talk"
            )
        return (
            "Jawaban:\n"
            "Sama-sama. Kalau ada bagian dokumen yang mau dicari, diringkas, atau dicek sumbernya, langsung tanya aja.\n\n"
            "Model: system-small-talk"
        )

    if normalized in SMALL_TALK_IDENTITY:
        if is_english:
            return (
                "Answer:\n"
                "I am LapisAI, a document-based RAG assistant. I answer using documents that have been uploaded and indexed.\n\n"
                "Model: system-small-talk"
            )
        return (
            "Jawaban:\n"
            "Aku LapisAI, asisten RAG yang bantu jawab pertanyaan berdasarkan dokumen yang sudah kamu upload dan index.\n\n"
            "Model: system-small-talk"
        )

    if normalized in SMALL_TALK_HELP:
        if is_english:
            return (
                "Answer:\n"
                "I can help summarize indexed documents, answer document-based questions, show sources, and check relevant pages.\n\n"
                "Model: system-small-talk"
            )
        return (
            "Jawaban:\n"
            "Aku bisa bantu menjawab pertanyaan dari dokumen, meringkas isi dokumen, menampilkan sumber halaman, dan mengecek informasi yang relevan.\n\n"
            "Model: system-small-talk"
        )

    if is_english:
        return (
            "Answer:\n"
            "Hi! I am ready to help answer questions based on the documents you have uploaded and indexed.\n\n"
            "Model: system-small-talk"
        )

    return (
        "Jawaban:\n"
        "Hai! Aku siap bantu menjawab pertanyaan berdasarkan dokumen yang sudah kamu upload dan index. Silakan tanya isi dokumennya.\n\n"
        "Model: system-small-talk"
    )


def _clean_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9]+", text.lower())
    return [token for token in tokens if len(token) > 2 and token not in STOPWORDS]


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp_score(value: Any) -> float:
    score = _to_float(value, 0.0)
    if score > 1:
        score = score / 100 if score <= 100 else 1.0
    return max(0.0, min(score, 1.0))


def _split_sentences(text: str) -> list[str]:
    clean = _clean_text(text)
    if not clean:
        return []

    # Pisahkan bagian noisy supaya jawaban tidak dump satu halaman penuh.
    clean = re.sub(
        r"\b(Gambar|Tabel|DAFTAR PUSTAKA|REFERENCES|SIMPULAN|KESIMPULAN)\b",
        r". \1",
        clean,
        flags=re.I,
    )
    candidates = re.split(r"(?<=[.!?])\s+|\s+[•\-–]\s+|\n+", clean)
    sentences: list[str] = []

    for candidate in candidates:
        sentence = _clean_text(candidate)
        if len(sentence) < 20:
            continue
        if len(sentence) > MAX_SENTENCE_CHARS:
            sentence = sentence[:MAX_SENTENCE_CHARS].rsplit(" ", 1)[0].strip() + "…"
        if sentence and sentence not in sentences:
            sentences.append(sentence)

    if not sentences and clean:
        excerpt = clean[:MAX_SENTENCE_CHARS].rsplit(" ", 1)[0].strip()
        sentences.append(excerpt + ("…" if len(clean) > len(excerpt) else ""))

    return sentences


_SOURCE_DURATION_WORDS = {
    "hour", "hours", "day", "days", "week", "weeks", "month", "months",
    "jam", "hari", "minggu", "bulan", "tahun", "minute", "minutes", "menit",
}


def _source_excerpt_segments(value: Any) -> list[str]:
    """Split source text into exact, readable evidence units.

    Line wrapping from PDF/TXT extraction is normalized, while document wording
    is not paraphrased. Decorative headings and separator lines are excluded.
    """
    raw = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    if not raw.strip():
        return []

    blocks: list[str] = []
    for raw_block in re.split(r"\n\s*\n+", raw):
        lines: list[str] = []
        for raw_line in raw_block.splitlines():
            line = raw_line.strip()
            if not line or re.fullmatch(r"[=\-_–—*#]{3,}", line):
                continue
            # Markdown headings are location context, not evidence by themselves.
            if line.startswith("##") and len(line) < 100:
                continue
            if (
                len(line) < 80
                and not re.search(r"[.!?;:]", line)
                and not re.match(r"^(?:Q|A):", line, flags=re.I)
            ):
                # Company names, page headings, and one-line section labels are
                # location context rather than evidence text.
                continue
            lines.append(line)

        block = _clean_text(" ".join(lines))
        if not block:
            continue
        # Skip short title-only blocks such as company name or document title.
        if len(block) < 80 and not re.search(r"[.!?;:]", block):
            continue
        blocks.append(block)

    if not blocks:
        blocks = [_clean_text(raw)]

    segments: list[str] = []
    for block in blocks:
        # Keep Q:/A: pairs as separate units so a matching question can include
        # its adjacent answer rather than the entire FAQ chunk.
        pieces = re.split(
            r"(?<=[.!?])\s+(?=(?:Q:|A:|[A-Z0-9\"“]))|\s+(?=A:\s*)",
            block,
        )
        for piece in pieces:
            clean = _clean_text(piece)
            if len(clean) < 12:
                continue
            if clean not in segments:
                segments.append(clean)

    return segments



def _normalize_faq_question(value: str) -> str:
    """Normalize a FAQ question for tolerant Q/A-pair matching."""
    text = _clean_text(value).casefold()
    text = re.sub(r"^(?:q|question|pertanyaan)\s*:\s*", "", text)
    text = re.sub(r"[^a-z0-9à-ÿ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _matched_faq_answer(question: str, segments: list[str]) -> str:
    """Return only the A: segment paired with the closest matching Q: segment.

    This prevents the context selector from choosing a neighbouring FAQ answer
    merely because it shares generic words such as "first day", "password", or
    "account".
    """
    normalized_question = _normalize_faq_question(question)
    if not normalized_question:
        return ""

    question_tokens = set(_tokenize(question))
    best_score = 0.0
    best_answer = ""

    for index, segment in enumerate(segments):
        if not re.match(r"^\s*Q\s*:", segment, flags=re.I):
            continue

        next_index = index + 1
        if next_index >= len(segments):
            continue

        answer_segment = segments[next_index]
        if not re.match(r"^\s*A\s*:", answer_segment, flags=re.I):
            continue

        normalized_candidate = _normalize_faq_question(segment)
        similarity = SequenceMatcher(
            None,
            normalized_question,
            normalized_candidate,
        ).ratio()

        candidate_tokens = set(_tokenize(segment))
        token_coverage = (
            len(question_tokens.intersection(candidate_tokens))
            / max(len(question_tokens), 1)
        )

        # Requiring both a reasonably close phrase match and query-token support
        # reduces false pairings while remaining tolerant of light paraphrases.
        score = (0.60 * similarity) + (0.40 * token_coverage)

        if score > best_score:
            best_score = score
            best_answer = re.sub(
                r"^\s*A\s*:\s*",
                "",
                answer_segment,
                flags=re.I,
            ).strip()

    return best_answer if best_score >= 0.42 else ""


def build_evidence_excerpt(
    question: str,
    content: Any,
    max_chars: int = SOURCE_EXCERPT_MAX_CHARS,
) -> str:
    """Select a short verbatim passage that best supports the user question."""
    segments = _source_excerpt_segments(content)
    if not segments:
        return ""

    # FAQ documents must keep the matched Q:/A: pair locked together. Returning
    # only the paired answer also keeps the model prompt and evaluation context
    # free from neighbouring, unrelated FAQ entries.
    faq_answer = _matched_faq_answer(question, segments)
    if faq_answer:
        if len(faq_answer) <= max_chars:
            return faq_answer
        shortened = faq_answer[:max_chars].rsplit(" ", 1)[0].strip()
        return shortened + "…"

    query_tokens = set(_tokenize(question))
    question_lower = str(question or "").lower()
    asks_for_duration = bool(
        re.search(r"\b(berapa lama|maksimal|how long|duration|when|kapan)\b", question_lower)
    )

    def score_segment(index: int) -> tuple[float, int]:
        segment = segments[index]
        segment_tokens = set(_tokenize(segment))
        overlap = len(query_tokens.intersection(segment_tokens))
        coverage = overlap / max(len(query_tokens), 1)
        score = coverage * 4.0 + overlap * 0.35

        if segment.lstrip().lower().startswith("a:"):
            score += 0.45
        if asks_for_duration and (
            any(token in segment_tokens for token in _SOURCE_DURATION_WORDS)
            or re.search(r"\b\d+(?:[x×/]\d+)?\b", segment)
        ):
            score += 1.2
        if re.search(r"\b\d+(?:[.,]\d+)?\s*%?\b", segment):
            score += 0.15

        return score, -index

    best_index = max(range(len(segments)), key=score_segment)
    selected_indexes = [best_index]

    # A FAQ question and its answer are a single evidence unit for display.
    if segments[best_index].lstrip().lower().startswith("q:"):
        next_index = best_index + 1
        if next_index < len(segments) and segments[next_index].lstrip().lower().startswith("a:"):
            selected_indexes.append(next_index)
    elif segments[best_index].lstrip().lower().startswith("a:"):
        previous_index = best_index - 1
        if previous_index >= 0 and segments[previous_index].lstrip().lower().startswith("q:"):
            selected_indexes.insert(0, previous_index)

    # Include one adjacent factual sentence when it adds a requested number,
    # duration, or another direct query term. This keeps citations concise while
    # retaining details such as both "3 months" and "week 12".
    next_index = best_index + 1
    if next_index < len(segments) and next_index not in selected_indexes:
        next_segment = segments[next_index]
        next_tokens = set(_tokenize(next_segment))
        has_query_overlap = bool(query_tokens.intersection(next_tokens))
        has_requested_number = asks_for_duration and bool(
            any(token in next_tokens for token in _SOURCE_DURATION_WORDS)
            or re.search(r"\b\d+(?:[x×/]\d+)?\b", next_segment)
        )
        projected = " ".join(
            [*(segments[index] for index in selected_indexes), next_segment]
        )
        if (has_query_overlap or has_requested_number) and len(projected) <= max_chars:
            selected_indexes.append(next_index)

    selected_indexes = sorted(set(selected_indexes))
    excerpt = " ".join(segments[index] for index in selected_indexes)
    excerpt = _clean_text(excerpt)

    if len(excerpt) <= max_chars:
        return excerpt

    shortened = excerpt[:max_chars].rsplit(" ", 1)[0].strip()
    return shortened + "…"


def _detect_definition_target(question: str) -> str | None:
    q = question.strip()
    for pattern in DEFINITION_PATTERNS:
        match = re.search(pattern, q, flags=re.I)
        if match:
            target = match.group(1).strip("?.!,;:()[]{} ")
            return target if target else None
    return None


def _is_exact_token_present(text: str, token: str) -> bool:
    if not token:
        return False
    return re.search(rf"\b{re.escape(token)}\b", str(text or ""), flags=re.I) is not None


def _acronym_candidates(chunks: list[dict[str, Any]]) -> set[str]:
    candidates: set[str] = set()
    for chunk in chunks[:6]:
        content = str(chunk.get("content") or "")
        for token in re.findall(r"\b[A-Z][A-Z0-9]{2,}\b", content):
            if 3 <= len(token) <= 12:
                candidates.add(token)
    return candidates


def _similar_acronym(target: str, chunks: list[dict[str, Any]]) -> str | None:
    if not target or len(target) < 3:
        return None
    target_upper = target.upper()
    best: tuple[float, str] | None = None
    for candidate in _acronym_candidates(chunks):
        ratio = SequenceMatcher(None, target_upper, candidate.upper()).ratio()
        if ratio >= 0.74 and candidate.upper() != target_upper:
            if best is None or ratio > best[0]:
                best = (ratio, candidate)
    return best[1] if best else None


def _window_around_keyword(text: str, keyword: str, radius: int = 220) -> str:
    clean = _clean_text(text)
    match = re.search(re.escape(keyword), clean, flags=re.I)
    if not match:
        return ""
    start = max(match.start() - radius, 0)
    end = min(match.end() + radius, len(clean))
    window = clean[start:end]
    return window.strip(" ,;:-|")


def _extract_definition_from_text(text: str, target: str) -> str | None:
    clean = _clean_text(text)
    if not clean or not target:
        return None

    target_re = re.escape(target)

    # Contoh: "Jurnal Ilmiah Teknik Informatika dan Elektro (JITEK) | ISSN ..."
    before_parentheses = re.search(
        rf"([A-ZÀ-Ý][^.|:;]{{5,150}}\(\s*{target_re}\s*\))",
        clean,
        flags=re.I,
    )
    if before_parentheses:
        phrase = _clean_text(before_parentheses.group(1)).strip(" -–—|,:;")
        # Hilangkan prefix nomor halaman/penulis kalau ikut kebawa.
        phrase = re.sub(r"^.*?((?:Jurnal|Journal|Sistem|Aplikasi|Metode|Framework)\b)", r"\1", phrase, flags=re.I)
        if len(phrase) <= 180:
            return phrase

    # Contoh: "JITEK adalah ..." / "JITEK merupakan ..."
    after_definition = re.search(
        rf"\b{target_re}\b\s*(?:adalah|merupakan|yaitu|means|is)\s+([^.|;]{{5,180}})",
        clean,
        flags=re.I,
    )
    if after_definition:
        return f"{target.upper()} adalah {_clean_text(after_definition.group(1)).strip(' -–—|,:;')}"

    # Fallback: ambil segmen terpendek yang mengandung target.
    for separator in ["|", ".", ";", ":"]:
        segments = [_clean_text(segment) for segment in clean.split(separator)]
        containing = [segment for segment in segments if re.search(target_re, segment, flags=re.I)]
        containing = sorted(containing, key=len)
        for segment in containing:
            if 12 <= len(segment) <= 180:
                return segment.strip(" -–—|,:;")

    window = _window_around_keyword(clean, target, radius=120)
    if window:
        return window[:180].rsplit(" ", 1)[0].strip() + ("…" if len(window) > 180 else "")
    return None


def _definition_answer(question: str, chunks: list[dict[str, Any]], language: str) -> tuple[str, float] | None:
    target = _detect_definition_target(question)
    if not target:
        return None

    # Strict: kalau user nulis JITAK dan dokumen cuma punya JITEK, jangan jawab seolah-olah JITAK ada.
    exact_found = any(_is_exact_token_present(str(chunk.get("content") or ""), target) for chunk in chunks[:6])
    if not exact_found:
        suggestion = _similar_acronym(target, chunks)
        if suggestion:
            if language.upper() == "EN":
                return (
                    "Answer:\n"
                    f"I could not find the term {target.upper()} in the indexed documents. "
                    f"The closest term found is {suggestion}. Please ask again using the exact term if that is what you mean.\n\n"
                    "Source:\n- No exact source for the typed term.\n\nConfidence: 0%",
                    0.0,
                )
            return (
                "Jawaban:\n"
                f"Aku tidak menemukan istilah {target.upper()} di dokumen yang sudah di-index. "
                f"Istilah terdekat yang ditemukan adalah {suggestion}. Coba tanyakan ulang dengan istilah yang tepat kalau memang maksudnya {suggestion}.\n\n"
                "Sumber:\n- Tidak ada sumber exact untuk istilah yang diketik.\n\nConfidence: 0%",
                0.0,
            )
        return None

    best_definition: str | None = None
    best_chunk: dict[str, Any] | None = None

    for chunk in chunks[:6]:
        content = str(chunk.get("content") or "")
        if not _is_exact_token_present(content, target):
            continue
        definition = _extract_definition_from_text(content, target)
        if definition:
            best_definition = definition
            best_chunk = chunk
            break

    if not best_definition or not best_chunk:
        return None

    name = best_chunk.get("documentName") or "-"
    page = best_chunk.get("page") or "-"
    confidence = EXACT_DEFINITION_CONFIDENCE
    confidence_pct = round(confidence * 100)

    if re.search(rf"\(\s*{re.escape(target)}\s*\)", best_definition, flags=re.I):
        answer_line = f"{target.upper()} adalah singkatan/nama dari {best_definition}."
    elif best_definition.lower().startswith(target.lower()):
        answer_line = best_definition.rstrip(".") + "."
    else:
        answer_line = f"{target.upper()} merujuk pada {best_definition}."

    if language.upper() == "EN":
        return (
            "Answer:\n"
            f"{answer_line}\n\n"
            "Source:\n"
            f"- {name}, p. {page}\n\n"
            f"Confidence: {confidence_pct}%",
            confidence,
        )

    return (
        "Jawaban:\n"
        f"{answer_line}\n\n"
        "Sumber:\n"
        f"- {name}, p. {page}\n\n"
        f"Confidence: {confidence_pct}%",
        confidence,
    )



def _is_inventory_data_question(question: str) -> bool:
    tokens = set(_tokenize(question))
    text = question.lower()
    has_inventory_hint = bool(tokens.intersection(INVENTORY_QUESTION_HINTS))
    asks_list = any(
        phrase in text
        for phrase in [
            "data apa saja", "apa saja", "sebutkan data", "sebutkan",
            "data yang digunakan", "bahan", "subjek", "pencatatan barang",
        ]
    )
    return has_inventory_hint and asks_list


def _extract_inventory_fields_from_text(text: str) -> list[str]:
    clean = _clean_text(text)
    lower = clean.lower()
    fields: list[str] = []

    # Pattern utama dari dokumen inventori: "kode aset, nama barang, merk, tipe, ..."
    for key, label in INVENTORY_DATA_TERMS.items():
        if re.search(rf"\b{re.escape(key)}\b", lower, flags=re.I):
            if label not in fields:
                fields.append(label)

    # Tambahan: ambil daftar setelah frasa "seperti/meliputi/antara lain" kalau ada.
    list_match = re.search(
        r"(?:seperti|meliputi|antara lain|yaitu)\s+([^.;:]{20,220})",
        clean,
        flags=re.I,
    )
    if list_match:
        raw_items = re.split(r",|\bdan\b|/", list_match.group(1), flags=re.I)
        for item in raw_items:
            label = _clean_text(item).strip(" -–—:;,.()")
            if 3 <= len(label) <= 40:
                normalized = label.lower()
                # Jangan masukkan frasa umum yang bukan nama data.
                if normalized not in {"informasi terkait barang", "informasi", "data"}:
                    pretty = label[:1].upper() + label[1:]
                    if pretty not in fields:
                        fields.append(pretty)

    # Normalisasi duplikat yang maknanya sama.
    normalized_fields: list[str] = []
    seen_keys: set[str] = set()
    for field in fields:
        key = field.lower().replace("merek", "merk")
        key = key.replace("pemilik alat / owner", "owner")
        key = key.replace("lokasi barang", "lokasi")
        key = key.replace("jumlah barang", "jumlah")
        if key in seen_keys:
            continue
        seen_keys.add(key)
        normalized_fields.append(field)

    return normalized_fields


def _extract_inventory_fields(chunks: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for chunk in chunks[:5]:
        for field in _extract_inventory_fields_from_text(str(chunk.get("content") or "")):
            if field not in fields:
                fields.append(field)
    return fields


def _inventory_support_score(question: str, chunks: list[dict[str, Any]]) -> float:
    if not _is_inventory_data_question(question):
        return 0.0

    fields = _extract_inventory_fields(chunks)
    if len(fields) < 3:
        return 0.0

    joined = " ".join(str(chunk.get("content") or "") for chunk in chunks[:3]).lower()
    support_terms = ["barang", "gudang", "data", "pencatatan", "inventori", "inventory", "persediaan"]
    support_hits = sum(1 for term in support_terms if term in joined)

    if len(fields) >= 6 and support_hits >= 3:
        return 0.88
    if len(fields) >= 4 and support_hits >= 2:
        return 0.84
    if len(fields) >= 3 and support_hits >= 2:
        return 0.80
    return 0.0


def _inventory_data_answer(question: str, chunks: list[dict[str, Any]], language: str, confidence: float) -> str | None:
    if not _is_inventory_data_question(question):
        return None

    fields = _extract_inventory_fields(chunks)
    if len(fields) < 3:
        return None

    # Batasi item supaya jawaban tidak kepanjangan, tapi tetap informatif.
    fields = fields[:9]
    field_lines = "\n".join(f"- {field}" for field in fields)
    source_lines = "\n".join(_unique_sources(chunks, limit=2, confidence=confidence))
    confidence_pct = round(confidence * 100)

    # Catatan proses hanya dimunculkan kalau memang ada di chunk.
    joined = " ".join(str(chunk.get("content") or "") for chunk in chunks[:3]).lower()
    note = ""
    if "excel" in joined and ("manual" in joined or "microsoft excel" in joined):
        note = "\n\nCatatan:\n- Pada dokumen, proses pencatatan sebelumnya disebut masih dilakukan secara manual menggunakan Microsoft Excel."

    if language.upper() == "EN":
        return (
            "Answer:\n"
            "The data used as the subject/material for warehouse item recording includes:\n"
            f"{field_lines}{note}\n\n"
            "Source:\n"
            f"{source_lines}\n\n"
            f"Confidence: {confidence_pct}%"
        )

    return (
        "Jawaban:\n"
        "Data yang digunakan sebagai subjek/bahan dalam proses pencatatan barang di gudang meliputi:\n"
        f"{field_lines}{note}\n\n"
        "Sumber:\n"
        f"{source_lines}\n\n"
        f"Confidence: {confidence_pct}%"
    )

def _keyword_coverage(question: str, chunks: list[dict[str, Any]]) -> float:
    query_tokens = set(_tokenize(question))
    if not query_tokens:
        return 0.0
    text = " ".join(str(chunk.get("content") or "") for chunk in chunks[:3]).lower()
    content_tokens = set(_tokenize(text))
    return len(query_tokens.intersection(content_tokens)) / max(len(query_tokens), 1)


def _weighted_average(signals: list[tuple[float, float]]) -> float:
    usable = [
        (clamp_score(value), max(float(weight), 0.0))
        for value, weight in signals
        if weight > 0
    ]
    total_weight = sum(weight for _, weight in usable)
    if total_weight <= 0:
        return 0.0
    return sum(value * weight for value, weight in usable) / total_weight


def _chunk_confidence(chunk: dict[str, Any]) -> float:
    """Blend retrieval, reranker, and evidence signals for one candidate.

    The confidence is intentionally not copied from one similarity score. Hybrid
    retrieval is treated as the base signal, then cross-encoder reranking and
    evidence verification are combined when those signals are available.
    """
    if chunk.get("evidenceHardFailures"):
        return 0.0

    final_score = clamp_score(chunk.get("score"))
    base_score = clamp_score(
        chunk.get("baseScore", chunk.get("preEvidenceScore", final_score))
    )
    semantic_score = clamp_score(chunk.get("semanticScore"))
    keyword_score = clamp_score(chunk.get("keywordScore"))

    # The final retrieval score already includes hybrid retrieval and, when
    # enabled, reranking/evidence blending. Keep it as the dominant signal so
    # cross-language questions are not punished merely for low literal overlap.
    retrieval_score = _weighted_average(
        [
            (final_score, 0.45),
            (base_score, 0.25),
            (semantic_score, 0.20),
            (keyword_score, 0.10),
        ]
    )

    signals: list[tuple[float, float]] = [(retrieval_score, 0.60)]

    if "rerankerScore" in chunk:
        signals.append((clamp_score(chunk.get("rerankerScore")), 0.20))

    if "evidenceScore" in chunk or "evidenceSupported" in chunk:
        evidence_score = clamp_score(chunk.get("evidenceScore"))
        if chunk.get("evidenceSupported") is True:
            evidence_score = max(evidence_score, 0.45)
            signals.append((evidence_score, 0.20))
        elif not chunk.get("evidenceHardFailures"):
            # Weak evidence is neutral, not a penalty. This matters when an
            # Indonesian question is semantically correct but not covered by the
            # small deterministic enterprise vocabulary.
            signals.append((evidence_score, 0.08))

    confidence = _weighted_average(signals)

    # A calibrated final retrieval score is a safe floor when no contradiction
    # was found. Without this floor, averaging lexical signals could turn a
    # correct multilingual result into a false refusal.
    if not chunk.get("evidenceHardFailures"):
        confidence = max(confidence, final_score)

    # Strong deterministic evidence should not be cancelled by a weak lexical
    # signal on cross-language questions. The floor still depends on retrieval,
    # so an unrelated chunk cannot pass only because it contains a number.
    if chunk.get("evidenceSupported") is True:
        evidence_score = clamp_score(chunk.get("evidenceScore"))
        evidence_floor = (0.40 * retrieval_score) + (0.60 * evidence_score)
        confidence = max(confidence, evidence_floor)

    exact_coverage = clamp_score(chunk.get("exactTokenCoverage"))
    if exact_coverage >= 0.67:
        confidence += 0.02 + (0.02 * exact_coverage)

    return clamp_score(confidence)


def _calibrated_confidence(question: str, chunks: list[dict[str, Any]]) -> float:
    if not chunks:
        return 0.0

    definition = _definition_answer(question, chunks, "ID")
    if definition and definition[1] >= EXACT_DEFINITION_CONFIDENCE:
        return definition[1]

    inventory_support = _inventory_support_score(question, chunks)

    ranked_scores: list[tuple[float, float]] = []
    rank_weights = (1.0, 0.65, 0.40)

    for index, chunk in enumerate(chunks[:3]):
        score = _chunk_confidence(chunk)
        if score <= 0:
            continue
        ranked_scores.append((score, rank_weights[index]))

    if not ranked_scores:
        return 0.0

    # The best chunk is the primary answer gate. Secondary chunks may increase
    # confidence when they independently support it, but must never drag a good
    # top result below the threshold.
    confidence = ranked_scores[0][0]

    reliable_support = sum(
        1
        for score, _ in ranked_scores
        if score >= MIN_ANSWER_CONFIDENCE
    )
    if reliable_support >= 2:
        confidence += min(0.04, 0.02 * (reliable_support - 1))

    # Keyword coverage is only a small calibration factor because bilingual
    # questions may have low lexical overlap even when semantic evidence is good.
    coverage = _keyword_coverage(question, chunks)
    confidence += min(0.025, coverage * 0.025)

    if inventory_support >= MIN_ANSWER_CONFIDENCE:
        confidence = max(confidence, inventory_support)

    return clamp_score(confidence)


def _sentence_score(sentence: str, query_tokens: set[str], chunk: dict[str, Any], chunk_rank: int) -> float:
    sentence_tokens = set(_tokenize(sentence))
    overlap = len(query_tokens.intersection(sentence_tokens))
    keyword_coverage = overlap / max(len(query_tokens), 1)
    chunk_score = clamp_score(chunk.get("score", 0.0))
    semantic_score = clamp_score(chunk.get("semanticScore", 0.0))
    keyword_score = clamp_score(chunk.get("keywordScore", 0.0))
    rank_bonus = max(0.0, 0.08 - (chunk_rank * 0.02))
    return (keyword_coverage * 0.70) + (chunk_score * 0.15) + (semantic_score * 0.10) + (keyword_score * 0.05) + rank_bonus


def _source_document_type(chunk: dict[str, Any]) -> str:
    metadata = chunk.get("metadata") or {}
    explicit = _clean_text(
        chunk.get("documentType")
        or chunk.get("document_type")
        or metadata.get("document_type")
    ).lower()
    if explicit:
        return explicit.lstrip(".")

    name = _clean_text(
        chunk.get("documentName")
        or chunk.get("document_name")
        or metadata.get("filename")
    ).lower()
    if "." in name:
        return name.rsplit(".", 1)[-1]
    return ""


def _source_location_parts(chunk: dict[str, Any]) -> list[str]:
    metadata = chunk.get("metadata") or {}
    document_type = _source_document_type(chunk)
    page = _normalize_page(chunk.get("page", metadata.get("page")))
    page_is_reliable = bool(
        chunk.get("pageIsReliable")
        if chunk.get("pageIsReliable") is not None
        else chunk.get(
            "page_is_reliable",
            metadata.get("page_is_reliable", document_type == "pdf"),
        )
    )

    parts: list[str] = []
    if document_type == "pdf" and page is not None:
        parts.append(f"Page {page}")
    elif document_type == "docx" and page_is_reliable and page is not None:
        parts.append(f"Page {page}")
    elif document_type not in {"txt", "docx"} and page is not None:
        parts.append(f"Page {page}")

    chapter = _clean_text(
        chunk.get("chapter")
        or metadata.get("chapter")
        or chunk.get("section")
        or metadata.get("section")
    )
    if chapter:
        parts.append(f"Chapter: {chapter}")

    paragraph_start = chunk.get(
        "paragraphStart", metadata.get("paragraph_start")
    )
    paragraph_end = chunk.get(
        "paragraphEnd", metadata.get("paragraph_end")
    )

    # Backward compatibility for old TXT indexes. After reindexing, TXT uses
    # paragraph_start and paragraph_end directly.
    if document_type == "txt" and paragraph_start is None:
        paragraph_start = chunk.get("lineStart", metadata.get("line_start"))
        paragraph_end = chunk.get("lineEnd", metadata.get("line_end"))

    if paragraph_start is not None:
        start_number = int(paragraph_start)
        end_number = int(
            paragraph_end if paragraph_end is not None else paragraph_start
        )
        if end_number == start_number:
            parts.append(f"Paragraph {start_number}")
        else:
            parts.append(f"Paragraphs {start_number}–{end_number}")

    return parts


def _source_line(chunk: dict[str, Any], confidence: float | None = None) -> str:
    name = _clean_text(chunk.get("documentName") or "-") or "-"
    location = ", ".join(_source_location_parts(chunk))
    score_pct = round(
        (
            confidence
            if confidence is not None
            else clamp_score(chunk.get("score", 0.0))
        )
        * 100
    )
    citation = f"{name}, {location}" if location else name
    return f"- {citation} ({score_pct}%)"


def _unique_sources(
    chunks: list[dict[str, Any]],
    limit: int = 2,
    confidence: float | None = None,
) -> list[str]:
    seen: set[tuple[str, ...]] = set()
    sources: list[str] = []
    effective_limit = min(max(1, int(limit)), MAX_SOURCE_CITATIONS)

    ranked_chunks = sorted(
        chunks,
        key=lambda item: clamp_score(item.get("score", 0.0)),
        reverse=True,
    )

    for chunk in ranked_chunks:
        metadata = chunk.get("metadata") or {}
        key = (
            _clean_text(chunk.get("documentName") or metadata.get("filename")).casefold(),
            str(chunk.get("page", metadata.get("page")) or ""),
            _clean_text(
                chunk.get("chapter")
                or metadata.get("chapter")
                or chunk.get("section")
                or metadata.get("section")
            ).casefold(),
            str(chunk.get("paragraphStart", metadata.get("paragraph_start")) or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            _source_line(
                chunk,
                confidence=confidence if not sources else None,
            )
        )
        if len(sources) >= effective_limit:
            break

    return sources

def has_answerable_evidence(chunks: list[dict[str, Any]]) -> bool:
    """Return True when the post-retrieval answerability gate accepted the bundle.

    Answerability and display confidence are separate concerns. A correctly
    verified bundle must not be refused again merely because the calibrated
    confidence used for UI display falls below MIN_ANSWER_CONFIDENCE.
    """
    accepted = [
        chunk for chunk in chunks
        if chunk.get("answerabilityAccepted") is True
        and chunk.get("answerabilityEvidenceSelected", True)
        and not chunk.get("evidenceHardFailures")
    ]
    return bool(accepted)


def _answerability_confidence(chunks: list[dict[str, Any]]) -> float:
    values = [
        clamp_score(chunk.get("answerabilityScore"))
        for chunk in chunks
        if chunk.get("answerabilityAccepted") is True
    ]
    return max(values, default=0.0)


def _clean_extractive_text(value: str) -> str:
    text = _clean_text(value)
    # FAQ excerpts may include both Q: and A:. The final fallback must contain
    # only the answer because question text lowers relevance and token F1.
    answer_match = re.search(r"(?:^|\s)A:\s*(.+)$", text, flags=re.I)
    if answer_match:
        text = answer_match.group(1).strip()
    text = re.sub(r"^(?:Q|A):\s*", "", text, flags=re.I).strip()

    # Normalize punctuation artifacts produced by PDF/TXT line joining, for
    # example "Bring your ID, transcripts,.".
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r",\s*\.$", ".", text)
    text = re.sub(r"\s*,\s*,+", ", ", text)
    text = text.strip(" ,;:")

    if text and text[-1] not in ".!?":
        text += "."
    return text


def build_safe_extractive_answer(
    question: str,
    chunks: list[dict[str, Any]],
    language: str = "ID",
) -> str:
    """Build a concise answer from verbatim evidence excerpts.

    This is the final fallback after model repair. It does not invent a summary:
    it selects the minimum number of excerpts needed to cover explicit answer
    requirements. The function intentionally returns answer text only.
    """
    selected_chunks = [
        chunk for chunk in chunks
        if chunk.get("answerabilityEvidenceSelected", True)
        and not chunk.get("evidenceHardFailures")
    ] or [chunk for chunk in chunks if not chunk.get("evidenceHardFailures")]

    requirements = [
        requirement
        for requirement in extract_evidence_requirements(question)
        if requirement.key.startswith("answer_")
    ]
    uncovered = {requirement.key for requirement in requirements}
    candidates: list[tuple[int, float, str, set[str]]] = []

    for rank, chunk in enumerate(selected_chunks[:4]):
        raw = str(chunk.get("content") or "")
        excerpt = _clean_extractive_text(
            build_evidence_excerpt(question, raw, max_chars=max(SOURCE_EXCERPT_MAX_CHARS, 520))
        )
        if not excerpt:
            continue
        covered = {
            requirement.key
            for requirement in requirements
            if requirement_satisfied(requirement, [excerpt])
        }
        candidates.append((rank, clamp_score(chunk.get("score")), excerpt, covered))

    output: list[str] = []
    seen: set[str] = set()
    while candidates and len(output) < 3:
        best_index = max(
            range(len(candidates)),
            key=lambda index: (
                len(candidates[index][3] & uncovered),
                candidates[index][1],
                -candidates[index][0],
            ),
        )
        _, _, excerpt, covered = candidates.pop(best_index)
        normalized = re.sub(r"\W+", "", excerpt.casefold())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(excerpt)
        uncovered.difference_update(covered)
        if requirements and not uncovered:
            break
        if not requirements:
            break

    if not output:
        return build_refusal_answer(language)

    answer = " ".join(output)
    if len(answer) > MAX_TOTAL_ANSWER_CHARS:
        answer = answer[:MAX_TOTAL_ANSWER_CHARS].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
    return answer.strip()


def has_reliable_context(chunks: list[dict[str, Any]], question: str = "") -> bool:
    return (
        _calibrated_confidence(question, chunks) >= MIN_ANSWER_CONFIDENCE
        or has_answerable_evidence(chunks)
    )


def build_grounded_answer(question: str, chunks: list[dict[str, Any]], language: str = "ID") -> str:
    definition = _definition_answer(question, chunks, language)
    if definition:
        return definition[0]

    confidence = _calibrated_confidence(question, chunks)
    if confidence < MIN_ANSWER_CONFIDENCE and not has_answerable_evidence(chunks):
        if language.upper() == "EN":
            return (
                "Answer:\n"
                "Not found with enough confidence in the indexed documents. I will not answer from weak context to avoid hallucination.\n\n"
                "Source:\n- No reliable source found.\n\nConfidence: 0%"
            )
        return (
            "Jawaban:\n"
            "Belum ketemu dengan confidence yang cukup di dokumen yang sudah di-index. Sistem tidak menjawab dari konteks lemah agar tidak halusinasi.\n\n"
            "Sumber:\n- Tidak ada sumber yang cukup relevan.\n\nConfidence: 0%"
        )

    inventory_answer = _inventory_data_answer(question, chunks, language, confidence)
    if inventory_answer:
        return inventory_answer

    query_tokens = set(_tokenize(question))
    ranked_sentences: list[tuple[float, str]] = []

    for chunk_rank, chunk in enumerate(chunks[:4]):
        if clamp_score(chunk.get("score")) < 0.25 and chunk_rank > 0:
            continue
        for sentence in _split_sentences(str(chunk.get("content") or "")):
            lower = sentence.lower()
            if any(noise in lower for noise in NOISE_KEYWORDS):
                if len(set(_tokenize(sentence)).intersection(query_tokens)) < 2:
                    continue
            ranked_sentences.append((_sentence_score(sentence, query_tokens, chunk, chunk_rank), sentence))

    ranked_sentences.sort(key=lambda item: item[0], reverse=True)

    selected: list[str] = []
    seen_normalized: set[str] = set()
    for _, sentence in ranked_sentences:
        normalized = re.sub(r"\W+", "", sentence.lower())[:120]
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)
        selected.append(sentence)
        if len(selected) >= MAX_BULLETS:
            break

    if not selected:
        if language.upper() == "EN":
            return "Answer:\nNot found in the indexed documents.\n\nSource:\n- No reliable source found.\n\nConfidence: 0%"
        return "Jawaban:\nBelum ketemu di dokumen yang sudah di-index.\n\nSumber:\n- Tidak ada sumber yang cukup relevan.\n\nConfidence: 0%"

    answer_body = "\n".join(f"- {sentence}" for sentence in selected)
    if len(answer_body) > MAX_TOTAL_ANSWER_CHARS:
        answer_body = answer_body[:MAX_TOTAL_ANSWER_CHARS].rsplit(" ", 1)[0].strip() + "…"

    source_lines = "\n".join(_unique_sources(chunks, limit=2, confidence=confidence))
    confidence_pct = round(confidence * 100)

    if language.upper() == "EN":
        return (
            "Answer:\n"
            f"{answer_body}\n\n"
            "Source:\n"
            f"{source_lines}\n\n"
            f"Confidence: {confidence_pct}%"
        )

    return (
        "Jawaban:\n"
        f"{answer_body}\n\n"
        "Sumber:\n"
        f"{source_lines}\n\n"
        f"Confidence: {confidence_pct}%"
    )


def answer_confidence(question: str, chunks: list[dict[str, Any]]) -> float:
    return _calibrated_confidence(question, chunks) if chunks else 0.0


def should_return_sources(question: str, chunks: list[dict[str, Any]]) -> bool:
    return answer_confidence(question, chunks) >= MIN_ANSWER_CONFIDENCE


def _normalize_page(value: Any) -> int | str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text or text == "-":
        return None
    if text.isdigit():
        return int(text)
    return text


def build_sources(
    chunks: list[dict[str, Any]],
    question: str = "",
    limit: int = 2,
) -> list[dict[str, Any]]:
    """Return at most two citations ordered by descending relevance score.

    PDF citations keep the physical PDF page and paragraph range. DOCX page
    numbers are returned only when the parser obtained them from a rendered
    layout. TXT never claims a fixed page and uses chapter plus paragraph range.
    """
    confidence = answer_confidence(question, chunks)
    answerability_accepted = has_answerable_evidence(chunks)
    if confidence < MIN_ANSWER_CONFIDENCE and not answerability_accepted:
        return []

    unique_sources: dict[tuple[str, ...], dict[str, Any]] = {}

    source_chunks = [
        chunk for chunk in chunks
        if chunk.get("answerabilityEvidenceSelected", True)
        and chunk.get("contextSelected", True)
    ] or chunks

    for chunk in source_chunks:
        raw_score = clamp_score(chunk.get("score"))
        semantic_score = clamp_score(chunk.get("semanticScore"))
        evidence_supported = chunk.get("evidenceSupported") is True
        hard_failures = chunk.get("evidenceHardFailures") or []

        if hard_failures:
            continue
        if not (
            evidence_supported
            or raw_score >= MIN_SOURCE_CONFIDENCE
            or semantic_score >= 0.40
        ):
            continue

        metadata = chunk.get("metadata") or {}
        document_name = _clean_text(
            chunk.get("documentName")
            or chunk.get("document_name")
            or metadata.get("filename")
        )
        if not document_name or document_name == "-":
            continue

        document_type = _source_document_type(
            {**chunk, "documentName": document_name}
        )
        location_type = _clean_text(
            chunk.get("locationType")
            or chunk.get("location_type")
            or metadata.get("location_type")
        ).lower()

        raw_page = _normalize_page(chunk.get("page", metadata.get("page")))
        raw_page_reliability = (
            chunk.get("pageIsReliable")
            if chunk.get("pageIsReliable") is not None
            else chunk.get(
                "page_is_reliable",
                metadata.get("page_is_reliable"),
            )
        )
        page_is_reliable = bool(raw_page_reliability)
        if document_type == "pdf" and raw_page is not None:
            page_is_reliable = True

        if document_type == "pdf":
            page = raw_page
        elif document_type == "docx":
            page = raw_page if page_is_reliable else None
        elif document_type == "txt":
            page = None
            page_is_reliable = False
        elif location_type in {"lines", "paragraphs"}:
            page = None
        else:
            page = raw_page

        chapter = _clean_text(
            chunk.get("chapter")
            or metadata.get("chapter")
            or chunk.get("section")
            or metadata.get("section")
        ) or None

        paragraph_start = chunk.get(
            "paragraphStart", metadata.get("paragraph_start")
        )
        paragraph_end = chunk.get(
            "paragraphEnd", metadata.get("paragraph_end")
        )
        line_start = chunk.get("lineStart", metadata.get("line_start"))
        line_end = chunk.get("lineEnd", metadata.get("line_end"))

        # Old TXT indexes used line ranges. Present them as paragraph ranges only
        # as a safe compatibility fallback. A reindex supplies real paragraph
        # metadata and chapter names from the updated parser.
        if document_type == "txt" and paragraph_start is None:
            paragraph_start = line_start
            paragraph_end = line_end

        excerpt = build_evidence_excerpt(
            question,
            chunk.get("content") or metadata.get("content") or "",
        )

        source: dict[str, Any] = {
            "document_name": document_name,
            "document_type": document_type,
            "page": page,
            "page_is_reliable": page_is_reliable,
            "score": round(raw_score, 4),
            "relevance_score": round(raw_score, 4),
            "excerpt": excerpt,
        }

        if chapter:
            source["chapter"] = chapter
            source["section"] = chapter
        if paragraph_start is not None:
            source["paragraph_start"] = int(paragraph_start)
        if paragraph_end is not None:
            source["paragraph_end"] = int(paragraph_end)

        dedupe_key = (
            document_name.casefold(),
            document_type,
            str(page or ""),
            str(chapter or "").casefold(),
            str(paragraph_start or ""),
            str(paragraph_end or ""),
        )
        existing = unique_sources.get(dedupe_key)

        if (
            existing is None
            or source["relevance_score"] > existing["relevance_score"]
        ):
            unique_sources[dedupe_key] = source

    effective_limit = min(max(1, int(limit)), MAX_SOURCE_CITATIONS)
    return sorted(
        unique_sources.values(),
        key=lambda source: source["relevance_score"],
        reverse=True,
    )[:effective_limit]

def build_refusal_answer(language: str = "ID") -> str:
    if str(language or "ID").upper() == "EN":
        return (
            "The requested information was not found with sufficient evidence "
            "in the indexed documents."
        )
    return (
        "Informasi tersebut tidak ditemukan dengan bukti yang cukup pada "
        "dokumen yang telah diindeks."
    )


def answer_text_only(value: Any) -> str:
    """Remove answer labels and embedded source/confidence metadata."""
    text = str(value or "")
    text = re.sub(r"<think>.*?</think>", " ", text, flags=re.I | re.S)
    text = re.sub(r"</?think>", " ", text, flags=re.I)
    text = re.sub(r"^\s*(?:Jawaban|Answer)\s*:\s*", "", text, flags=re.I)
    text = re.split(
        r"(?:\r?\n){1,}\s*(?:Sumber|Source|Confidence|Kepercayaan|Model)\s*:",
        text,
        maxsplit=1,
        flags=re.I,
    )[0]
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return text.strip()


def is_refusal_answer(value: Any) -> bool:
    text = answer_text_only(value).casefold().strip()
    refusal_prefixes = (
        "informasi tersebut tidak ditemukan",
        "informasi tidak ditemukan",
        "tidak ditemukan dengan bukti",
        "belum ditemukan di dokumen",
        "belum ketemu di dokumen",
        "tidak ada informasi yang cukup",
        "konteks tidak cukup",
        "the requested information was not found",
        "the information was not found",
        "i could not find",
        "could not find the requested information",
        "no sufficient information was found",
        "insufficient context",
        "insufficient evidence",
    )
    return text.startswith(refusal_prefixes)


def top_confidence(chunks: list[dict[str, Any]], question: str = "") -> float:
    confidence = answer_confidence(question, chunks)
    if confidence >= MIN_ANSWER_CONFIDENCE:
        return round(confidence, 4)
    if has_answerable_evidence(chunks):
        # Keep the real calibrated value when possible. Answerability score is a
        # fallback display confidence, not a second refusal threshold.
        return round(max(confidence, _answerability_confidence(chunks), 0.01), 4)
    return 0.0
