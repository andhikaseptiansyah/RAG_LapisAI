from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
ROOT = Path(__file__).resolve().parent


def backup(path: Path) -> Path:
    target = path.with_name(f"{path.name}.backup_chat_citation_{STAMP}")
    shutil.copy2(path, target)
    return target


def write_if_changed(path: Path, original: str, updated: str) -> None:
    if updated == original:
        print(f"[SKIP] {path} sudah berisi perbaikan")
        return
    saved = backup(path)
    path.write_text(updated, encoding="utf-8", newline="\n")
    print(f"[OK]   {path}")
    print(f"       backup: {saved}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Marker tidak ditemukan untuk {label}")
    return text.replace(old, new, 1)


def patch_evidence_verifier() -> None:
    path = ROOT / "retrieval" / "evidence_verifier.py"
    original = path.read_text(encoding="utf-8")
    text = original

    pattern_marker = '''VERSION_PATTERN = re.compile(
    r"\\b(?:version|versi|macos|windows|android|ios)\\s*[v.]?\\s*\\d+(?:\\.\\d+)*\\b",
    flags=re.I,
)
'''
    relative_pattern = pattern_marker + '''
RELATIVE_DATE_TIME_PATTERN = re.compile(
    r"\\b(?:"
    r"(?:the\\s+)?(?:next|following|previous|prior)\\s+(?:working\\s+day|business\\s+day|"
    r"day|week|month|year|payroll(?:\\s+cycle)?)|"
    r"(?:next|following)\\s+month(?:'s)?\\s+payroll|"
    r"payroll\\s+(?:cycle\\s+)?(?:of\\s+)?(?:the\\s+)?(?:next|following)\\s+month|"
    r"(?:hari\\s+kerja|hari|minggu|bulan|tahun|payroll)\\s+(?:sebelumnya|berikutnya)|"
    r"siklus\\s+payroll\\s+(?:bulan\\s+)?berikutnya|"
    r"payroll\\s+bulan\\s+berikutnya"
    r")\\b",
    flags=re.I,
)
'''
    if "RELATIVE_DATE_TIME_PATTERN" not in text:
        text = replace_once(
            text,
            pattern_marker,
            relative_pattern,
            "pengenalan jadwal relatif",
        )

    text = replace_once(
        text,
        '''            NUMBER_PATTERN.search(content_text)
            or TIME_PATTERN.search(content_text)
            or VERSION_PATTERN.search(content_text)
''',
        '''            NUMBER_PATTERN.search(content_text)
            or TIME_PATTERN.search(content_text)
            or RELATIVE_DATE_TIME_PATTERN.search(content_text)
            or VERSION_PATTERN.search(content_text)
''',
        "jadwal relatif sebagai bukti kapan",
    )

    write_if_changed(path, original, text)


