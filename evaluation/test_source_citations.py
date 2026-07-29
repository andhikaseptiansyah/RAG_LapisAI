from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.answer_formatter import build_sources  # noqa: E402


def main() -> int:
    question = "How long is the probation period and when is it reviewed?"
    pdf_content = (
        "New employees serve a probation period of 3 months. "
        "A formal performance evaluation is conducted in week 12 before confirmation."
    )

    pdf_sources = build_sources(
        [
            {
                "documentName": "SOP_Onboarding.pdf",
                "page": 5,
                "content": pdf_content,
                "score": 0.95,
                "semanticScore": 0.91,
                "evidenceSupported": True,
                "metadata": {
                    "filename": "SOP_Onboarding.pdf",
                    "document_type": "pdf",
                    "page": 5,
                    "page_is_reliable": True,
                    "location_type": "page_paragraphs",
                    "paragraph_start": 3,
                    "paragraph_end": 4,
                },
            }
        ],
        question=question,
    )
    assert pdf_sources, "PDF source should pass the citation confidence gate."
    assert pdf_sources[0]["page"] == 5
    assert pdf_sources[0]["page_is_reliable"] is True
    assert pdf_sources[0]["paragraph_start"] == 3
    assert pdf_sources[0]["paragraph_end"] == 4
    assert "3 months" in pdf_sources[0]["excerpt"]
    assert "week 12" in pdf_sources[0]["excerpt"]

    docx_sources = build_sources(
        [
            {
                "documentName": "Policy_WFH.docx",
                "page": 2,
                "content": (
                    "Employees may work from home up to two days per week "
                    "with manager approval."
                ),
                "score": 0.93,
                "semanticScore": 0.90,
                "evidenceSupported": True,
                "metadata": {
                    "filename": "Policy_WFH.docx",
                    "document_type": "docx",
                    "page": 2,
                    "page_is_reliable": True,
                    "location_type": "page_paragraphs",
                    "chapter": "Working Arrangements",
                    "paragraph_start": 11,
                    "paragraph_end": 20,
                },
            }
        ],
        question="What is the work-from-home policy?",
    )
    assert docx_sources
    assert docx_sources[0]["page"] == 2
    assert docx_sources[0]["page_is_reliable"] is True
    assert docx_sources[0]["chapter"] == "Working Arrangements"
    assert docx_sources[0]["paragraph_start"] == 11
    assert docx_sources[0]["paragraph_end"] == 20

    unreliable_docx_sources = build_sources(
        [
            {
                "documentName": "Legacy_Policy.docx",
                "page": 4,
                "content": "The policy applies to permanent employees.",
                "score": 0.91,
                "semanticScore": 0.88,
                "evidenceSupported": True,
                "metadata": {
                    "filename": "Legacy_Policy.docx",
                    "document_type": "docx",
                    "page": 4,
                    "page_is_reliable": False,
                    "location_type": "paragraphs",
                    "chapter": "Eligibility",
                    "paragraph_start": 7,
                    "paragraph_end": 7,
                },
            }
        ],
        question="Who is eligible?",
    )
    assert unreliable_docx_sources
    assert unreliable_docx_sources[0]["page"] is None
    assert unreliable_docx_sources[0]["chapter"] == "Eligibility"
    assert unreliable_docx_sources[0]["paragraph_start"] == 7

    txt_sources = build_sources(
        [
            {
                "documentName": "FAQ_IT_Support.txt",
                "page": 99,
                "content": (
                    "Q: How do I reset my password? "
                    "A: Raise a ticket to the IT Helpdesk via the portal; "
                    "resets are processed within 1x24 hours."
                ),
                "score": 0.96,
                "semanticScore": 0.92,
                "evidenceSupported": True,
                "metadata": {
                    "filename": "FAQ_IT_Support.txt",
                    "document_type": "txt",
                    "page": 99,
                    "page_is_reliable": False,
                    "location_type": "paragraphs",
                    "chapter": "Account Recovery",
                    "paragraph_start": 11,
                    "paragraph_end": 20,
                },
            }
        ],
        question="Bagaimana prosedur reset password dan berapa lama prosesnya?",
    )
    assert txt_sources
    assert txt_sources[0]["page"] is None
    assert txt_sources[0]["page_is_reliable"] is False
    assert "chapter" not in txt_sources[0]
    assert "section" not in txt_sources[0]
    assert txt_sources[0]["paragraph_start"] == 11
    assert txt_sources[0]["paragraph_end"] == 20
    assert "IT Helpdesk" in txt_sources[0]["excerpt"]
    assert "1x24 hours" in txt_sources[0]["excerpt"]

    ordered_sources = build_sources(
        [
            {
                "documentName": "Second.pdf",
                "page": 2,
                "content": pdf_content,
                "score": 0.92,
                "semanticScore": 0.90,
                "evidenceSupported": True,
                "metadata": {
                    "filename": "Second.pdf",
                    "document_type": "pdf",
                    "page": 2,
                    "page_is_reliable": True,
                    "paragraph_start": 1,
                    "paragraph_end": 2,
                },
            },
            {
                "documentName": "First.pdf",
                "page": 1,
                "content": pdf_content,
                "score": 0.99,
                "semanticScore": 0.97,
                "evidenceSupported": True,
                "metadata": {
                    "filename": "First.pdf",
                    "document_type": "pdf",
                    "page": 1,
                    "page_is_reliable": True,
                    "paragraph_start": 3,
                    "paragraph_end": 4,
                },
            },
            {
                "documentName": "Third.pdf",
                "page": 3,
                "content": pdf_content,
                "score": 0.94,
                "semanticScore": 0.91,
                "evidenceSupported": True,
                "metadata": {
                    "filename": "Third.pdf",
                    "document_type": "pdf",
                    "page": 3,
                    "page_is_reliable": True,
                    "paragraph_start": 5,
                    "paragraph_end": 6,
                },
            },
        ],
        question=question,
        limit=5,
    )
    assert len(ordered_sources) == 3, "All three evidence-bearing sources should be returned within the configured cap."
    assert ordered_sources[0]["document_name"] == "First.pdf"
    assert ordered_sources[1]["document_name"] == "Third.pdf"
    assert ordered_sources[2]["document_name"] == "Second.pdf"
    assert (
        ordered_sources[0]["relevance_score"]
        >= ordered_sources[1]["relevance_score"]
        >= ordered_sources[2]["relevance_score"]
    )

    print("Source citation tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
