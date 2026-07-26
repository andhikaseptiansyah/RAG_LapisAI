from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if not (ROOT / "api").is_dir():
    ROOT = Path.cwd()

API = ROOT / "api"
ANSWER_FORMATTER = API / "answer_formatter.py"
CHAT_SERVICE = API / "chat_service.py"
OLLAMA_CLIENT = API / "ollama_client.py"
TEST_FILE = ROOT / "tests" / "test_single_source_long_financial_answer.py"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def backup(path: Path) -> None:
    destination = path.with_name(path.name + f".backup_single_source_{STAMP}")
    shutil.copy2(path, destination)
    print(f"       backup: {destination}")


def replace_build_sources(text: str) -> str:
    start = text.find("def build_sources(")
    end = text.find("\ndef build_refusal_answer", start)
    if start < 0 or end < 0:
        raise RuntimeError("Fungsi build_sources() tidak ditemukan")

    replacement = r'''def build_sources(
    chunks: list[dict[str, Any]],
    question: str = "",
    limit: int = 2,
    answer: str = "",
) -> list[dict[str, Any]]:
    """Return only citations that support the final answer.

    Citations are grouped by document and physical location. When one source
    independently supports the complete final answer, only the strongest such
    source is returned. Multiple sources are retained only when separate
    evidence units are genuinely needed to support different answer claims.

    PDF citations keep physical page metadata. DOCX pages are shown only when
    the parser marked them reliable. TXT uses chapter and paragraph ranges.
    """
    confidence = answer_confidence(question, chunks)
    answerability_accepted = has_answerable_evidence(chunks)
    if confidence < MIN_ANSWER_CONFIDENCE and not answerability_accepted:
        return []

    if answerability_accepted:
        source_chunks = [
            chunk for chunk in chunks
            if chunk.get("answerabilityAccepted") is True
            and chunk.get("answerabilityEvidenceSelected", True)
            and chunk.get("contextSelected", True)
            and (
                chunk.get("evidenceSupported") is True
                or chunk.get("answerabilityCoherentEvidence") is True
            )
            and not chunk.get("evidenceHardFailures")
            and not chunk.get("evidenceHardContradictions")
            and (
                not chunk.get("answerabilityRequiresCoherentEvidence")
                or chunk.get("answerabilityCoherentEvidence") is True
            )
        ]
    else:
        source_chunks = [
            chunk for chunk in chunks
            if chunk.get("contextSelected", True)
            and not chunk.get("evidenceHardFailures")
            and not chunk.get("evidenceHardContradictions")
        ]

    grouped_sources: dict[tuple[str, ...], dict[str, Any]] = {}
    grouped_chunks: dict[tuple[str, ...], list[dict[str, Any]]] = {}

    for chunk in source_chunks:
        raw_score = clamp_score(chunk.get("score"))
        semantic_score = clamp_score(chunk.get("semanticScore"))
        evidence_supported = bool(
            chunk.get("evidenceSupported") is True
            or chunk.get("answerabilityCoherentEvidence") is True
        )

        if answerability_accepted:
            if not evidence_supported:
                continue
        elif not (
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
        if isinstance(raw_page, int) and raw_page < 1:
            raw_page = None
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
        if document_type == "txt" and paragraph_start is None:
            paragraph_start = chunk.get(
                "lineStart", metadata.get("line_start")
            )
            paragraph_end = chunk.get(
                "lineEnd", metadata.get("line_end")
            )

        excerpt = build_evidence_excerpt(
            question,
            chunk.get("content") or metadata.get("content") or "",
        )
        evidence_score = clamp_score(chunk.get("evidenceScore"))

        # Adjacent chunks on the same document page/section are one citation.
        group_key = (
            document_name.casefold(),
            document_type,
            str(page or ""),
            str(chapter or "").casefold(),
        )
        grouped_chunks.setdefault(group_key, []).append(chunk)

        source: dict[str, Any] = {
            "document_name": document_name,
            "document_type": document_type,
            "page": page,
            "page_is_reliable": page_is_reliable,
            "score": round(raw_score, 4),
            "relevance_score": round(raw_score, 4),
            "excerpt": excerpt,
            "citation_validated": bool(excerpt),
            "citation_support_score": round(max(raw_score, evidence_score), 4),
        }
        if chapter:
            source["chapter"] = chapter
            source["section"] = chapter
        if paragraph_start is not None:
            source["paragraph_start"] = int(paragraph_start)
        if paragraph_end is not None:
            source["paragraph_end"] = int(paragraph_end)

        existing = grouped_sources.get(group_key)
        if existing is None:
            grouped_sources[group_key] = source
            continue

        starts = [
            value
            for value in (
                existing.get("paragraph_start"),
                source.get("paragraph_start"),
            )
            if value is not None
        ]
        ends = [
            value
            for value in (
                existing.get("paragraph_end"),
                source.get("paragraph_end"),
            )
            if value is not None
        ]
        if starts:
            existing["paragraph_start"] = min(starts)
        if ends:
            existing["paragraph_end"] = max(ends)

        combined_excerpt = _clean_text(
            f"{existing.get('excerpt', '')} {source.get('excerpt', '')}"
        )
        if combined_excerpt:
            existing["excerpt"] = (
                build_evidence_excerpt(question, combined_excerpt)
                or combined_excerpt
            )
        if source["relevance_score"] > existing["relevance_score"]:
            existing["score"] = source["score"]
            existing["relevance_score"] = source["relevance_score"]
        existing["citation_support_score"] = max(
            existing.get("citation_support_score", 0.0),
            source.get("citation_support_score", 0.0),
        )

    if not grouped_sources:
        return []

    full_support: list[dict[str, Any]] = []
    partial_support: list[dict[str, Any]] = []
    clean_answer = answer_text_only(answer)

    if clean_answer:
        # Validate citations claim-by-claim. Missing answer-type requirements are
        # ignored for an individual claim because separate sources may support
        # complementary parts of one multi-part answer. Unsupported facts and
        # unsupported claims remain disqualifying.
        from api.grounding_validator import (
            _atomic_claims,
            validate_grounded_answer,
        )

        answer_claims = _atomic_claims(clean_answer)
        total_claim_chars = sum(len(claim) for claim in answer_claims) or 1

        for group_key, source in grouped_sources.items():
            evidence_group = grouped_chunks[group_key]
            supported_claims: list[str] = []
            claim_scores: list[float] = []

            for claim in answer_claims:
                claim_decision = validate_grounded_answer(
                    question,
                    claim,
                    evidence_group,
                )
                if (
                    not claim_decision.unsupported_facts
                    and not claim_decision.unsupported_claims
                ):
                    supported_claims.append(claim)
                    claim_scores.append(claim_decision.support_score)

            if not supported_claims:
                continue

            coverage = sum(len(claim) for claim in supported_claims) / total_claim_chars
            support_score = (
                sum(claim_scores) / len(claim_scores)
                if claim_scores
                else 0.0
            )
            source["citation_validated"] = True
            source["citation_support_score"] = round(
                max(
                    source.get("citation_support_score", 0.0),
                    support_score,
                ),
                4,
            )
            source["citation_answer_coverage"] = round(min(coverage, 1.0), 4)

            if len(supported_claims) == len(answer_claims):
                source["citation_answer_coverage"] = 1.0
                full_support.append(source)
            else:
                partial_support.append(source)

    # One complete source is preferable to several merely topically similar
    # sources. This removes Q3 reports from a full-year answer when the annual
    # report alone supports every generated claim.
    if full_support:
        best = max(
            full_support,
            key=lambda source: (
                source.get("citation_support_score", 0.0),
                source.get("relevance_score", 0.0),
            ),
        )
        return [best]

    effective_limit = min(max(1, int(limit)), MAX_SOURCE_CITATIONS)
    if partial_support:
        return sorted(
            partial_support,
            key=lambda source: (
                source.get("citation_answer_coverage", 0.0),
                source.get("citation_support_score", 0.0),
                source.get("relevance_score", 0.0),
            ),
            reverse=True,
        )[:effective_limit]

    # Compatibility path for callers that do not yet pass the final answer.
    return sorted(
        grouped_sources.values(),
        key=lambda source: source.get("relevance_score", 0.0),
        reverse=True,
    )[:effective_limit]
'''
    return text[:start] + replacement + text[end:]


