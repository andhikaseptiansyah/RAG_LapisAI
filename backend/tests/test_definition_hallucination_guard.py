from api.answer_formatter import _definition_answer, build_sources
from api.grounding_validator import prune_unsupported_claims, validate_grounded_answer
from retrieval.answerability import assess_answerability
from retrieval.requirements import (
    extract_definition_target,
    extract_evidence_requirements,
    requirement_satisfied,
)


QUESTION = "what is SOP"
TITLE_ONLY_EVIDENCE = (
    "Nusantara Dynamics SOP - Business Travel Booking. "
    "Domestic flights must be booked at least 7 days in advance through the "
    "appointed travel agent. Economy class is standard for domestic travel."
)
EXPLICIT_DEFINITION = (
    "Standard Operating Procedure (SOP) is a documented set of standard steps "
    "for a recurring process."
)
HALLUCINATED_ANSWER = (
    "SOP adalah singkatan dari Standard Operating Procedure. "
    "SOP digunakan oleh Nusantara Dynamics untuk mengatur berbagai proses bisnis."
)


def candidate(content: str, name: str = "SOP_Travel_Booking.pdf") -> dict:
    return {
        "chunkId": "definition-1",
        "content": content,
        "documentName": name,
        "page": 1,
        "score": 0.98,
        "baseScore": 0.95,
        "preEvidenceScore": 0.95,
        "semanticScore": 0.98,
        "exactTokenCoverage": 1.0,
        "evidenceSupported": True,
        "evidenceScore": 0.95,
        "evidenceHardFailures": [],
        "evidenceHardContradictions": [],
        "evidenceContradictions": [],
        "evidenceMissingRequirements": [],
        "rerankerApplied": True,
    }


def strict_candidate(content: str, name: str = "SOP_Travel_Booking.pdf") -> dict:
    return {
        **candidate(content, name),
        "answerabilityAccepted": True,
        "answerabilityStrictlySupported": True,
        "answerabilityEvidenceSelected": True,
        "answerabilityCoherentEvidence": True,
        "contextSelected": True,
    }


def definition_requirement(question: str = QUESTION):
    return next(
        item
        for item in extract_evidence_requirements(question)
        if item.key == "answer_definition"
    )


def test_definition_intent_does_not_capture_multiword_value_question() -> None:
    assert extract_definition_target(QUESTION) == "SOP"
    assert extract_definition_target("apa itu SOP") == "SOP"
    assert extract_definition_target("what is my mailbox size limit") is None


def test_title_mention_is_not_an_explicit_definition() -> None:
    requirement = definition_requirement()
    assert requirement_satisfied(requirement, [TITLE_ONLY_EVIDENCE]) is False
    assert requirement_satisfied(requirement, ["SOP (Travel Booking)"]) is False
    assert requirement_satisfied(requirement, [EXPLICIT_DEFINITION]) is True


def test_answerability_rejects_high_scoring_title_only_match() -> None:
    decision = assess_answerability(QUESTION, [candidate(TITLE_ONLY_EVIDENCE)])
    assert decision.answerable is False
    assert "explicit_definition" in decision.failed_checks


def test_grounding_rejects_definition_not_present_in_evidence() -> None:
    decision = validate_grounded_answer(
        QUESTION,
        HALLUCINATED_ANSWER,
        [candidate(TITLE_ONLY_EVIDENCE)],
    )
    assert decision.supported is False
    assert "missing_evidence_requirement" in decision.reasons
    assert decision.missing_evidence_requirements == ("answer_definition",)
    assert prune_unsupported_claims(
        QUESTION,
        HALLUCINATED_ANSWER,
        [candidate(TITLE_ONLY_EVIDENCE)],
    ) == ""


def test_definition_formatter_does_not_convert_document_title_into_definition() -> None:
    assert _definition_answer(
        QUESTION,
        [candidate(TITLE_ONLY_EVIDENCE)],
        "ID",
    ) is None
    valid = _definition_answer(
        QUESTION,
        [candidate(EXPLICIT_DEFINITION, "Glossary.pdf")],
        "ID",
    )
    assert valid is not None
    assert "Standard Operating Procedure" in valid[0]


def test_citation_builder_returns_no_false_source_for_hallucinated_answer() -> None:
    sources = build_sources(
        [strict_candidate(TITLE_ONLY_EVIDENCE)],
        question=QUESTION,
        answer=HALLUCINATED_ANSWER,
    )
    assert sources == []


def test_explicit_definition_remains_answerable_and_citable() -> None:
    evidence = candidate(EXPLICIT_DEFINITION, "Glossary.pdf")
    assert assess_answerability(QUESTION, [evidence]).answerable is True

    answer = "SOP adalah singkatan dari Standard Operating Procedure."
    grounding = validate_grounded_answer(QUESTION, answer, [evidence])
    assert grounding.supported is True

    sources = build_sources(
        [strict_candidate(EXPLICIT_DEFINITION, "Glossary.pdf")],
        question=QUESTION,
        answer=answer,
    )
    assert len(sources) == 1
    assert sources[0]["document_name"] == "Glossary.pdf"