def patch_answerability() -> None:
    path = ROOT / "retrieval" / "answerability.py"
    original = path.read_text(encoding="utf-8")
    text = original

    if "verify_evidence" not in text.split("\n", 20)[10:20]:
        text = text.replace(
            "from retrieval.evidence_verifier import HARD_CONCEPTS, _concept_match",
            "from retrieval.evidence_verifier import HARD_CONCEPTS, _concept_match, verify_evidence",
            1,
        )

    helper = '''

def _candidate_document_key(candidate: dict[str, Any]) -> str:
    metadata = candidate.get("metadata") or {}
    return str(
        candidate.get("documentName")
        or candidate.get("document_name")
        or metadata.get("filename")
        or ""
    ).casefold().strip()


def _candidate_chunk_index(candidate: dict[str, Any]) -> int | None:
    metadata = candidate.get("metadata") or {}
    value = candidate.get("chunkIndex", metadata.get("chunk_index"))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _candidate_paragraph_bounds(
    candidate: dict[str, Any],
) -> tuple[int | None, int | None]:
    metadata = candidate.get("metadata") or {}
    start = candidate.get("paragraphStart", metadata.get("paragraph_start"))
    end = candidate.get("paragraphEnd", metadata.get("paragraph_end", start))
    try:
        start_value = int(start) if start is not None else None
    except (TypeError, ValueError):
        start_value = None
    try:
        end_value = int(end) if end is not None else start_value
    except (TypeError, ValueError):
        end_value = start_value
    return start_value, end_value


def _candidates_are_adjacent(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    left_document = _candidate_document_key(left)
    if not left_document or left_document != _candidate_document_key(right):
        return False

    left_meta = left.get("metadata") or {}
    right_meta = right.get("metadata") or {}
    left_page = str(left.get("page", left_meta.get("page")) or "")
    right_page = str(right.get("page", right_meta.get("page")) or "")
    if left_page and right_page and left_page != right_page:
        return False

    left_index = _candidate_chunk_index(left)
    right_index = _candidate_chunk_index(right)
    if left_index is not None and right_index is not None:
        return abs(left_index - right_index) <= 1

    left_start, left_end = _candidate_paragraph_bounds(left)
    right_start, right_end = _candidate_paragraph_bounds(right)
    if left_start is None or right_start is None:
        return False
    left_end = left_end if left_end is not None else left_start
    right_end = right_end if right_end is not None else right_start
    return right_start <= left_end + 1 and left_start <= right_end + 1


def _coherent_evidence_group(
    question: str,
    selected: list[dict[str, Any]],
    required_concepts: set[str],
    requirements: list[EvidenceRequirement],
    min_evidence_score: float,
) -> tuple[list[dict[str, Any]], float]:
    """Select one safe evidence group from one source.

    FAQ and policy text may be split between a question/heading and its answer.
    Only adjacent chunks from the same document may be combined. Cross-document
    stitching is still forbidden.
    """
    groups: list[list[dict[str, Any]]] = [[candidate] for candidate in selected]
    by_document: dict[str, list[dict[str, Any]]] = {}

    for candidate in selected:
        key = _candidate_document_key(candidate)
        if key:
            by_document.setdefault(key, []).append(candidate)

    for document_candidates in by_document.values():
        ordered = sorted(
            document_candidates,
            key=lambda item: (
                _candidate_chunk_index(item)
                if _candidate_chunk_index(item) is not None
                else 10**9,
                _candidate_paragraph_bounds(item)[0]
                if _candidate_paragraph_bounds(item)[0] is not None
                else 10**9,
            ),
        )
        for start in range(len(ordered)):
            group = [ordered[start]]
            for offset in (1, 2):
                position = start + offset
                if position >= len(ordered):
                    break
                if not _candidates_are_adjacent(group[-1], ordered[position]):
                    break
                group.append(ordered[position])
                groups.append(list(group))

    best_group: list[dict[str, Any]] = []
    best_score = 0.0
    seen_ids: set[tuple[str, ...]] = set()

    for group in groups:
        identifiers = tuple(
            str(item.get("chunkId") or f"anon:{index}")
            for index, item in enumerate(group)
        )
        if identifiers in seen_ids:
            continue
        seen_ids.add(identifiers)

        if any(item.get("evidenceHardContradictions") for item in group):
            continue
        combined = "\\n".join(
            str(item.get("content") or "").strip()
            for item in group
        ).strip()
        if not combined:
            continue
        if any(
            not _concept_match(concept, combined)
            for concept in required_concepts
        ):
            continue
        if any(
            not requirement_satisfied(requirement, [combined])
            for requirement in requirements
        ):
            continue

        semantic_score = max(
            (_clamp(item.get("semanticScore")) for item in group),
            default=0.0,
        )
        verification = verify_evidence(
            question,
            combined,
            minimum_score=min_evidence_score,
            semantic_score=semantic_score,
        )
        if not verification.supported:
            continue

        retrieval_score = max(
            (_clamp(item.get("score")) for item in group),
            default=0.0,
        )
        group_score = (
            0.60 * verification.score
            + 0.40 * retrieval_score
        )
        if group_score > best_score:
            best_group = group
            best_score = group_score

    return best_group, _clamp(best_score)
'''

    if "def _coherent_evidence_group(" not in text:
        text = replace_once(
            text,
            "def assess_answerability(\n",
            helper + "\n\ndef assess_answerability(\n",
            "penggabungan adjacent chunks",
        )

    text = replace_once(
        text,
        '''    coherent = [
        candidate
        for candidate in selected
        if _candidate_satisfies_all(candidate, required_concepts, requirements)
    ]
    coherent_chunk_ids = tuple(
        str(item.get("chunkId") or "")
        for item in coherent
        if item.get("chunkId")
    )
''',
        '''    coherent, coherent_group_score = _coherent_evidence_group(
        question,
        selected,
        required_concepts,
        requirements,
        min_evidence_score,
    )
    coherent_chunk_ids = tuple(
        str(item.get("chunkId") or "")
        for item in coherent
        if item.get("chunkId")
    )
''',
        "koherensi lintas adjacent chunks",
    )

    text = replace_once(
        text,
        '''    evidence_supported = supporting_candidate_count > 0
    strictly_supported = coverage_complete and coherent_complete and evidence_supported
''',
        '''    evidence_supported = supporting_candidate_count > 0 or bool(coherent)
    if coherent and supporting_candidate_count == 0:
        supporting_candidate_count = len(coherent)
    strictly_supported = coverage_complete and coherent_complete and evidence_supported
''',
        "dukungan bundle koheren",
    )

    text = replace_once(
        text,
        '''    mean_evidence = sum(_clamp(item.get("evidenceScore")) for item in selected) / len(selected)
''',
        '''    mean_evidence = sum(_clamp(item.get("evidenceScore")) for item in selected) / len(selected)
    if coherent_group_score > 0.0:
        mean_evidence = max(mean_evidence, coherent_group_score)
''',
        "skor bundle koheren",
    )

    text = replace_once(
        text,
        '''    evidence_chunk_ids = tuple(
        str(item.get("chunkId") or "")
        for item in selected
        if item.get("chunkId")
    )
''',
        '''    evidence_source = (
        coherent
        if requires_coherent_evidence and coherent
        else supporting or selected
    )
    evidence_chunk_ids = tuple(
        str(item.get("chunkId") or "")
        for item in evidence_source
        if item.get("chunkId")
    )
''',
        "pemilihan chunk bukti final",
    )

    strict_old = '''            "answerabilityStrictlySupported": bool(
                decision.strictly_supported
                and candidate.get("evidenceSupported") is True
                and (not selected_ids or str(candidate.get("chunkId") or "") in selected_ids)
                and (
                    not decision.requires_coherent_evidence
                    or str(candidate.get("chunkId") or "") in coherent_ids
                )
            ),
'''
    strict_new = '''            "answerabilityStrictlySupported": bool(
                decision.strictly_supported
                and (
                    candidate.get("evidenceSupported") is True
                    or str(candidate.get("chunkId") or "") in coherent_ids
                )
                and (not selected_ids or str(candidate.get("chunkId") or "") in selected_ids)
                and (
                    not decision.requires_coherent_evidence
                    or str(candidate.get("chunkId") or "") in coherent_ids
                )
            ),
'''
    if strict_new not in text:
        if strict_old in text:
            text = text.replace(strict_old, strict_new, 1)
        else:
            text = replace_once(
                text,
                '            "answerabilityStrictlySupported": decision.strictly_supported,\n',
                strict_new,
                "strict support per chunk",
            )

    write_if_changed(path, original, text)


