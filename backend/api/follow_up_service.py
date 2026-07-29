from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = PROJECT_ROOT / "evaluation" / "ground_truth.json"
DEFAULT_CORPUS_PATH = PROJECT_ROOT / "backend" / "uploads" / "files"

ENABLE_DATASET_FOLLOW_UP = os.getenv("ENABLE_DATASET_FOLLOW_UP", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
FOLLOW_UP_DATASET_PATH = Path(
    os.getenv("FOLLOW_UP_DATASET_PATH", str(DEFAULT_DATASET_PATH))
)
FOLLOW_UP_CORPUS_PATH = Path(
    os.getenv("FOLLOW_UP_CORPUS_PATH", str(DEFAULT_CORPUS_PATH))
)
FOLLOW_UP_MIN_SCORE = float(os.getenv("FOLLOW_UP_MIN_SCORE", "25.0"))
FOLLOW_UP_REQUIRE_TOPIC_MATCH = os.getenv(
    "FOLLOW_UP_REQUIRE_TOPIC_MATCH", "true"
).strip().lower() in {"1", "true", "yes", "on"}
FOLLOW_UP_VERIFY_RETRIEVAL = os.getenv(
    "FOLLOW_UP_VERIFY_RETRIEVAL", "true"
).strip().lower() in {"1", "true", "yes", "on"}
FOLLOW_UP_VERIFY_MAX_CANDIDATES = max(
    1,
    int(os.getenv("FOLLOW_UP_VERIFY_MAX_CANDIDATES", "3")),
)
FOLLOW_UP_VERIFICATION_TOP_K = max(
    1,
    int(os.getenv("FOLLOW_UP_VERIFICATION_TOP_K", "5")),
)

# Words that do not describe the subject of a follow-up question.
_STOPWORDS = {
    "a",
    "adalah",
    "akan",
    "an",
    "and",
    "anda",
    "apa",
    "apakah",
    "atau",
    "bagaimana",
    "berapa",
    "berdasarkan",
    "dalam",
    "dan",
    "dari",
    "dengan",
    "di",
    "dilakukan",
    "diproses",
    "does",
    "for",
    "from",
    "harus",
    "how",
    "if",
    "in",
    "is",
    "it",
    "itu",
    "jika",
    "ke",
    "kapan",
    "kepada",
    "mana",
    "melalui",
    "mereka",
    "of",
    "on",
    "pada",
    "perusahaan",
    "saya",
    "seorang",
    "sudah",
    "the",
    "tidak",
    "to",
    "untuk",
    "what",
    "when",
    "where",
    "which",
    "with",
    "yang",
}

_CANONICAL_TOKEN = {
    "credential": "password",
    "credentials": "password",
    "kredensial": "password",
    "sandi": "password",
    "passwords": "password",
    "reset": "password",
    "reimburse": "expense",
    "reimbursement": "expense",
    "penggantian": "expense",
    "biaya": "expense",
    "leave": "cuti",
    "liburan": "cuti",
    "vacation": "cuti",
    "employee": "karyawan",
    "employees": "karyawan",
    "staff": "karyawan",
    "worker": "karyawan",
    "revenue": "pendapatan",
    "income": "pendapatan",
    "profit": "laba",
    "margin": "laba",
    "security": "keamanan",
    "secure": "keamanan",
    "email": "mail",
    "mailbox": "mail",
    "electronic": "mail",
    "onboarding": "orientasi",
    "orientation": "orientasi",
    "offboarding": "resign",
    "departure": "resign",
    "resignation": "resign",
    "travel": "perjalanan",
    "trip": "perjalanan",
    "vendor": "pemasok",
    "supplier": "pemasok",
    "monitoring": "pemantauan",
    "incident": "insiden",
    "outage": "insiden",
    "downtime": "insiden",
}

# These words may be useful for retrieval, but are too generic to prove that
# two questions discuss the same subject.
_GENERIC_TOKENS = {
    "company",
    "dokumen",
    "internal",
    "jam",
    "hari",
    "bulan",
    "tahun",
    "duration",
    "lama",
    "karyawan",
    "maksimal",
    "maximum",
    "portal",
    "proses",
    "prosesnya",
    "procedure",
    "prosedur",
    "sistem",
    "time",
    "waktu",
    "faq",
    "policy",
    "report",
    "sop",
    "tech",
    "technical",
    "txt",
    "pdf",
    "docx",
}


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tokens(value: Any) -> set[str]:
    raw_tokens = re.findall(r"[a-z0-9]+", _clean_text(value).casefold())
    result: set[str] = set()
    for token in raw_tokens:
        if len(token) < 3 or token in _STOPWORDS:
            continue
        result.add(_CANONICAL_TOKEN.get(token, token))
    return result


def _topic_tokens(value: Any) -> set[str]:
    return _tokens(value) - _GENERIC_TOKENS


def _normalize_question(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _clean_text(value).casefold()))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _document_name(source: dict[str, Any]) -> str:
    return _clean_text(
        source.get("document_name")
        or source.get("documentName")
        or source.get("filename")
    )


