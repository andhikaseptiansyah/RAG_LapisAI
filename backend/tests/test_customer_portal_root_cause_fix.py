from retrieval.answerability import assess_answerability
from retrieval.evidence_verifier import verify_evidence
from retrieval.query_expansion import CONCEPT_ALIASES, concepts_in_text, contains_alias


QUESTION = "Apa penyebab utama gangguan portal pelanggan pada 14 Oktober 2025?"
EVIDENCE = (
    "Nusantara Dynamics Incident Postmortem - October 2025. "
    "The 14 October 2025 outage lasted 3 hours 20 minutes, affecting the customer portal. "
    "The root cause was an expired TLS certificate on the API gateway."
)


def _chunk(content: str, decision):
    return {
        "chunkId": "incident-postmortem-1",
        "content": content,
        "score": 0.84,
        "baseScore": 0.80,
        "semanticScore": 0.90,
        "evidenceSupported": decision.supported,
        "evidenceScore": decision.score,
        "evidenceHardFailures": list(decision.hard_failures),
        "metadata": {
            "filename": "Report_Incident_Postmortem.pdf",
            "page": 1,
            "paragraph_start": 1,
            "paragraph_end": 8,
        },
    }


def test_alias_matches_before_sentence_punctuation():
    assert contains_alias(
        "The outage affected the customer portal.",
        CONCEPT_ALIASES["customer_portal"],
    )
    assert "customer_portal" in concepts_in_text(
        "The outage affected the customer portal."
    )


def test_short_alias_does_not_match_inside_an_unrelated_word():
    assert not contains_alias("corporate policy", ("rpo",))


def test_customer_portal_root_cause_passes_evidence_and_answerability():
    evidence = verify_evidence(QUESTION, EVIDENCE, semantic_score=0.90)
    assert evidence.supported is True
    assert "customer_portal" in evidence.matched_concepts
    assert not evidence.hard_failures

    answerability = assess_answerability(QUESTION, [_chunk(EVIDENCE, evidence)])
    assert answerability.answerable is True
    assert answerability.strictly_supported is True
    assert "concept:customer_portal" in answerability.passed_checks


def test_negative_upload_size_question_still_has_no_storage_answer():
    question = "What is the maximum file-upload size in the customer portal?"
    evidence = verify_evidence(question, EVIDENCE, semantic_score=0.90)
    # Portal matching is fixed, but the unrelated postmortem still lacks the
    # requested file-upload concept and storage value. The safety gate remains.
    assert evidence.supported is False
    assert any(
        item in evidence.hard_failures
        for item in ("missing_concept:file_upload", "missing_numeric_value")
    )
