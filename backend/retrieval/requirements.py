"""Generic evidence requirements for answerability and grounding validation.

This module extracts answer-type requirements from arbitrary Indonesian or
English questions. It intentionally avoids rules tied to individual benchmark
questions, so the runtime remains useful outside the evaluation set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from retrieval.query_expansion import normalize_text


@dataclass(frozen=True)
class EvidenceRequirement:
    key: str
    description: str
    kind: str
    value: str = ""
    unit: str = ""
    same_chunk_terms: tuple[str, ...] = ()


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
NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\b")
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
QUOTED_PATTERN = re.compile(r"['\"“”‘’*]([^'\"“”‘’*]{8,160})['\"“”‘’*]")
NUMBER_WITH_UNIT_PATTERN = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(GB|MB|TB|KB|days?|years?|months?|weeks?|hours?|"
    r"minutes?|seconds?|characters?|chars?|requests?|calls?|hari|tahun|bulan|minggu|jam|"
    r"menit|detik|karakter|permintaan|panggilan|%|persen|percent)(?=$|[^A-Za-z0-9])",
    flags=re.I,
)


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

    if _contains_phrase(
        query,
        (
            "mailbox size", "mailbox limit", "mailbox quota", "storage limit",
            "storage quota", "ukuran mailbox", "batas mailbox", "kapasitas mailbox",
            "batas penyimpanan", "kuota penyimpanan",
        ),
    ):
        add(EvidenceRequirement("answer_storage", "an explicit storage quantity", "storage"))

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
    if requirement.kind == "version":
        return bool(VERSION_PATTERN.search(combined))
    if requirement.kind == "cadence":
        return bool(CADENCE_PATTERN.search(combined))
    if requirement.kind == "money":
        return bool(MONEY_PATTERN.search(combined))
    if requirement.kind == "percentage":
        return bool(PERCENT_PATTERN.search(combined))
    if requirement.kind == "storage":
        return bool(STORAGE_PATTERN.search(combined))
    if requirement.kind == "duration":
        return bool(TIME_PATTERN.search(combined))
    if requirement.kind == "date_or_time":
        return bool(
            TIME_PATTERN.search(combined)
            or re.search(r"\b(?:the\s+)?\d{1,2}(?:st|nd|rd|th)?\b", combined, flags=re.I)
            or re.search(r"\b\d{1,2}[:.]\d{2}\b", combined)
            or YEAR_PATTERN.search(combined)
        )
    if requirement.kind == "number":
        return bool(NUMBER_PATTERN.search(combined))
    if requirement.kind == "approval":
        return bool(re.search(
            r"\b(?:approval|approved|approve|approver|persetujuan|disetujui|menyetujui)\b",
            combined,
            flags=re.I,
        ))
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
        return bool(re.search(
            r"\b(?:receipt|receipts|invoice|invoices|document|documents|attachment|attachments|"
            r"proof|evidence|kuitansi|faktur|dokumen|lampiran|bukti)\b|"
            r"\b(?:must|required|wajib)\s+(?:be\s+)?(?:attach|attached|submit|submitted|provide|provided|"
            r"dilampirkan|disertakan|diajukan)\b",
            combined,
            flags=re.I,
        ))
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
