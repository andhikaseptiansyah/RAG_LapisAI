from api.grounding_validator import prune_unsupported_claims, validate_grounded_answer


QUESTION = "Seberapa cepat insiden IT P1 harus diselesaikan?"
EVIDENCE = (
    "Incidents are classified as P1 (critical), P2 (high), P3 (medium), P4 (low). "
    "P1 incidents must be acknowledged within 15 minutes and resolved within 4 hours. "
    "P2 within 1 hour and 8 business hours respectively. "
    "If a P1 is not resolved within 2 hours, it is escalated to the Head of Infrastructure."
)


def chunk():
    return {
        "content": EVIDENCE,
        "answerabilityEvidenceSelected": True,
        "contextSelected": True,
        "evidenceHardFailures": [],
    }


def test_accepts_natural_indonesian_grounded_answer():
    answer = (
        "Berdasarkan ketentuan pada dokumen, insiden IT prioritas P1 harus "
        "diselesaikan dalam waktu 4 jam. Jangka waktu tersebut merupakan "
        "batas penyelesaian yang ditetapkan untuk insiden IT prioritas P1."
    )
    decision = validate_grounded_answer(QUESTION, answer, [chunk()])
    assert decision.supported, decision


def test_prunes_unsupported_explanation_but_keeps_supported_fact():
    answer = (
        "Insiden IT prioritas P1 harus diselesaikan dalam waktu 4 jam. "
        "Ketentuan ini dibuat untuk meningkatkan kepuasan pelanggan."
    )
    pruned = prune_unsupported_claims(QUESTION, answer, [chunk()])
    assert "4 jam" in pruned
    assert "kepuasan pelanggan" not in pruned


def test_rejects_cross_priority_relation_swap():
    answer = "Insiden IT prioritas P2 harus diselesaikan dalam waktu 4 jam."
    decision = validate_grounded_answer(QUESTION, answer, [chunk()])
    assert not decision.supported
    assert "unsupported_claims" in decision.reasons