def patch_hybrid_search() -> None:
    path = ROOT / "retrieval" / "hybrid_search.py"
    original = path.read_text(encoding="utf-8")
    text = original

    helper = '''

def _pre_rerank_may_defer(decision) -> bool:
    """Defer only soft chunking/bundle failures to the final gate.

    Missing concepts, values, years, contradictions, and weak base retrieval
    remain hard rejections. The final post-rerank answerability gate is still
    authoritative.
    """
    failed = set(getattr(decision, "failed_checks", ()) or ())
    soft_failures = {
        "supported_evidence",
        "no_coherent_single_chunk_evidence",
        "ambiguous_top_margin",
    }
    return bool(failed) and failed.issubset(soft_failures)
'''
    if "def _pre_rerank_may_defer(" not in text:
        text = replace_once(
            text,
            "def hybrid_search(\n",
            helper + "\n\ndef hybrid_search(\n",
            "soft pre-rerank defer",
        )

    text = replace_once(
        text,
        '''        if not pre_rerank_decision.answerable:
            print(
                "[ANSWERABILITY] Pre-rerank veto rejected query: "
                f"{pre_rerank_decision.reason}"
            )
            return []
''',
        '''        if not pre_rerank_decision.answerable:
            if _pre_rerank_may_defer(pre_rerank_decision):
                print(
                    "[ANSWERABILITY] Pre-rerank soft failure deferred to final gate: "
                    f"{pre_rerank_decision.reason}"
                )
            else:
                print(
                    "[ANSWERABILITY] Pre-rerank veto rejected query: "
                    f"{pre_rerank_decision.reason}"
                )
                return []
''',
        "pre-rerank tidak terlalu cepat menolak",
    )

    write_if_changed(path, original, text)