def patch_chat_service(text: str) -> str:
    pattern = re.compile(
        r"sources\s*=\s*build_sources\(\s*chunks,\s*question=question,\s*limit=MAX_SOURCE_CITATIONS,?\s*\)",
        flags=re.S,
    )
    replacement = (
        "sources = build_sources(\n"
        "        chunks,\n"
        "        question=question,\n"
        "        limit=MAX_SOURCE_CITATIONS,\n"
        "        answer=answer,\n"
        "    )"
    )
    patched, count = pattern.subn(replacement, text, count=1)
    if count == 0:
        if "answer=answer" in text and "build_sources(" in text:
            return text
        raise RuntimeError("Pemanggilan build_sources() di chat_service.py tidak ditemukan")
    return patched


EXPANSION_FUNCTION = r'''

def _expand_supported_multi_metric_answer(
    question: str,
    answer: str,
    language: str,
) -> str:
    """Add one grounded summary sentence for a two-metric financial answer.

    The sentence only repeats the money and percentage already present in the
    validated answer. It never introduces a new number, reason, trend, or
    interpretation. A second grounding pass decides whether the expansion may
    be returned.
    """
    clean_answer = _clean_text(answer)
    normalized_question = _clean_text(question).casefold()
    if not clean_answer or _question_expected_numeric_values(question) < 2:
        return clean_answer

    revenue_terms = ("pendapatan", "revenue")
    margin_terms = (
        "margin laba bersih",
        "marjin laba bersih",
        "net profit margin",
        "net margin",
    )
    if not any(term in normalized_question for term in revenue_terms):
        return clean_answer
    if not any(term in normalized_question for term in margin_terms):
        return clean_answer

    # Keep already detailed answers unchanged.
    sentence_count = len([
        item for item in re.split(r"(?<=[.!?])\s+", clean_answer)
        if _clean_text(item)
    ])
    if sentence_count >= 3:
        return clean_answer

    money_match = re.search(
        r"\b(?:IDR|Rp\.?|USD|EUR)\s*\d[\d.,]*"
        r"(?:\s*(?:ribu|juta|miliar|triliun|thousand|million|billion|trillion))?\b",
        clean_answer,
        flags=re.I,
    )
    percent_match = re.search(
        r"\b\d+(?:[.,]\d+)?\s*(?:%(?=$|[^0-9])|persen\b|percent\b)",
        clean_answer,
        flags=re.I,
    )
    year_match = re.search(r"\b(?:19|20)\d{2}\b", question)
    if not money_match or not percent_match:
        return clean_answer

    money = _clean_text(money_match.group(0))
    percentage = _clean_text(percent_match.group(0))
    year = year_match.group(0) if year_match else ""

    if language.upper() == "EN":
        period = f" in {year}" if year else ""
        if year:
            summary = (
                f"For {year} the company recorded revenue of {money} with a "
                f"net profit margin of {percentage}."
            )
        else:
            summary = (
                f"The company recorded revenue of {money} with a net profit "
                f"margin of {percentage}."
            )
    else:
        period = f" tahun {year}" if year else ""
        if year:
            summary = (
                f"Untuk tahun {year} perusahaan mencatat pendapatan {money} "
                f"dengan margin laba bersih {percentage}."
            )
        else:
            summary = (
                f"Perusahaan mencatat pendapatan {money} dengan margin laba "
                f"bersih {percentage}."
            )

    normalized_summary = re.sub(r"\W+", "", summary.casefold())
    normalized_answer = re.sub(r"\W+", "", clean_answer.casefold())
    if normalized_summary and normalized_summary in normalized_answer:
        return clean_answer

    candidate = f"{clean_answer.rstrip()} {summary}".strip()
    if len(candidate) > MAX_ANSWER_CHARS:
        return clean_answer
    return candidate
'''


