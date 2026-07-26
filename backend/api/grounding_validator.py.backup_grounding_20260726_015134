"""Deterministic post-generation grounding validation.

The validator checks answer completeness and rejects explicit facts that cannot be
traced to selected evidence or to values supplied in the user's scenario. It is
language-tolerant for Indonesian/English paraphrases but strict for numbers,
units, money, percentages, versions, URLs, emails, and system identifiers.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from retrieval.query_expansion import CONCEPT_ALIASES, normalize_text
from retrieval.requirements import (
    EMAIL_PATTERN,
    URL_PATTERN,
    VERSION_PATTERN,
    canonical_unit,
    extract_evidence_requirements,
    is_scenario_comparison,
    requirement_satisfied,
)
from uploads.config import GENERATION_MIN_CLAIM_SUPPORT


@dataclass(frozen=True)
class GroundingDecision:
    supported: bool
    score: float
    reasons: tuple[str, ...]
    unsupported_facts: tuple[str, ...]
    unsupported_claims: tuple[str, ...] = ()
    missing_answer_requirements: tuple[str, ...] = ()
    checked_claims: int = 0

    @property
    def support_score(self) -> float:
        """Compatibility alias used by the newer API diagnostics."""
        return self.score

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["support_score"] = self.score
        for key in (
            "reasons",
            "unsupported_facts",
            "unsupported_claims",
            "missing_answer_requirements",
        ):
            payload[key] = list(payload[key])
        return payload


# Backward-compatible public name from the first reliability patch.
GroundingValidation = GroundingDecision


STOPWORDS = {
    "yang", "dan", "atau", "adalah", "dengan", "untuk", "dalam", "pada", "dari",
    "ke", "sebagai", "oleh", "ini", "itu", "tersebut", "harus", "dapat", "akan",
    "juga", "kepada",
    "the", "and", "or", "is", "are", "was", "were", "with", "for", "to", "in",
    "on", "of", "by", "this", "that", "must", "can", "will", "a", "an",
    "according", "based", "berdasarkan", "document", "dokumen", "source", "sumber",
}

WORD_NUMBERS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "nol": "0", "satu": "1", "dua": "2", "tiga": "3", "empat": "4",
    "lima": "5", "enam": "6", "tujuh": "7", "delapan": "8", "sembilan": "9", "sepuluh": "10",
}
WORD_NUMBER_PATTERN = "|".join(sorted((re.escape(key) for key in WORD_NUMBERS), key=len, reverse=True))
NUMBER_CORE = r"(?:\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?|" + WORD_NUMBER_PATTERN + r")"

MONEY_PATTERN = re.compile(
    rf"\b(?:IDR|Rp\.?|USD|EUR)\s*{NUMBER_CORE}"
    r"(?:\s*(?:ribu|thousand|juta|million|miliar|billion|triliun|trillion))?\b",
    flags=re.I,
)
PERCENT_PATTERN = re.compile(
    rf"\b{NUMBER_CORE}\s*(?:%|persen|percent|percentage)\b",
    flags=re.I,
)
NUMBER_UNIT_PATTERN = re.compile(
    rf"\b({NUMBER_CORE}|\d+\s*[x×]\s*\d+)\s*"
    r"(GB|MB|TB|KB|minutes?|mins?|hours?|hrs?|working\s+days?|business\s+days?|days?|weeks?|months?|years?|"
    r"seconds?|secs?|menit|jam|hari\s+kerja|hari|minggu|bulan|tahun|detik|characters?|chars?|karakter|"
    r"requests?|calls?|customers?|pelanggan)\b",
    flags=re.I,
)
PLAIN_NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?(?:st|nd|rd|th)?\b", flags=re.I)
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
ACRONYM_PATTERN = re.compile(r"\b[A-Z][A-Z0-9/_-]{1,11}\b")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+|\s+[•-]\s+")
CLAUSE_SPLIT = re.compile(
    r"\s*(?:;|\b(?:and|but|because|due\s+to|therefore|thus|while|whereas|"
    r"dan|tetapi|namun|karena|sehingga|sedangkan)\b)\s*",
    flags=re.I,
)
CONDITIONAL_COMMA_PREFIX = re.compile(
    r"^\s*(?:if|when|once|before|after|unless|provided\s+that|"
    r"jika|ketika|apabila|bila|sebelum|setelah)\b",
    flags=re.I,
)

# Grounding needs a slightly richer bilingual vocabulary than retrieval.
# These aliases do not add facts or retrieval hits. They only prove that an
# Indonesian claim is a faithful rendering of the same English evidence unit.
GROUNDING_CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    **CONCEPT_ALIASES,
    "probation": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("probation", ()),
        "serve a probation period",
        "serves a probation period",
        "probation lasts",
        "probation period lasts",
        "masa percobaan berlangsung",
        "masa percobaan selama",
        "menjalani masa percobaan",
        "berlangsung selama masa percobaan",
    ))),
    "new_employee": (
        "new employee",
        "new employees",
        "new hire",
        "new hires",
        "karyawan baru",
        "pegawai baru",
    ),
    "performance_evaluation": (
        "performance evaluation",
        "formal performance evaluation",
        "performance review",
        "evaluation is conducted",
        "evaluasi kinerja",
        "evaluasi kinerja formal",
        "evaluasi formal",
        "evaluasi dilakukan",
        "dilakukan evaluasi",
    ),
    "employment_confirmation": (
        "before confirmation",
        "employee confirmation",
        "confirmation decision",
        "sebelum konfirmasi",
        "konfirmasi karyawan",
        "keputusan konfirmasi",
    ),
    "incident_acknowledgement": (
        "incident acknowledgement",
        "incident acknowledgment",
        "must be acknowledged",
        "acknowledged within",
        "acknowledgement time",
        "acknowledgment time",
        "insiden harus diakui",
        "harus diakui",
        "diakui dalam",
        "waktu pengakuan insiden",
        "respons awal",
        "respons awal diberikan",
    ),
    "incident_escalation": (
        "incident escalation",
        "is escalated",
        "it is escalated",
        "escalated to",
        "if not resolved",
        "not resolved within",
        "eskalasi insiden",
        "insiden dieskalasikan",
        "akan dieskalasikan",
        "dieskalasikan kepada",
        "jika belum selesai",
        "jika belum diselesaikan",
        "belum terselesaikan",
    ),
    "infrastructure_head": (
        "head of infrastructure",
        "infrastructure head",
        "kepala infrastruktur",
    ),
}

# These qualifiers materially change the meaning of a claim. A generated claim
# may use an Indonesian or English alias, but the same qualifier family must be
# present in the supporting evidence unit. This blocks unsupported additions such
# as "because it is scalable", "only", "unless", or "approximately".
QUALIFIER_PATTERNS: dict[str, re.Pattern[str]] = {
    "causal": re.compile(
        r"\b(?:because|due\s+to|caused\s+by|as\s+a\s+result|karena|disebabkan\s+oleh|sehingga)\b",
        flags=re.I,
    ),
    "exclusive": re.compile(r"\b(?:only|solely|exclusively|hanya)\b", flags=re.I),
    "minimum": re.compile(
        r"\b(?:at\s+least|minimum|minimal|no\s+less\s+than|sekurang-kurangnya)\b",
        flags=re.I,
    ),
    "maximum": re.compile(
        r"\b(?:up\s+to|within|maximum|maximal|maksimal|no\s+more\s+than|"
        r"no\s+later\s+than|paling\s+banyak|paling\s+lambat|selambat-lambatnya|"
        r"dalam\s+waktu)\b",
        flags=re.I,
    ),
    "exception": re.compile(r"\b(?:except|unless|excluding|kecuali)\b", flags=re.I),
    "prohibition": re.compile(
        r"\b(?:must\s+not|cannot|may\s+not|not\s+allowed|prohibited|dilarang|tidak\s+boleh)\b",
        flags=re.I,
    ),
    "approximate": re.compile(
        r"\b(?:about|approximately|roughly|around|sekitar|kurang\s+lebih)\b",
        flags=re.I,
    ),
    "unmet_condition": re.compile(
        r"\b(?:if\b.{0,45}\bnot\s+resolved|not\s+resolved\s+within|"
        r"jika\b.{0,45}\bbelum\s+(?:selesai|diselesaikan|terselesaikan)|"
        r"belum\s+(?:selesai|diselesaikan|terselesaikan))\b",
        flags=re.I,
    ),
}

IGNORED_ACRONYMS = {
    "IDR", "USD", "EUR", "WIB", "GB", "MB", "TB", "KB", "FAQ", "SOP",
    "PDF", "DOCX", "TXT", "AI", "IT",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_number(value: str) -> str:
    raw = normalize_text(value)
    if raw in WORD_NUMBERS:
        return WORD_NUMBERS[raw]
    raw = re.sub(r"(?:st|nd|rd|th)$", "", str(value).strip(), flags=re.I).replace(" ", "")
    if "x" in raw.casefold() or "×" in raw:
        return raw.casefold().replace("×", "x")
    # A single separator followed by one or two digits is treated as decimal.
    if raw.count(",") == 1 and raw.count(".") == 0 and len(raw.split(",")[-1]) <= 2:
        return raw.replace(",", ".")
    if raw.count(".") == 1 and raw.count(",") == 0 and len(raw.split(".")[-1]) <= 2:
        return raw
    return raw.replace(",", "").replace(".", "")


def _normalize_magnitude(value: str) -> str:
    mapping = {
        "ribu": "thousand", "thousand": "thousand",
        "juta": "million", "million": "million",
        "miliar": "billion", "billion": "billion",
        "triliun": "trillion", "trillion": "trillion",
    }
    return mapping.get(normalize_text(value), normalize_text(value))


def _tokenize(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9à-ÿ]+", normalize_text(value))
        if len(token) >= 3 and token not in STOPWORDS
    }


def _grounding_concepts(value: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9à-ÿ]+", " ", normalize_text(value))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    padded = f" {normalized} "
    return {
        canonical
        for canonical, aliases in GROUNDING_CONCEPT_ALIASES.items()
        if any(
            (
                candidate := re.sub(
                    r"\s+",
                    " ",
                    re.sub(r"[^a-z0-9à-ÿ]+", " ", normalize_text(alias)),
                ).strip()
            )
            and f" {candidate} " in padded
            for alias in aliases
        )
    }


def _span_overlaps(span: tuple[int, int], occupied: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < other_end and end > other_start for other_start, other_end in occupied)


def _fact_entries(value: str) -> list[tuple[str, str, str]]:
    """Return unique (key, raw display, canonical display) facts."""
    raw = str(value or "")
    entries: list[tuple[str, str, str]] = []
    occupied: list[tuple[int, int]] = []

    def add(key: str, display: str, canonical_display: str, span: tuple[int, int] | None = None) -> None:
        if key not in {item[0] for item in entries}:
            entries.append((key, display, canonical_display))
        if span is not None:
            occupied.append(span)

    for match in URL_PATTERN.finditer(raw):
        display = match.group(0).rstrip(".,;)]}")
        add(f"url:{display.casefold()}", display, display.casefold(), match.span())
    for match in EMAIL_PATTERN.finditer(raw):
        display = match.group(0)
        add(f"email:{display.casefold()}", display, display.casefold(), match.span())

    for match in MONEY_PATTERN.finditer(raw):
        display = match.group(0)
        parsed = re.search(
            rf"\b(IDR|Rp\.?|USD|EUR)\s*({NUMBER_CORE})"
            r"(?:\s*(ribu|thousand|juta|million|miliar|billion|triliun|trillion))?\b",
            display,
            flags=re.I,
        )
        if parsed:
            currency = parsed.group(1).casefold().replace("rp.", "idr").replace("rp", "idr")
            number = _normalize_number(parsed.group(2))
            magnitude = _normalize_magnitude(parsed.group(3) or "")
            canonical = " ".join(part for part in (currency, number, magnitude) if part)
            add(f"money:{currency}:{number}:{magnitude}", display, canonical, match.span())

    for match in PERCENT_PATTERN.finditer(raw):
        if _span_overlaps(match.span(), occupied):
            continue
        display = match.group(0)
        number_match = re.search(NUMBER_CORE, display, flags=re.I)
        if number_match:
            number = _normalize_number(number_match.group(0))
            add(f"percent:{number}", display, f"{number}%", match.span())

    for match in NUMBER_UNIT_PATTERN.finditer(raw):
        if _span_overlaps(match.span(), occupied):
            continue
        display = match.group(0)
        number = _normalize_number(match.group(1))
        unit = canonical_unit(match.group(2))
        canonical = f"{number} {unit}".strip()
        add(f"quantity:{number}:{unit}", display, canonical, match.span())

    for match in VERSION_PATTERN.finditer(raw):
        if _span_overlaps(match.span(), occupied):
            continue
        display = match.group(0)
        normalized = normalize_text(display)
        add(f"version:{normalized}", display, normalized, match.span())

    for match in YEAR_PATTERN.finditer(raw):
        if _span_overlaps(match.span(), occupied):
            continue
        display = match.group(0)
        add(f"year:{display}", display, display, match.span())

    for match in PLAIN_NUMBER_PATTERN.finditer(raw):
        if _span_overlaps(match.span(), occupied):
            continue
        display = match.group(0)
        number = _normalize_number(display)
        add(f"number:{number}", display, number, match.span())

    for match in ACRONYM_PATTERN.finditer(raw):
        display = match.group(0).upper()
        if display in IGNORED_ACRONYMS or display.isdigit():
            continue
        if re.fullmatch(r"FY(?:19|20)\d{2}", display):
            # YEAR_PATTERN already records the comparable year key.
            continue
        add(f"identifier:{display}", display, display)

    return entries


def _selected_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        chunk
        for chunk in chunks
        if chunk.get("answerabilityEvidenceSelected", True)
        and chunk.get("contextSelected", True)
        and not chunk.get("evidenceHardFailures")
    ] or [
        chunk for chunk in chunks
        if not chunk.get("evidenceHardFailures")
    ]


def _evidence_units(chunks: list[dict[str, Any]]) -> list[str]:
    """Split evidence into claim-sized units without mixing separate sources."""
    units: list[str] = []
    for chunk in _selected_chunks(chunks):
        content = _clean(chunk.get("content"))
        if not content:
            continue
        # Keep the whole chunk as a source-bounded unit so a valid answer may
        # combine adjacent sentences from the same passage. Separate chunks are
        # never merged, which still blocks cross-document relation swapping.
        if content not in units:
            units.append(content)
        parts = [
            _clean(part).lstrip("-• ")
            for part in SENTENCE_SPLIT.split(content)
            if _clean(part).lstrip("-• ")
        ]
        for part in parts:
            if part not in units:
                units.append(part)
    return units


def _context_text(chunks: list[dict[str, Any]]) -> str:
    return "\n".join(_evidence_units(chunks))


def _qualifier_families(value: str) -> set[str]:
    return {
        family
        for family, pattern in QUALIFIER_PATTERNS.items()
        if pattern.search(str(value or ""))
    }


def _atomic_claims(value: Any) -> list[str]:
    """Split an answer into independently validated factual claims.

    Besides sentence boundaries, comma-separated and semicolon-separated
    list items are checked individually. This prevents one supported item
    from hiding another unsupported item.

    Example:

        Bring your ID, academic transcripts.

    becomes:

        Bring your ID
        academic transcripts

    Commas inside numbers such as 1,000 are not treated as separators.
    """

    raw_text = str(value or "")
    claims: list[str] = []
    seen: set[str] = set()

    for raw_sentence in SENTENCE_SPLIT.split(raw_text):
        sentence = _clean(raw_sentence).lstrip("-? ")

        if not sentence:
            continue

        # Bersihkan artefak tanda baca seperti ",." dan spasi sebelum koma.
        sentence = re.sub(
            r"\s+([,.;:!?])",
            r"\1",
            sentence,
        )
        sentence = re.sub(
            r",\s*\.$",
            ".",
            sentence,
        )
        sentence = sentence.strip()

        # Pisahkan klausa kausal/kontras terlebih dahulu. Ini memungkinkan
        # bagian fakta yang didukung tetap dipertahankan ketika model menambah
        # ekor spekulatif seperti "because it is more scalable".
        clause_parts = [
            part for part in CLAUSE_SPLIT.split(sentence)
            if _clean(part)
        ] or [sentence]

        # Pecah daftar berdasarkan koma/semicolon, tetapi jangan pecah koma
        # yang berada di antara angka, misalnya 1,000.
        parts: list[str] = []
        for clause_part in clause_parts:
            if CONDITIONAL_COMMA_PREFIX.search(clause_part):
                # Keep conditional and temporal prefixes attached to the main
                # clause. Splitting "Jika belum selesai, insiden dieskalasikan"
                # creates two fragments that cannot be grounded independently.
                parts.extend(re.split(r";", clause_part))
            else:
                parts.extend(re.split(r"(?<!\d),(?!\d)|;", clause_part))

        cleaned_parts: list[str] = []

        for part in parts:
            clean_part = _clean(part).lstrip("-? ")

            # Hilangkan kata sambung pada awal item.
            clean_part = re.sub(
                r"^(?:and|or|dan|atau|serta)\s+",
                "",
                clean_part,
                flags=re.I,
            )

            clean_part = clean_part.strip(
                " ,;:."
            )

            if clean_part:
                cleaned_parts.append(clean_part)

        # Hanya gunakan pemecahan daftar jika memang ada minimal dua item.
        candidate_claims = (
            cleaned_parts
            if len(cleaned_parts) >= 2
            else [sentence.strip(" ,;:")]
        )

        for claim in candidate_claims:
            claim = _clean(claim).strip()

            if not claim:
                continue

            normalized = re.sub(
                r"\W+",
                "",
                claim.casefold(),
            )

            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            claims.append(claim)

    return claims


def _claim_reference_units(claim: str, evidence_units: list[str]) -> list[str]:
    claim_fact_keys = {key for key, _, _ in _fact_entries(claim)}
    if not claim_fact_keys:
        return list(evidence_units)
    return [
        unit
        for unit in evidence_units
        if claim_fact_keys.issubset({key for key, _, _ in _fact_entries(unit)})
    ]


def _canonical_claim_token_coverage(
    claim: str,
    unit: str,
    claim_concepts: set[str],
    unit_concepts: set[str],
) -> float:
    """Measure bilingual claim coverage through canonical aliases and facts.

    Literal token overlap is naturally low when the answer is Indonesian and the
    indexed evidence is English. The retrieval layer already maps both languages
    to the same domain concepts, so the grounding validator must reuse that same
    canonical vocabulary instead of treating a faithful translation as an
    unsupported claim.

    The bridge remains strict: every concept in the claim must exist in the same
    evidence unit, every explicit fact is already bound to that unit by
    ``_claim_reference_units``, and almost every remaining content token must be
    explainable by a known bilingual alias or an explicit fact. Unsupported tails
    therefore do not receive this cross-language support floor.
    """
    claim_tokens = _tokenize(claim)
    if not claim_tokens:
        return 1.0
    if not claim_concepts or not claim_concepts.issubset(unit_concepts):
        return 0.0

    covered = set(claim_tokens.intersection(_tokenize(unit)))

    for concept in claim_concepts:
        for alias in GROUNDING_CONCEPT_ALIASES.get(concept, ()):
            covered.update(claim_tokens.intersection(_tokenize(alias)))

    for _, raw, canonical in _fact_entries(claim):
        covered.update(claim_tokens.intersection(_tokenize(raw)))
        covered.update(claim_tokens.intersection(_tokenize(canonical)))

    return len(covered) / len(claim_tokens)


def _claim_support(
    claim: str,
    evidence_units: list[str],
    *,
    question: str = "",
) -> float:
    """Return support from one evidence unit, not a token soup across documents."""
    claim_tokens = _tokenize(claim)
    claim_concepts = _grounding_concepts(claim)
    question_concepts = _grounding_concepts(question)
    claim_qualifiers = _qualifier_families(claim)
    if not claim_tokens and not claim_concepts:
        return 1.0

    scores: list[float] = []
    for unit in evidence_units:
        # Material qualifiers must be explicit in the same evidence unit. This is
        # stricter than ordinary paraphrase matching because these words change
        # the policy or causal meaning of the claim.
        if not claim_qualifiers.issubset(_qualifier_families(unit)):
            continue

        unit_tokens = _tokenize(unit)
        lexical = (
            len(claim_tokens.intersection(unit_tokens)) / len(claim_tokens)
            if claim_tokens
            else 0.0
        )
        unit_concepts = _grounding_concepts(unit) | question_concepts
        concept = (
            len(claim_concepts.intersection(unit_concepts)) / len(claim_concepts)
            if claim_concepts
            else 0.0
        )

        # Concept aliases may bridge Indonesian/English wording. Literal overlap
        # still remains the default, while a high canonical-token coverage allows
        # a faithful translation to pass without lowering the global threshold.
        if claim_tokens and claim_concepts:
            score = max(lexical, 0.75 * lexical + 0.25 * concept)
        elif claim_concepts:
            score = concept
        else:
            score = lexical

        canonical_coverage = _canonical_claim_token_coverage(
            claim,
            unit,
            claim_concepts,
            unit_concepts,
        )
        has_explicit_facts = bool(_fact_entries(claim))
        required_coverage = 0.85 if has_explicit_facts else 0.95
        if canonical_coverage + 1e-9 >= required_coverage:
            score = max(score, canonical_coverage)

        scores.append(score)
    return max(scores, default=0.0)


def prune_unsupported_claims(
    question: str,
    answer: str,
    chunks: list[dict[str, Any]],
    *,
    minimum_claim_support: float = GENERATION_MIN_CLAIM_SUPPORT,
) -> str:
    """Return only independently supported claims, or an empty string.

    The function never invents replacement text. It removes unsupported clauses
    from the model output and keeps the remaining answer only when all explicit
    answer-type requirements are still satisfied.
    """
    evidence_units = _evidence_units(chunks)
    if is_scenario_comparison(question):
        evidence_units = [*evidence_units, question]

    kept: list[str] = []
    for claim in _atomic_claims(answer):
        reference_units = _claim_reference_units(claim, evidence_units)
        if not reference_units:
            continue
        if (
            _claim_support(claim, reference_units, question=question) + 1e-9
            < minimum_claim_support
        ):
            continue
        if claim not in kept:
            kept.append(claim)

    if not kept:
        return ""

    candidate = ". ".join(item.rstrip(".!? ") for item in kept).strip()
    if candidate and candidate[-1:] not in ".!?":
        candidate += "."

    for requirement in extract_evidence_requirements(question):
        if requirement.key.startswith("answer_") and not requirement_satisfied(requirement, [candidate]):
            return ""
    return candidate


def _unsupported_fact_displays(
    answer_entries: list[tuple[str, str, str]],
    allowed_keys: set[str],
) -> list[str]:
    output: list[str] = []
    for key, raw, canonical in answer_entries:
        if key in allowed_keys:
            continue
        # Keep the original text for user-facing diagnostics and the canonical
        # text for stable regression assertions across punctuation/languages.
        for display in (raw, canonical):
            if display and display not in output:
                output.append(display)
    return output


def validate_grounded_answer(
    question: str,
    answer: str,
    chunks: list[dict[str, Any]],
    *,
    minimum_claim_support: float = GENERATION_MIN_CLAIM_SUPPORT,
) -> GroundingDecision:
    clean_answer = _clean(answer)
    evidence_units = _evidence_units(chunks)
    context = "\n".join(evidence_units)
    if not clean_answer or not context:
        return GroundingDecision(
            supported=False,
            score=0.0,
            reasons=("empty_answer_or_context",),
            unsupported_facts=(),
        )

    context_entries = _fact_entries(context)
    question_entries = _fact_entries(question) if is_scenario_comparison(question) else []
    allowed_keys = {key for key, _, _ in context_entries + question_entries}
    answer_entries = _fact_entries(clean_answer)
    unsupported_facts = _unsupported_fact_displays(answer_entries, allowed_keys)

    claim_reference_units = list(evidence_units)
    if is_scenario_comparison(question):
        claim_reference_units.append(question)

    unsupported_claims: list[str] = []
    claim_scores: list[float] = []
    for claim in _atomic_claims(answer):
        # Validate short substantive answers as well. Skipping claims with fewer
        # than four words allowed unsupported answers such as "MySQL" to pass.
        if not _tokenize(claim) and not _fact_entries(claim):
            continue
        fact_bound_units = _claim_reference_units(claim, claim_reference_units)
        # A factual claim must be supported by the same evidence unit that
        # contains its explicit values. This prevents relation swapping across
        # chunks, such as attaching a P2 deadline to a P1 incident.
        score = (
            _claim_support(claim, fact_bound_units, question=question)
            if fact_bound_units
            else 0.0
        )
        claim_scores.append(score)
        if score + 1e-9 < minimum_claim_support:
            unsupported_claims.append(claim[:220])

    missing_requirements: list[str] = []
    for requirement in extract_evidence_requirements(question):
        if not requirement.key.startswith("answer_"):
            continue
        if not requirement_satisfied(requirement, [clean_answer]):
            missing_requirements.append(requirement.key)

    reasons: list[str] = []
    if unsupported_facts:
        reasons.append("unsupported_explicit_facts")
    if unsupported_claims:
        reasons.append("unsupported_claims")
    if missing_requirements:
        reasons.append("incomplete_answer_type")

    unique_facts = tuple(dict.fromkeys(unsupported_facts))
    unique_claims = tuple(dict.fromkeys(unsupported_claims))
    unique_missing = tuple(dict.fromkeys(missing_requirements))
    mean_claim = sum(claim_scores) / len(claim_scores) if claim_scores else 1.0
    penalty = min(
        1.0,
        0.28 * len(unique_facts)
        + 0.22 * len(unique_claims)
        + 0.25 * len(unique_missing),
    )
    score = max(0.0, min(mean_claim * (1.0 - penalty), 1.0))

    return GroundingDecision(
        supported=not reasons,
        score=round(score, 6),
        reasons=tuple(reasons),
        unsupported_facts=unique_facts,
        unsupported_claims=unique_claims,
        missing_answer_requirements=unique_missing,
        checked_claims=len(claim_scores),
    )