def patch_answer_formatter() -> None:
    path = ROOT / "api" / "answer_formatter.py"
    original = path.read_text(encoding="utf-8")
    text = original

    contextualizer = '''

def _contextualize_verified_scalar(
    question: str,
    scalar_answer: str,
    language: str,
) -> str:
    """Create a short explanation around an already verified scalar.

    The value remains deterministic. Subject and action are taken only from the
    user question, so this does not invent a new policy detail.
    """
    scalar = _clean_text(scalar_answer).rstrip(".")
    if not scalar:
        return ""

    normalized = normalize_text(question)
    target = "EN" if str(language).upper() == "EN" else "ID"

    if target == "ID":
        if "p1" in normalized and "insiden" in normalized:
            subject = "insiden IT prioritas P1"
        elif "p2" in normalized and "insiden" in normalized:
            subject = "insiden IT prioritas P2"
        elif "insiden" in normalized:
            subject = "insiden tersebut"
        elif "akses" in normalized:
            subject = "akses tersebut"
        elif "laporan" in normalized:
            subject = "laporan tersebut"
        elif "permintaan" in normalized:
            subject = "permintaan tersebut"
        else:
            subject = "proses yang ditanyakan"

        if any(term in normalized for term in ("diselesaikan", "penyelesaian", "selesai")):
            action = "harus diselesaikan"
            explanation = "batas penyelesaian"
        elif any(term in normalized for term in ("diakui", "ditanggapi", "respons")):
            action = "harus ditanggapi"
            explanation = "batas waktu tanggapan"
        elif any(term in normalized for term in ("dilaporkan", "melaporkan")):
            action = "harus dilaporkan"
            explanation = "batas waktu pelaporan"
        elif any(term in normalized for term in ("diproses", "pemrosesan", "proses")):
            action = "harus diproses"
            explanation = "batas waktu pemrosesan"
        elif any(term in normalized for term in ("dicabut", "mencabut")):
            action = "harus dicabut"
            explanation = "batas waktu pencabutan"
        else:
            action = "memiliki jangka waktu"
            explanation = "jangka waktu"

        if action == "memiliki jangka waktu":
            first = (
                f"Berdasarkan dokumen sumber, {subject} memiliki "
                f"jangka waktu {scalar}."
            )
        else:
            first = (
                f"Berdasarkan dokumen sumber, {subject} {action} "
                f"dalam waktu {scalar}."
            )
        return (
            f"{first} Jangka waktu tersebut merupakan {explanation} "
            "yang ditetapkan dalam dokumen."
        )

    if "p1" in normalized and "incident" in normalized:
        subject = "the P1 IT incident"
    elif "p2" in normalized and "incident" in normalized:
        subject = "the P2 IT incident"
    elif "incident" in normalized:
        subject = "the incident"
    else:
        subject = "the requested process"

    if any(term in normalized for term in ("resolved", "resolution", "completed")):
        action = "must be completed"
        explanation = "the resolution time limit"
    elif any(term in normalized for term in ("acknowledged", "acknowledgement", "responded")):
        action = "must be acknowledged"
        explanation = "the acknowledgement time limit"
    elif any(term in normalized for term in ("reported", "report")):
        action = "must be reported"
        explanation = "the reporting time limit"
    elif any(term in normalized for term in ("processed", "processing")):
        action = "must be processed"
        explanation = "the processing time limit"
    elif any(term in normalized for term in ("revoked", "revoke")):
        action = "must be revoked"
        explanation = "the revocation time limit"
    else:
        action = "has a specified period of"
        explanation = "the time limit"

    if action == "has a specified period of":
        first = (
            f"According to the source document, {subject} has a "
            f"specified period of {scalar}."
        )
    else:
        first = (
            f"According to the source document, {subject} {action} "
            f"within {scalar}."
        )
    return f"{first} This period is {explanation} stated in the document."
'''
    if "def _contextualize_verified_scalar(" not in text:
        text = replace_once(
            text,
            "def build_verified_scalar_answer(\n",
            contextualizer + "\n\ndef build_verified_scalar_answer(\n",
            "jawaban scalar kontekstual",
        )

    text = replace_once(
        text,
        '''    return top_answer


def _clean_extractive_text''',
        '''    return _contextualize_verified_scalar(
        question,
        top_answer,
        target,
    )


def _clean_extractive_text''',
        "pemakaian jawaban scalar kontekstual",
    )

    build_sources_start = text.index("def build_sources(")
    prefix = text[:build_sources_start]
    source_part = text[build_sources_start:]

    source_part = replace_once(
        source_part,
        '''            and chunk.get("evidenceSupported") is True
            and not chunk.get("evidenceHardContradictions")
''',
        '''            and (
                chunk.get("evidenceSupported") is True
                or chunk.get("answerabilityCoherentEvidence") is True
            )
            and not chunk.get("evidenceHardContradictions")
''',
        "sitasi dari coherent evidence",
    )

    source_part = replace_once(
        source_part,
        '''        evidence_supported = chunk.get("evidenceSupported") is True
''',
        '''        evidence_supported = bool(
            chunk.get("evidenceSupported") is True
            or chunk.get("answerabilityCoherentEvidence") is True
        )
''',
        "dukungan sitasi coherent",
    )

    source_part = replace_once(
        source_part,
        '''        raw_page = _normalize_page(chunk.get("page", metadata.get("page")))
''',
        '''        raw_page = _normalize_page(chunk.get("page", metadata.get("page")))
        if isinstance(raw_page, int) and raw_page < 1:
            raw_page = None
''',
        "validasi nomor halaman",
    )

    source_part = replace_once(
        source_part,
        '''            "excerpt": excerpt,
        }
''',
        '''            "excerpt": excerpt,
            "citation_validated": bool(excerpt),
            "citation_support_score": round(
                max(raw_score, clamp_score(chunk.get("evidenceScore"))),
                4,
            ),
        }
''',
        "metadata validasi sitasi",
    )

    source_part = replace_once(
        source_part,
        '''        dedupe_key = (
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
''',
        '''        dedupe_key = (
            document_name.casefold(),
            document_type,
            str(page or ""),
            str(chapter or "").casefold(),
        )
        existing = unique_sources.get(dedupe_key)

        if existing is None:
            unique_sources[dedupe_key] = source
        else:
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
                f"{existing.get('excerpt', '')} "
                f"{source.get('excerpt', '')}"
            )
            if combined_excerpt:
                existing["excerpt"] = build_evidence_excerpt(
                    question,
                    combined_excerpt,
                ) or combined_excerpt
                existing["citation_validated"] = True

            if source["relevance_score"] > existing["relevance_score"]:
                existing["score"] = source["score"]
                existing["relevance_score"] = source["relevance_score"]
            existing["citation_support_score"] = max(
                existing.get("citation_support_score", 0.0),
                source.get("citation_support_score", 0.0),
            )
''',
        "penggabungan rentang sitasi",
    )

    text = prefix + source_part

    top_start = text.index("def top_confidence(")
    prefix = text[:top_start]
    top_part = text[top_start:]
    top_part = replace_once(
        top_part,
        '''        and chunk.get("evidenceSupported") is True
        and not chunk.get("evidenceHardContradictions")
''',
        '''        and (
            chunk.get("evidenceSupported") is True
            or chunk.get("answerabilityCoherentEvidence") is True
        )
        and not chunk.get("evidenceHardContradictions")
''',
        "confidence coherent evidence",
    )
    text = prefix + top_part

    write_if_changed(path, original, text)