def patch_ollama_client(text: str) -> str:
    if "def _expand_supported_multi_metric_answer(" not in text:
        marker = "\ndef _is_likely_incomplete_answer("
        position = text.find(marker)
        if position < 0:
            raise RuntimeError("Lokasi penyisipan fungsi ekspansi tidak ditemukan")
        text = text[:position] + EXPANSION_FUNCTION + text[position:]

    if "expanded_candidate = _expand_supported_multi_metric_answer(" not in text:
        marker = "\n    if is_refusal_answer(llm_answer):"
        position = text.find(marker)
        if position < 0:
            raise RuntimeError("Blok final Ollama tidak ditemukan")
        insertion = r'''

    # Multi-part financial questions are easier to read with one concise summary
    # sentence. The candidate is accepted only if the same grounding validator
    # confirms that every repeated value and relationship remains supported.
    expanded_candidate = _expand_supported_multi_metric_answer(
        question,
        llm_answer,
        language,
    )
    if expanded_candidate != llm_answer:
        expanded_grounding = validate_grounded_answer(
            question,
            expanded_candidate,
            grounding_chunks,
        )
        if (
            expanded_grounding.supported
            and answer_matches_requested_language(expanded_candidate, language)
            and not _is_likely_incomplete_answer(question, expanded_candidate)
        ):
            llm_answer = expanded_candidate
            print("[GROUNDING] added a grounded multi-metric summary sentence")
'''
        text = text[:position] + insertion + text[position:]
    return text


