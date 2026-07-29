# LapisAI Retrieval Evaluation Report

Generated: `2026-07-10T17:50:51+00:00`

## Configuration

- Split: `test`
- k: `1, 3, 5`
- candidate_k: `20`
- minimum score: `0.22`
- evaluated questions: `20`
- indexed corpus files: `50/50`

## Primary results: page-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.9333 |
| Hit Rate@1 | 93.33% |
| Precision@1 | 93.33% |
| Recall@1 | 93.33% |
| Hit Rate@3 | 93.33% |
| Precision@3 | 31.11% |
| Recall@3 | 93.33% |
| Hit Rate@5 | 93.33% |
| Precision@5 | 18.67% |
| Recall@5 | 93.33% |

## Supporting results: document-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.9333 |
| Hit Rate@1 | 93.33% |
| Precision@1 | 93.33% |
| Recall@1 | 93.33% |
| Hit Rate@3 | 93.33% |
| Precision@3 | 31.11% |
| Recall@3 | 93.33% |
| Hit Rate@5 | 93.33% |
| Precision@5 | 18.67% |
| Recall@5 | 93.33% |

## Unanswerable-question retrieval behaviour

- Questions: `5`
- No-result rate: `0.00%`
- Retrieval false-positive rate: `100.00%`
- Mean top retrieval score: `0.5418`

## Interpretation note

Page-level metrics are the primary metrics because the project requires citations to the exact source page. Document-level metrics are included as supporting evidence. Unanswerable metrics only measure retrieval behaviour; final refusal quality must be assessed during answer-generation evaluation.