def patch_chat_service() -> None:
    path = ROOT / "api" / "chat_service.py"
    original = path.read_text(encoding="utf-8")
    text = replace_once(
        original,
        '''        and chunk.get("answerabilityStrictlySupported", chunk.get("evidenceSupported") is True)
''',
        '''        and chunk.get(
            "answerabilityStrictlySupported",
            chunk.get("evidenceSupported") is True
            or chunk.get("answerabilityCoherentEvidence") is True,
        )
''',
        "strict coherent generation context",
    )
    write_if_changed(path, original, text)


def write_tests() -> None:
    path = ROOT / "tests" / "test_general_false_refusal_and_citations.py"
    content = '''from api.answer_formatter import build_sources, has_answerable_evidence
from retrieval.answerability import apply_answerability_gate, assess_answerability
from retrieval.evidence_verifier import verify_chunks
from retrieval.hybrid_search import _pre_rerank_may_defer


PENSION_QUESTION = "Apakah perusahaan memberikan manfaat pensiun bagi karyawan?"


def _faq_split_candidates():
    base = {
        "documentName": "FAQ_Benefits.txt",
        "page": "-",
        "score": 0.76,
        "baseScore": 0.74,
        "semanticScore": 0.83,
        "keywordScore": 0.55,
        "exactTokenCoverage": 0.45,
        "metadata": {
            "filename": "FAQ_Benefits.txt",
            "document_type": "txt",
        },
    }
    return [
        {
            **base,
            "chunkId": "benefit-10",
            "chunkIndex": 10,
            "content": "Q: Is there a pension benefit?",
            "metadata": {
                **base["metadata"],
                "chunk_index": 10,
                "paragraph_start": 21,
                "paragraph_end": 21,
            },
        },
        {
            **base,
            "chunkId": "benefit-11",
            "chunkIndex": 11,
            "content": (
                "A: The company contributes to BPJS Ketenagakerjaan "
                "for all employees."
            ),
            "metadata": {
                **base["metadata"],
                "chunk_index": 11,
                "paragraph_start": 22,
                "paragraph_end": 22,
            },
        },
    ]


def test_adjacent_faq_chunks_form_one_coherent_answer_bundle():
    verified = verify_chunks(PENSION_QUESTION, _faq_split_candidates())
    decision = assess_answerability(PENSION_QUESTION, verified)
    assert decision.answerable, decision.reason
    assert set(decision.coherent_chunk_ids) == {"benefit-10", "benefit-11"}

    gated = apply_answerability_gate(PENSION_QUESTION, verified)
    assert has_answerable_evidence(gated)
    assert all(row["answerabilityCoherentEvidence"] for row in gated)


def test_pre_rerank_only_defers_soft_bundle_failures():
    verified = verify_chunks(PENSION_QUESTION, _faq_split_candidates())
    decision = assess_answerability(PENSION_QUESTION, verified[:1])
    assert not decision.answerable
    assert _pre_rerank_may_defer(decision)


def test_citations_merge_adjacent_paragraphs_and_keep_pdf_page():
    chunks = []
    for chunk_id, start, end, content, score in (
        (
            "c1",
            4,
            5,
            "The policy states that approved requests are recorded.",
            0.82,
        ),
        (
            "c2",
            6,
            7,
            "Payment is made in the following payroll cycle.",
            0.80,
        ),
    ):
        chunks.append(
            {
                "chunkId": chunk_id,
                "documentName": "Policy.pdf",
                "page": 3,
                "content": content,
                "score": score,
                "evidenceScore": 0.88,
                "evidenceSupported": True,
                "answerabilityAccepted": True,
                "answerabilityStrictlySupported": True,
                "answerabilityEvidenceSelected": True,
                "answerabilityRequiresCoherentEvidence": True,
                "answerabilityCoherentEvidence": True,
                "contextSelected": True,
                "metadata": {
                    "filename": "Policy.pdf",
                    "document_type": "pdf",
                    "page": 3,
                    "paragraph_start": start,
                    "paragraph_end": end,
                },
            }
        )

    sources = build_sources(
        chunks,
        question="When is payment made?",
        limit=2,
    )
    assert len(sources) == 1
    source = sources[0]
    assert source["page"] == 3
    assert source["page_is_reliable"] is True
    assert source["paragraph_start"] == 4
    assert source["paragraph_end"] == 7
    assert source["citation_validated"] is True


def test_txt_citation_never_claims_a_physical_page():
    chunks = apply_answerability_gate(
        PENSION_QUESTION,
        verify_chunks(PENSION_QUESTION, _faq_split_candidates()),
    )
    sources = build_sources(chunks, question=PENSION_QUESTION, limit=2)
    assert len(sources) == 1
    assert sources[0]["document_name"] == "FAQ_Benefits.txt"
    assert sources[0]["page"] is None
    assert sources[0]["paragraph_start"] == 21
    assert sources[0]["paragraph_end"] == 22
'''
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"[OK]   test regresi: {path}")


def main() -> None:
    required = [
        ROOT / "retrieval" / "evidence_verifier.py",
        ROOT / "retrieval" / "answerability.py",
        ROOT / "retrieval" / "hybrid_search.py",
        ROOT / "api" / "answer_formatter.py",
        ROOT / "api" / "chat_service.py",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Jalankan script dari folder backend. File tidak ditemukan: "
            + ", ".join(missing)
        )

    patch_evidence_verifier()
    patch_answerability()
    patch_hybrid_search()
    patch_answer_formatter()
    patch_chat_service()
    write_tests()

    print("\nPatch chat dan sitasi selesai.")
    print("Restart backend lalu jalankan test regresi.")


if __name__ == "__main__":
    main()