def _document_category(document_name: str) -> str:
    prefix = document_name.split("_", 1)[0].casefold()
    aliases = {
        "faq": "faq",
        "policy": "policy",
        "pol": "policy",
        "report": "report",
        "sop": "sop",
        "tech": "technical",
        "technical": "technical",
    }
    return aliases.get(prefix, prefix)


def _document_topic_tokens(document_names: list[str]) -> set[str]:
    topics: set[str] = set()
    for document_name in document_names:
        stem = Path(document_name).stem
        parts = stem.split("_")
        if parts and _document_category(document_name) in {
            "faq",
            "policy",
            "report",
            "sop",
            "technical",
        }:
            parts = parts[1:]
        topics.update(_topic_tokens(" ".join(parts)))
    return topics


def _reference_documents(item: dict[str, Any]) -> list[str]:
    documents: list[str] = []
    for reference in item.get("references") or []:
        if not isinstance(reference, dict):
            continue
        document = _clean_text(reference.get("document"))
        if document:
            documents.append(document)
    return documents


def _references_exist(documents: list[str]) -> bool:
    if not documents:
        return False
    if not FOLLOW_UP_CORPUS_PATH.exists():
        # The dataset remains the source of truth in packaged/test environments
        # where the corpus directory may intentionally be omitted.
        return True
    return all((FOLLOW_UP_CORPUS_PATH / document).is_file() for document in documents)


def _localized_question(item: dict[str, Any], language: str) -> str:
    target = (language or "ID").upper()
    item_language = _clean_text(item.get("language")).lower()
    question = _clean_text(item.get("question"))
    variants = [
        _clean_text(value)
        for value in item.get("query_variants") or []
        if _clean_text(value)
    ]

    if target == "EN":
        if item_language == "en" and question:
            return question
        if len(variants) >= 2:
            return variants[1]
        return question or (variants[0] if variants else "")

    if item_language == "id" and question:
        return question
    if len(variants) >= 2:
        return variants[1]
    return question or (variants[0] if variants else "")


@lru_cache(maxsize=1)
def _load_items() -> tuple[dict[str, Any], ...]:
    if not ENABLE_DATASET_FOLLOW_UP or not FOLLOW_UP_DATASET_PATH.exists():
        return ()

    try:
        with FOLLOW_UP_DATASET_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return ()

    raw_items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        return ()

    valid_items: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict) or item.get("answerable") is not True:
            continue

        expected_answer = _clean_text(item.get("expected_answer"))
        references = _reference_documents(item)
        if not expected_answer or not references or not _references_exist(references):
            continue
        valid_items.append(item)

    return tuple(valid_items)


def _is_duplicate_candidate(
    item: dict[str, Any],
    *,
    current_question: str,
    answer: str,
    candidate_question: str,
    same_document: bool,
) -> bool:
    if _normalize_question(candidate_question) == _normalize_question(current_question):
        return True

    if not same_document:
        return False

    current_question_tokens = _topic_tokens(current_question)
    candidate_question_tokens = _topic_tokens(candidate_question)
    current_answer_tokens = _topic_tokens(answer)
    expected_answer_tokens = _topic_tokens(item.get("expected_answer"))

    # Same document plus substantially equivalent question/answer usually means
    # this is merely another benchmark wording for the answer just shown.
    return (
        _jaccard(current_question_tokens, candidate_question_tokens) >= 0.50
        and _jaccard(current_answer_tokens, expected_answer_tokens) >= 0.45
    )