def write_test() -> None:
    TEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEST_FILE.write_text(
        '''from api.answer_formatter import build_sources\n'''
        '''from api.grounding_validator import validate_grounded_answer\n'''
        '''from api.ollama_client import _expand_supported_multi_metric_answer\n\n'''
        '''QUESTION = "Berapa pendapatan tahun 2025 dan margin laba bersih perusahaan?"\n'''
        '''ANSWER = "Pendapatan tahun 2025 perusahaan adalah IDR 158 miliar. Margin laba bersih perusahaan adalah 14%."\n\n'''
        '''def _chunk(name: str, content: str, score: float):\n'''
        '''    return {\n'''
        '''        "documentName": name,\n'''
        '''        "documentType": "pdf",\n'''
        '''        "page": 1,\n'''
        '''        "pageIsReliable": True,\n'''
        '''        "paragraphStart": 1,\n'''
        '''        "paragraphEnd": 4,\n'''
        '''        "content": content,\n'''
        '''        "score": score,\n'''
        '''        "semanticScore": score,\n'''
        '''        "evidenceScore": score,\n'''
        '''        "evidenceSupported": True,\n'''
        '''        "answerabilityAccepted": True,\n'''
        '''        "answerabilityStrictlySupported": True,\n'''
        '''        "answerabilityEvidenceSelected": True,\n'''
        '''        "contextSelected": True,\n'''
        '''        "evidenceHardFailures": [],\n'''
        '''        "evidenceHardContradictions": [],\n'''
        '''    }\n\n'''
        '''def test_one_complete_source_replaces_topical_secondary_source():\n'''
        '''    chunks = [\n'''
        '''        _chunk("Report_Financial_FY2025.pdf", "Full-year 2025 revenue was IDR 158 billion. Net profit margin was 14%.", 0.84),\n'''
        '''        _chunk("Report_Q3_2025_Performance.pdf", "Q3 2025 revenue was IDR 42.5 billion, a 12% increase over Q2 2025. Customer churn was 2.1%.", 0.77),\n'''
        '''    ]\n'''
        '''    sources = build_sources(chunks, question=QUESTION, answer=ANSWER, limit=2)\n'''
        '''    assert len(sources) == 1\n'''
        '''    assert sources[0]["document_name"] == "Report_Financial_FY2025.pdf"\n'''
        '''    assert sources[0]["citation_validated"] is True\n\n'''
        '''def test_financial_answer_gets_one_grounded_summary_sentence():\n'''
        '''    expanded = _expand_supported_multi_metric_answer(QUESTION, ANSWER, "ID")\n'''
        '''    assert expanded.count(".") >= 3\n'''
        '''    assert "IDR 158 miliar" in expanded\n'''
        '''    assert "14%" in expanded\n'''
        '''    chunk = _chunk("Report_Financial_FY2025.pdf", "Full-year 2025 revenue was IDR 158 billion. Net profit margin was 14%.", 0.84)\n'''
        '''    decision = validate_grounded_answer(QUESTION, expanded, [chunk])\n'''
        '''    assert decision.supported is True\n''',
        encoding="utf-8",
    )
    print(f"[OK]   test regresi: {TEST_FILE}")


def patch_file(path: Path, transform) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    original = path.read_text(encoding="utf-8")
    patched = transform(original)
    if patched == original:
        print(f"[SKIP] {path} sudah memuat perbaikan")
        return
    backup(path)
    path.write_text(patched, encoding="utf-8")
    print(f"[OK]   {path}")


def main() -> None:
    patch_file(ANSWER_FORMATTER, replace_build_sources)
    patch_file(CHAT_SERVICE, patch_chat_service)
    patch_file(OLLAMA_CLIENT, patch_ollama_client)
    write_test()
    print("\nPatch selesai. Jalankan test lalu restart backend.")


if __name__ == "__main__":
    main()
