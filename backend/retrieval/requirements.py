"""Generic evidence requirements for answerability and grounding validation.

This module extracts answer-type requirements from arbitrary Indonesian or
English questions. It intentionally avoids rules tied to individual benchmark
questions, so the runtime remains useful outside the evaluation set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from retrieval.query_expansion import (
    CONCEPT_ALIASES,
    concepts_in_text,
    contains_alias,
    normalize_text,
)


@dataclass(frozen=True)
class EvidenceRequirement:
    key: str
    description: str
    kind: str
    value: str = ""
    unit: str = ""
    same_chunk_terms: tuple[str, ...] = ()
    subject_concepts: tuple[str, ...] = ()


URL_PATTERN = re.compile(
    r"(?:https?://|www\.)[^\s)\]}>\"']+|\b/[A-Za-z0-9_.~!$&'()*+,;=:@%/-]{3,}",
    flags=re.I,
)
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", flags=re.I)
VERSION_PATTERN = re.compile(
    r"\b(?:v(?:ersion)?\s*)?\d+(?:\.\d+){1,3}\b|"
    r"\b(?:macos|windows|android|ios|postgresql|python|node(?:\.js)?|crm)\s*"
    r"(?:version|versi)?\s*[v.]?\s*\d+(?:\.\d+)*\b",
    flags=re.I,
)
CADENCE_PATTERN = re.compile(
    r"\b(?:daily|nightly|weekly|monthly|quarterly|annually|yearly|biweekly|"
    r"hourly|once\s+(?:a|per)\s+(?:day|week|month|quarter|year)|"
    r"twice\s+(?:a|per)\s+(?:day|week|month|quarter|year)|"
    r"every\s+\d+(?:[.,]\d+)?\s+(?:minutes?|hours?|days?|weeks?|months?|years?)|"
    r"harian|setiap\s+malam|mingguan|bulanan|triwulan|kuartalan|tahunan|"
    r"setiap\s+(?:jam|hari|malam|minggu|bulan|triwulan|kuartal|tahun)|"
    r"\d+\s+kali\s+(?:per|setiap)\s+(?:hari|minggu|bulan|tahun))\b",
    flags=re.I,
)
MONEY_PATTERN = re.compile(
    r"(?:\b(?:IDR|Rp\.?|USD|EUR)\s*\d[\d.,]*"
    r"(?:\s*(?:ribu|thousand|juta|million|miliar|billion|triliun|trillion))?"
    r"|\b\d[\d.,]*\s*(?:rupiah|IDR|USD|EUR)\b)",
    flags=re.I,
)
PERCENT_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%(?=$|[^0-9])|percent\b|percentage\b|persen\b)", flags=re.I)
STORAGE_PATTERN = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:KB|MB|GB|TB|kilobytes?|megabytes?|gigabytes?|terabytes?)\b",
    flags=re.I,
)
TIME_PATTERN = re.compile(
    r"\b(?:within\s+|at\s+least\s+|up\s+to\s+|maksimal\s+|minimal\s+|"
    r"paling\s+lambat\s+|dalam\s+waktu\s+)?"
    r"(?:\d+\s*[x×]\s*\d+|\d+(?:[.,]\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"satu|dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh)\s*"
    r"(?:minutes?|mins?|hours?|hrs?|working\s+days?|business\s+days?|days?|weeks?|months?|years?|"
    r"menit|jam|hari\s+kerja|hari|minggu|bulan|tahun)\b",
    flags=re.I,
)
RELATIVE_DATE_TIME_PATTERN = re.compile(
    r"\b(?:"
    r"(?:the\s+)?(?:next|following|previous|prior)\s+(?:working\s+day|business\s+day|"
    r"day|week|month|year|payroll(?:\s+cycle)?)|"
    r"(?:next|following)\s+month(?:'s)?\s+payroll|"
    r"(?:next|following)\s+monthly\s+payroll(?:\s+cycle)?|"
    r"payroll\s+(?:cycle\s+)?(?:of\s+)?(?:the\s+)?(?:next|following)\s+month|"
    r"(?:hari\s+kerja|hari|minggu|bulan|tahun|payroll)\s+(?:sebelumnya|berikutnya)|"
    r"siklus\s+payroll\s+(?:bulan\s+)?berikutnya|"
    r"payroll\s+bulan\s+berikutnya"
    r")\b",
    flags=re.I,
)
NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\b")
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
QUOTED_PATTERN = re.compile(r"['\"“”‘’*]([^'\"“”‘’*]{8,160})['\"“”‘’*]")
NUMBER_WITH_UNIT_PATTERN = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(GB|MB|TB|KB|(?:consecutive\s+)?days?|years?|months?|weeks?|hours?|"
    r"minutes?|seconds?|characters?|chars?|requests?|calls?|hari|tahun|bulan|minggu|jam|"
    r"hari\s+berturut-turut|menit|detik|karakter|permintaan|panggilan|%|persen|percent)(?=$|[^A-Za-z0-9])",
    flags=re.I,
)


DEFINITION_QUESTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^\s*(?:apa\s+itu|apa\s+yang\s+dimaksud\s+dengan)\s+(.+?)\s*[?.!]*$",
        flags=re.I,
    ),
    re.compile(
        r"^\s*what\s+does\s+(.+?)\s+(?:mean|stand\s+for)\s*[?.!]*$",
        flags=re.I,
    ),
    re.compile(
        r"^\s*(?:kepanjangan|arti)\s+(?:dari\s+)?(.+?)(?:\s+apa)?\s*[?.!]*$",
        flags=re.I,
    ),
    re.compile(
        r"^\s*(.+?)\s+(?:singkatan|kepanjangan)\s+dari\s+apa\s*[?.!]*$",
        flags=re.I,
    ),
    # ``what is`` is ambiguous for value questions. Restrict this form to one
    # compact term so "what is my mailbox size limit" is not misclassified.
    re.compile(
        r"^\s*what\s+is\s+([A-Za-z0-9][A-Za-z0-9_.\-/]{1,31})\s*[?.!]*$",
        flags=re.I,
    ),
)


def extract_definition_target(question: str) -> str | None:
    """Return the exact term requested by a clear definition question."""

    raw = str(question or "").strip()
    if not raw:
        return None

    for pattern in DEFINITION_QUESTION_PATTERNS:
        match = pattern.search(raw)
        if not match:
            continue
        target = match.group(1).strip(" \t\r\n?.!,;:()[]{}\"'“”‘’")
        target = re.sub(r"\s+", " ", target)
        if not target or len(target) > 80:
            return None
        return target
    return None


def _definition_value_is_substantive(value: str, target: str) -> bool:
    normalized_value = normalize_text(value)
    normalized_target = normalize_text(target)
    if not normalized_value or normalized_value == normalized_target:
        return False
    tokens = [
        token
        for token in re.findall(r"[a-z0-9à-ÿ]+", normalized_value)
        if len(token) >= 2
    ]
    return len(tokens) >= 2


def _acronym_matches_expansion(target: str, expansion: str) -> bool:
    """Reject parenthetical labels that merely group a topic under an acronym."""

    acronym = re.sub(r"[^A-Za-z0-9]", "", str(target or "")).upper()
    words = re.findall(r"[A-Za-zÀ-ÿ0-9]+", str(expansion or ""))
    if len(acronym) < 2 or len(words) < 2:
        return False

    stopwords = {"and", "of", "the", "for", "dan", "dari", "yang", "untuk"}
    significant = [word for word in words if normalize_text(word) not in stopwords]
    if len(significant) < 2:
        significant = words

    initials = "".join(word[0] for word in significant if word).upper()
    all_initials = "".join(word[0] for word in words if word).upper()
    return acronym in {initials, all_initials}


def has_explicit_definition(text: str, target: str, *, acronym_mode: bool = False) -> bool:
    """Return True only when one evidence unit explicitly defines ``target``.

    A title such as ``Nusantara Dynamics SOP - Travel Booking`` and a sentence
    such as ``This SOP defines onboarding`` are topical mentions, not definitions.
    """

    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    clean_target = str(target or "").strip()
    if not raw or not clean_target:
        return False

    target_re = re.escape(clean_target)
    value_patterns: list[re.Pattern[str]] = [
        re.compile(
            rf"\b{target_re}\b\s*,?\s*(?:stands\s+for|means|is\s+short\s+for|"
            rf"is\s+an?\s+acronym\s+for|singkatan\s+dari|kepanjangan\s+dari|"
            rf"(?:adalah|merupakan)\s+(?:singkatan|kepanjangan)\s+dari|"
            rf"berarti|didefinisikan\s+sebagai)\s+([^.;|]{{3,220}})",
            flags=re.I,
        ),
        re.compile(
            rf"\b{target_re}\b\s*\(\s*([^)]{{3,180}})\s*\)",
            flags=re.I,
        ),
    ]

    # ``X is Y`` is valid for ordinary terms, but too loose for acronym mode.
    # For example, "RTO is 4 hours" states a value, not what RTO stands for.
    if not acronym_mode:
        value_patterns.append(
            re.compile(
                rf"\b{target_re}\b\s*(?:adalah|merupakan|yaitu|merujuk\s+pada|"
                rf"is|refers\s+to|is\s+defined\s+as)\s+([^.;|]{{3,220}})",
                flags=re.I,
            )
        )

    for pattern in value_patterns:
        match = pattern.search(raw)
        if not match:
            continue
        value = match.group(1).strip(" ,.;:|-_")
        if not _definition_value_is_substantive(value, clean_target):
            continue
        if acronym_mode and "(" in match.group(0) and not _acronym_matches_expansion(clean_target, value):
            continue
        return True

    # Expansion before acronym: ``Standard Operating Procedure (SOP)``.
    before_parentheses = re.search(
        rf"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9/&,.\- ]{{3,180}}?)\s*"
        rf"\(\s*{target_re}\s*\)",
        raw,
        flags=re.I,
    )
    if before_parentheses:
        value = before_parentheses.group(1).strip(" ,.;:|-_")
        if (
            _definition_value_is_substantive(value, clean_target)
            and (not acronym_mode or _acronym_matches_expansion(clean_target, value))
        ):
            return True

    abbreviated_as = re.search(
        rf"([A-Za-zÀ-ÿ][^.;|]{{3,180}}?)\s*,?\s*"
        rf"(?:abbreviated\s+as|disingkat\s+(?:sebagai|menjadi)?)\s+"
        rf"\b{target_re}\b",
        raw,
        flags=re.I,
    )
    if abbreviated_as:
        value = abbreviated_as.group(1).strip(" ,.;:|-_")
        if _definition_value_is_substantive(value, clean_target):
            return True

    return False


def _contains_phrase(text: str, phrases: Iterable[str]) -> bool:
    padded = f" {normalize_text(text)} "
    return any(
        normalized and f" {normalized} " in padded
        for normalized in (normalize_text(phrase) for phrase in phrases)
    )


def is_scenario_comparison(question: str) -> bool:
    query = normalize_text(question)
    has_scenario_marker = _contains_phrase(
        query,
        ("if", "jika", "apabila", "seandainya", "suppose", "assuming", "ketika"),
    )
    has_decision_intent = _contains_phrase(
        query,
        (
            "comply", "compliant", "mematuhi", "memenuhi", "allowed", "permissible",
            "diperbolehkan", "diizinkan", "boleh", "rejected", "ditolak", "violate",
            "melanggar", "will", "would", "does", "apakah",
        ),
    )
    return has_scenario_marker and has_decision_intent


def canonical_unit(unit: str) -> str:
    value = normalize_text(unit)
    aliases = {
        "day": "days", "hari": "days", "working day": "days", "business day": "days",
        "consecutive day": "days", "consecutive days": "days",
        "hari berturut turut": "days", "hari berturut-turut": "days",
        "year": "years", "tahun": "years", "month": "months", "bulan": "months",
        "week": "weeks", "minggu": "weeks", "hour": "hours", "hr": "hours", "jam": "hours",
        "minute": "minutes", "min": "minutes", "menit": "minutes",
        "second": "seconds", "sec": "seconds", "detik": "seconds",
        "character": "characters", "char": "characters", "karakter": "characters",
        "request": "requests", "call": "requests", "permintaan": "requests", "panggilan": "requests",
        "persen": "%", "percent": "%", "percentage": "%",
    }
    return aliases.get(value, value)


def numeric_constraints(text: str) -> list[tuple[str, str]]:
    constraints: list[tuple[str, str]] = []
    for number, unit in NUMBER_WITH_UNIT_PATTERN.findall(str(text or "")):
        item = (number.replace(",", "."), canonical_unit(unit))
        if item not in constraints:
            constraints.append(item)
    return constraints


def unit_family(unit: str) -> str:
    value = canonical_unit(unit)
    if value in {"gb", "mb", "tb", "kb"}:
        return "storage"
    if value in {"seconds", "minutes", "hours", "days", "weeks", "months", "years"}:
        return "duration"
    if value == "characters":
        return "length"
    if value == "requests":
        return "request_count"
    if value == "%":
        return "percentage"
    return value


def _subject_terms_for_exact_detail(question: str) -> tuple[str, ...]:
    query = normalize_text(question)
    stop = {
        "apa", "apakah", "berapa", "bagaimana", "yang", "untuk", "dengan", "dalam",
        "what", "which", "how", "the", "for", "with", "exact", "persis", "langsung",
        "url", "endpoint", "link", "version", "versi", "nomor", "nilai", "maksimum",
    }
    tokens = [
        token for token in re.findall(r"[a-z0-9]+", query)
        if len(token) >= 4 and token not in stop
    ]
    return tuple(dict.fromkeys(tokens[:6]))


def extract_evidence_requirements(question: str) -> list[EvidenceRequirement]:
    query = normalize_text(question)
    requirements: list[EvidenceRequirement] = []

    def add(requirement: EvidenceRequirement) -> None:
        if requirement.key not in {item.key for item in requirements}:
            requirements.append(requirement)

    definition_target = extract_definition_target(question)
    if definition_target:
        explicit_acronym_intent = _contains_phrase(
            query,
            (
                "stand for",
                "singkatan dari",
                "kepanjangan dari",
                "kepanjangan",
            ),
        )
        letters = re.sub(r"[^A-Za-z]", "", definition_target)
        acronym_mode = bool(
            explicit_acronym_intent
            or (
                letters
                and 2 <= len(letters) <= 12
                and letters.upper() == letters
            )
        )
        add(EvidenceRequirement(
            "answer_definition",
            f"an explicit definition of {definition_target}",
            "definition",
            value=definition_target,
            unit="acronym" if acronym_mode else "term",
        ))

    if _contains_phrase(query, ("url", "endpoint", "link", "alamat web")):
        add(EvidenceRequirement(
            "answer_url", "an explicit URL, endpoint, link, or email address", "url",
            same_chunk_terms=_subject_terms_for_exact_detail(question),
        ))

    if _contains_phrase(query, ("version", "versi", "version number", "nomor versi", "minimum version", "versi minimum")):
        add(EvidenceRequirement("answer_version", "an explicit version number", "version"))

    if _contains_phrase(query, ("how often", "how frequently", "seberapa sering", "berapa kali", "frekuensi", "jadwal pelaksanaan")):
        add(EvidenceRequirement("answer_cadence", "an explicit cadence or frequency", "cadence"))

    # "How much advance notice" asks for a duration, not money. Monetary intent
    # must include an amount-bearing subject such as cost, allowance, or reimbursement.
    monetary_intent = _contains_phrase(
        query,
        (
            "berapa biaya", "berapa nominal", "nilai nominal", "batas nominal",
            "maximum reimbursement", "minimum reimbursement", "reimbursement limit", "reimbursement maximum",
            "batas reimbursement", "per diem", "allowance",
            "tunjangan", "subsidi", "biaya penggantian", "replacement fee",
            "what amount", "what cost", "how much", "maximum amount", "maximum value",
            "berapa rupiah", "jumlah biaya", "nilai maksimum",
        ),
    )
    duration_amount_phrase = _contains_phrase(
        query,
        ("advance notice", "how much notice", "berapa lama pemberitahuan", "berapa hari sebelumnya"),
    )
    financial_metric_intent = _contains_phrase(
        query,
        (
            "revenue", "pendapatan", "net profit", "gross profit", "laba bersih",
            "laba kotor", "operating income", "annual sales", "quarterly sales",
        ),
    )
    if (monetary_intent or financial_metric_intent) and not duration_amount_phrase:
        add(EvidenceRequirement("answer_money", "an explicit monetary amount", "money"))

    percentage_metric_intent = _contains_phrase(
        query,
        (
            "csat", "customer satisfaction score", "satisfaction score",
            "availability slo", "api availability", "service availability",
            "unit test coverage", "unit-test coverage", "code coverage",
        ),
    )
    if (
        "%" in str(question)
        or _contains_phrase(query, ("persen", "persentase", "percentage", "percent", "margin", "tingkat"))
        or percentage_metric_intent
    ):
        add(EvidenceRequirement("answer_percentage", "an explicit percentage", "percentage"))

    storage_intent = _contains_phrase(
        query,
        (
            "mailbox size", "mailbox limit", "mailbox quota", "storage limit",
            "storage quota", "ukuran mailbox", "batas mailbox", "kapasitas mailbox",
            "batas penyimpanan", "kuota penyimpanan",
            "maximum file upload size", "maximum file-upload size",
            "file upload size", "file-upload size", "upload size limit",
            "maximum attachment size", "attachment size limit",
            "ukuran unggahan file", "batas ukuran file",
            "ukuran maksimum file", "maksimal ukuran unggahan",
        ),
    )
    if storage_intent:
        storage_subjects = tuple(
            concept
            for concept in concepts_in_text(question)
            if concept in {"mailbox_quota", "file_upload", "customer_portal"}
        )
        add(EvidenceRequirement(
            "answer_storage",
            "an explicit storage quantity tied to the requested storage subject",
            "storage",
            subject_concepts=storage_subjects,
        ))

    if _contains_phrase(
        query,
        (
            "how long", "within how long", "how fast", "advance notice", "berapa lama", "seberapa cepat", "batas waktu", "deadline",
            "paling lambat", "berapa hari", "berapa jam", "berapa bulan", "retained", "masa berlaku",
            "valid", "rto", "rpo", "resolved", "acknowledged", "revoke", "submit",
        ),
    ):
        add(EvidenceRequirement("answer_duration", "an explicit duration or deadline", "duration"))

    if _contains_phrase(query, ("when", "kapan", "tanggal berapa", "jam berapa", "payday")):
        add(EvidenceRequirement("answer_date_or_time", "an explicit date, day, or time", "date_or_time"))

    if _contains_phrase(query, ("how many", "berapa banyak", "berapa jumlah", "berapa orang", "berapa pelanggan")):
        add(EvidenceRequirement("answer_count", "an explicit numeric count", "number"))

    if _contains_phrase(
        query,
        (
            "what approval", "which approval", "who approves", "who must approve",
            "approval is needed", "approval required", "persetujuan apa",
            "persetujuan siapa", "siapa yang menyetujui", "siapa yang harus menyetujui",
        ),
    ):
        add(EvidenceRequirement("answer_approval", "an explicit approver or approval rule", "approval"))

    if _contains_phrase(
        query,
        (
            "reported to", "report to", "who must", "who should", "who do i contact",
            "contact whom", "kepada siapa", "lapor ke", "dilaporkan kepada",
            "siapa yang harus dihubungi", "kontak siapa",
        ),
    ) and _contains_phrase(query, ("report", "reported", "contact", "notify", "lapor", "dilaporkan", "hubungi")):
        add(EvidenceRequirement("answer_contact", "an explicit reporting contact or responsible role", "contact"))

    if _contains_phrase(
        query,
        (
            "what document", "what documents", "which document", "which documents",
            "supporting document", "supporting documents", "what must be attached",
            "what should be attached", "what must be submitted", "dokumen apa",
            "dokumen pendukung", "lampiran apa", "bukti apa", "apa yang harus dilampirkan",
            "apa yang harus disertakan", "kuitansi", "receipt",
        ),
    ):
        add(EvidenceRequirement(
            "answer_supporting_document",
            "an explicit supporting document, receipt, proof, or attachment requirement",
            "supporting_document",
        ))

    for phrase_match in QUOTED_PATTERN.finditer(str(question or "")):
        phrase = normalize_text(phrase_match.group(1))
        if len(phrase.split()) >= 3:
            add(EvidenceRequirement(f"quoted:{phrase}", f"the quoted subject '{phrase}'", "literal", value=phrase))

    for year in sorted(set(YEAR_PATTERN.findall(str(question or "")))):
        add(EvidenceRequirement(f"year:{year}", f"the requested year {year}", "year", value=year))

    if not is_scenario_comparison(question):
        for number, unit in numeric_constraints(question):
            add(EvidenceRequirement(
                f"constraint:{number}:{unit}", f"the explicit condition {number} {unit}",
                "numeric_constraint", value=number, unit=unit,
            ))
    else:
        for family in sorted({unit_family(unit) for _, unit in numeric_constraints(question)}):
            add(EvidenceRequirement(
                f"scenario_threshold:{family}", f"a policy threshold in the {family} measurement family",
                "numeric_family", unit=family,
            ))

    return requirements


def _has_numeric_constraint(text: str, number: str, unit: str) -> bool:
    number_pattern = re.escape(number).replace(r"\.", r"[.,]")
    unit_patterns = {
        "days": r"(?:days?|working\s+days?|business\s+days?|hari(?:\s+kerja)?)",
        "years": r"(?:years?|tahun)", "months": r"(?:months?|bulan)",
        "weeks": r"(?:weeks?|minggu)", "hours": r"(?:hours?|hrs?|jam)",
        "minutes": r"(?:minutes?|mins?|menit)", "seconds": r"(?:seconds?|secs?|detik)",
        "characters": r"(?:characters?|chars?|karakter)",
        "requests": r"(?:requests?|calls?|permintaan|panggilan)",
        "%": r"(?:%|percent|percentage|persen)",
        "gb": r"gb", "mb": r"mb", "tb": r"tb", "kb": r"kb",
    }
    return bool(re.search(
        rf"\b{number_pattern}\s*{unit_patterns.get(unit, re.escape(unit))}\b",
        str(text or ""), flags=re.I,
    ))


def _has_numeric_family(text: str, family: str) -> bool:
    for _, unit in numeric_constraints(text):
        if unit_family(unit) == family:
            return True
    if family == "duration" and TIME_PATTERN.search(str(text or "")):
        return True
    if family == "percentage" and PERCENT_PATTERN.search(str(text or "")):
        return True
    return False


def requirement_satisfied(requirement: EvidenceRequirement, evidence_texts: list[str]) -> bool:
    texts = [str(text or "") for text in evidence_texts if str(text or "").strip()]
    combined = "\n".join(texts)
    normalized_combined = normalize_text(combined)

    if requirement.kind == "url":
        for text in texts:
            if not (URL_PATTERN.search(text) or EMAIL_PATTERN.search(text)):
                continue
            normalized = normalize_text(text)
            if not requirement.same_chunk_terms:
                return True
            matched = sum(term in normalized for term in requirement.same_chunk_terms)
            if matched >= min(2, len(requirement.same_chunk_terms)):
                return True
        return False
    if requirement.kind == "definition":
        return any(
            has_explicit_definition(
                text,
                requirement.value,
                acronym_mode=requirement.unit == "acronym",
            )
            for text in texts
        )
    if requirement.kind == "version":
        return bool(VERSION_PATTERN.search(combined))
    if requirement.kind == "cadence":
        return bool(CADENCE_PATTERN.search(combined))
    if requirement.kind == "money":
        return bool(MONEY_PATTERN.search(combined))
    if requirement.kind == "percentage":
        return bool(PERCENT_PATTERN.search(combined))
    if requirement.kind == "storage":
        for text in texts:
            if not STORAGE_PATTERN.search(text):
                continue
            if not requirement.subject_concepts:
                return True
            if all(
                contains_alias(text, CONCEPT_ALIASES.get(concept, (concept,)))
                for concept in requirement.subject_concepts
            ):
                return True
        return False
    if requirement.kind == "duration":
        return bool(TIME_PATTERN.search(combined))
    if requirement.kind == "date_or_time":
        return bool(
            TIME_PATTERN.search(combined)
            or RELATIVE_DATE_TIME_PATTERN.search(combined)
            or re.search(r"\b(?:the\s+)?\d{1,2}(?:st|nd|rd|th)?\b", combined, flags=re.I)
            or re.search(r"\b\d{1,2}[:.]\d{2}\b", combined)
            or YEAR_PATTERN.search(combined)
        )
    if requirement.kind == "number":
        return bool(NUMBER_PATTERN.search(combined))
    if requirement.kind == "approval":
        if re.search(
            r"\b(?:approval|approved|approve|approver|persetujuan|disetujui|menyetujui)\b",
            combined,
            flags=re.I,
        ):
            return True
        # Compact policy tables often encode the approver as
        # ``Below IDR 10,000,000: manager`` without the word "approval".
        # Require both a monetary threshold and an explicit organizational
        # role so an unrelated mention of a manager cannot pass this gate.
        has_threshold = bool(MONEY_PATTERN.search(combined)) and bool(
            re.search(
                r"\b(?:below|under|up\s+to|between|above|over|"
                r"di\s+bawah|hingga|antara|di\s+atas)\b",
                combined,
                flags=re.I,
            )
        )
        has_role = bool(
            re.search(
                r"(?:[:;\-–—]|\brequires?\b|\bby\b)\s*"
                r"(?:the\s+)?(?:manager|department\s+head|director|"
                r"manajer|kepala\s+departemen|direktur)\b",
                combined,
                flags=re.I,
            )
        )
        return has_threshold and has_role
    if requirement.kind == "contact":
        return bool(
            EMAIL_PATTERN.search(combined)
            or re.search(
                r"\b(?:report(?:ed)?\s+to|notify|contact|lapor\s+ke|dilaporkan\s+kepada|hubungi)\b",
                combined,
                flags=re.I,
            )
        )
    if requirement.kind == "supporting_document":
        if re.search(
            r"\b(?:receipt|receipts|invoice|invoices|document|documents|attachment|attachments|"
            r"proof|evidence|kuitansi|faktur|dokumen|lampiran|bukti)\b|"
            r"\b(?:must|required|wajib)\s+(?:be\s+)?(?:attach|attached|submit|submitted|provide|provided|"
            r"dilampirkan|disertakan|diajukan)\b",
            combined,
            flags=re.I,
        ):
            return True
        # Onboarding and identity checklists frequently list the concrete
        # items directly (for example a valid ID, tax ID, and bank details)
        # without repeating the generic word "document". These markers are
        # explicit document/detail types, not inferred answer values.
        explicit_items = (
            r"\b(?:valid\s+(?:photo\s+)?id|identity\s+(?:card|document)|"
            r"government(?:-issued)?\s+id|tax\s+id|npwp|passport|birth\s+certificate|"
            r"medical\s+certificate|bank\s+account\s+details?|bank\s+details?|"
            r"nomor\s+rekening|detail\s+rekening|kartu\s+identitas|identitas\s+resmi|"
            r"surat\s+keterangan|form(?:ulir)?|certificate|license|licence)\b"
        )
        return bool(re.search(explicit_items, combined, flags=re.I))
    if requirement.kind in {"literal", "year"}:
        return requirement.value in normalized_combined
    if requirement.kind == "numeric_constraint":
        return _has_numeric_constraint(combined, requirement.value, requirement.unit)
    if requirement.kind == "numeric_family":
        return _has_numeric_family(combined, requirement.unit)
    return True


def evaluate_requirements(
    question: str,
    evidence_texts: list[str],
) -> tuple[list[str], list[str], list[EvidenceRequirement]]:
    requirements = extract_evidence_requirements(question)
    passed: list[str] = []
    failed: list[str] = []
    for requirement in requirements:
        (passed if requirement_satisfied(requirement, evidence_texts) else failed).append(requirement.key)
    return passed, failed, requirements
