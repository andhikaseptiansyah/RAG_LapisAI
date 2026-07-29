# LapisAI Retrieval Evaluation Report

Generated: `2026-07-10T17:56:32+00:00`

## Configuration

- Split: `development`
- k: `1, 3, 5`
- candidate_k: `20`
- minimum score: `0.22`
- evaluated questions: `40`
- indexed corpus files: `50/50`

## Primary results: page-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.8857 |
| Hit Rate@1 | 88.57% |
| Precision@1 | 88.57% |
| Recall@1 | 88.57% |
| Hit Rate@3 | 88.57% |
| Precision@3 | 29.52% |
| Recall@3 | 88.57% |
| Hit Rate@5 | 88.57% |
| Precision@5 | 17.71% |
| Recall@5 | 88.57% |

## Supporting results: document-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.8857 |
| Hit Rate@1 | 88.57% |
| Precision@1 | 88.57% |
| Recall@1 | 88.57% |
| Hit Rate@3 | 88.57% |
| Precision@3 | 29.52% |
| Recall@3 | 88.57% |
| Hit Rate@5 | 88.57% |
| Precision@5 | 17.71% |
| Recall@5 | 88.57% |

## Unanswerable-question retrieval behaviour

- Questions: `5`
- No-result rate: `20.00%`
- Retrieval false-positive rate: `80.00%`
- Mean top retrieval score: `0.3218`

## Interpretation note

Page-level metrics are the primary metrics because the project requires citations to the exact source page. Document-level metrics are included as supporting evidence. Unanswerable metrics only measure retrieval behaviour; final refusal quality must be assessed during answer-generation evaluation.
