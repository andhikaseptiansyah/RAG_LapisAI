# P1 Citation and Reranker Implementation

## Citation contract

Every answer source now contains:

```json
{
  "document_name": "SOP_Onboarding.pdf",
  "page": 5,
  "excerpt": "New employees serve a probation period of 3 months. A formal performance evaluation is conducted in week 12 before confirmation.",
  "score": 0.91
}
```

Location rules:

- PDF: physical page from the PDF parser.
- DOCX: `paragraph_start` and `paragraph_end`; `page` is `null` in the public citation.
- TXT: `line_start` and `line_end`; `page` is `null` in the public citation.

The excerpt is copied from the retrieved chunk, not rewritten by the LLM. It is capped by `SOURCE_EXCERPT_MAX_CHARS` and stored in conversation history and query logs.

## Reranker flow

```text
Semantic top 20 ----┐
                    ├─ unique union (up to 40 chunks)
BM25 top 20 --------┘
                    ↓
cross-encoder/ms-marco-MiniLM-L-6-v2
                    ↓
evidence verification / contradiction rejection
                    ↓
final score threshold
                    ↓
top 5
```

The union is not truncated before cross-encoder scoring. `rerankerRawScore`, `rerankerScore`, `rerankerRank`, and `rerankerApplied` are included in retrieval results and evaluation output.

## Required evaluation

```powershell
python .\evaluation\test_source_citations.py
python .\evaluation\test_reranker_pipeline.py
.\evaluation\run_reranker_ablation.ps1 -Split development
.\evaluation\run_reranker_ablation.ps1 -Split test
```

Use the development split for tuning. Use the test split once after configuration is frozen.
