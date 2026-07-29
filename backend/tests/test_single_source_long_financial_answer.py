from api.answer_formatter import build_sources
from api.grounding_validator import validate_grounded_answer
import api.ollama_client as ollama_client

QUESTION = "Berapa pendapatan tahun 2025 dan margin laba bersih perusahaan?"
ANSWER = "Pendapatan tahun 2025 perusahaan adalah IDR 158 miliar. Margin laba bersih perusahaan adalah 14%."

def _chunk(name: str, content: str, score: float):
    return {
        "documentName": name,
        "documentType": "pdf",
        "page": 1,
        "pageIsReliable": True,
        "paragraphStart": 1,
        "paragraphEnd": 4,
        "content": content,
        "score": score,
        "semanticScore": score,
        "evidenceScore": score,
        "evidenceSupported": True,
        "answerabilityAccepted": True,
        "answerabilityStrictlySupported": True,
        "answerabilityEvidenceSelected": True,
        "contextSelected": True,
        "evidenceHardFailures": [],
        "evidenceHardContradictions": [],
    }

def test_one_complete_source_replaces_topical_secondary_source():
    chunks = [
        _chunk("Report_Financial_FY2025.pdf", "Full-year 2025 revenue was IDR 158 billion. Net profit margin was 14%.", 0.84),
        _chunk("Report_Q3_2025_Performance.pdf", "Q3 2025 revenue was IDR 42.5 billion, a 12% increase over Q2 2025. Customer churn was 2.1%.", 0.77),
    ]
    sources = build_sources(chunks, question=QUESTION, answer=ANSWER, limit=2)
    assert len(sources) == 1
    assert sources[0]["document_name"] == "Report_Financial_FY2025.pdf"
    assert sources[0]["citation_validated"] is True


def test_repetitive_multi_metric_expansion_is_removed():
    assert not hasattr(ollama_client, '_expand_supported_multi_metric_answer')