def _candidate_score(
    item: dict[str, Any],
    *,
    current_question: str,
    answer: str,
    source_documents: list[str],
    language: str,
) -> float:
    candidate_question = _localized_question(item, language)
    if not candidate_question:
        return float("-inf")

    candidate_documents = _reference_documents(item)
    source_names = {name.casefold() for name in source_documents}
    candidate_names = {name.casefold() for name in candidate_documents}
    same_document = bool(source_names & candidate_names)

    if _is_duplicate_candidate(
        item,
        current_question=current_question,
        answer=answer,
        candidate_question=candidate_question,
        same_document=same_document,
    ):
        return float("-inf")

    current_content_topics = _topic_tokens(f"{current_question} {answer}")
    candidate_content_topics = _topic_tokens(
        " ".join(
            [
                candidate_question,
                _clean_text(item.get("expected_answer")),
                " ".join(
                    _clean_text(value)
                    for value in item.get("expected_answer_keywords") or []
                ),
            ]
        )
    )
    shared_content_topics = current_content_topics & candidate_content_topics

    source_document_topics = _document_topic_tokens(source_documents)
    candidate_document_topics = _document_topic_tokens(candidate_documents)
    shared_document_topics = source_document_topics & candidate_document_topics
    shared_anchor_topics = shared_content_topics & (
        source_document_topics | candidate_document_topics
    )
    # A common subject must be anchored by a document topic (for example,
    # "password" in Policy_Password.docx). Sharing a source document is not
    # sufficient because multi-hop benchmark rows can cite the same document
    # for a secondary fact while answering a different user intent. When no
    # anchored subject exists, no follow-up is safer than an unrelated one.
    if FOLLOW_UP_REQUIRE_TOPIC_MATCH and not shared_anchor_topics:
        return float("-inf")

    source_categories = {_document_category(name) for name in source_documents}
    candidate_categories = {_document_category(name) for name in candidate_documents}
    same_category = bool(source_categories & candidate_categories)

    score = 0.0
    if same_document:
        score += 20.0
    score += 30.0 * len(shared_anchor_topics)
    score += 8.0 * len(shared_content_topics)
    score += 5.0 * len(shared_document_topics)
    if same_category:
        score += 1.0

    # Prefer concise, user-facing questions over long retrieval variants.
    score -= max(0, len(candidate_question.split()) - 30) * 0.05
    return score


@lru_cache(maxsize=256)
def _question_is_retrievable(
    candidate_question: str,
    expected_documents: tuple[str, ...],
) -> bool:
    """Verify that the production retrieval pipeline can answer the suggestion.

    Ground-truth metadata alone is not enough: a benchmark row can be marked
    answerable while a stricter runtime gate rejects its exact wording. The
    follow-up is shown only when ``hybrid_search`` returns evidence from one of
    the row's referenced documents.
    """
    if not FOLLOW_UP_VERIFY_RETRIEVAL:
        return True

    try:
        # Lazy import avoids coupling module initialization to the vector store.
        from retrieval.hybrid_search import hybrid_search

        rows = hybrid_search(
            candidate_question,
            top_k=FOLLOW_UP_VERIFICATION_TOP_K,
        )
    except Exception as exc:
        print(f"[FOLLOW_UP] Retrieval verification failed: {exc}")
        return False

    if not rows:
        return False

    expected = {Path(name).name.casefold() for name in expected_documents if name}
    if not expected:
        return False

    retrieved = {
        Path(
            _clean_text(
                row.get("documentName")
                or row.get("document_name")
                or (row.get("metadata") or {}).get("filename")
            )
        ).name.casefold()
        for row in rows
        if isinstance(row, dict)
    }
    return bool(expected & retrieved)


def build_dataset_follow_up_question(
    question: str,
    answer: str,
    sources: list[dict[str, Any]],
    language: str = "ID",
) -> str | None:
    """Return one closely related, answerable follow-up from ground truth.

    The follow-up is never invented by the LLM. A candidate must:
    - be marked answerable in the ground-truth dataset;
    - contain an expected answer and reference existing corpus documents;
    - not duplicate the question/answer just shown; and
    - come from the same document or share a specific topic token.

    If no candidate passes these checks, ``None`` is returned and the UI shows
    a neutral closing sentence instead of an unrelated recommendation.
    """
    if not ENABLE_DATASET_FOLLOW_UP or not sources:
        return None

    source_documents = [
        name for source in sources if (name := _document_name(source))
    ]
    if not source_documents:
        return None

    scored: list[tuple[float, str, str, tuple[str, ...]]] = []
    for item in _load_items():
        candidate_question = _localized_question(item, language)
        score = _candidate_score(
            item,
            current_question=question,
            answer=answer,
            source_documents=source_documents,
            language=language,
        )
        if score == float("-inf"):
            continue
        scored.append(
            (
                score,
                _clean_text(item.get("id")),
                candidate_question,
                tuple(_reference_documents(item)),
            )
        )

    if not scored:
        return None

    # Deterministic ordering keeps demos and saved conversations reproducible.
    scored.sort(key=lambda value: (-value[0], value[1], value[2]))

    checked = 0
    for score, _, candidate_question, expected_documents in scored:
        if score < FOLLOW_UP_MIN_SCORE:
            break
        if checked >= FOLLOW_UP_VERIFY_MAX_CANDIDATES:
            break
        checked += 1

        if _question_is_retrievable(candidate_question, expected_documents):
            return candidate_question

    # Do not recommend a benchmark question that the actual runtime pipeline
    # would refuse. The UI will show its neutral closing sentence instead.
    return None
