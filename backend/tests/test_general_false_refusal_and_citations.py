from api.answer_formatter import build_sources, has_answerable_evidence
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
