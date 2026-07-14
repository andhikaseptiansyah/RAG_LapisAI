# LapisAI Retrieval Evaluation Report

Generated: `2026-07-10T18:16:00+00:00`

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
| MRR | 0.9571 |
| Hit Rate@1 | 94.29% |
| Precision@1 | 94.29% |
| Recall@1 | 94.29% |
| Hit Rate@3 | 97.14% |
| Precision@3 | 32.38% |
| Recall@3 | 97.14% |
| Hit Rate@5 | 97.14% |
| Precision@5 | 19.43% |
| Recall@5 | 97.14% |

## Supporting results: document-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.9571 |
| Hit Rate@1 | 94.29% |
| Precision@1 | 94.29% |
| Recall@1 | 94.29% |
| Hit Rate@3 | 97.14% |
| Precision@3 | 32.38% |
| Recall@3 | 97.14% |
| Hit Rate@5 | 97.14% |
| Precision@5 | 19.43% |
| Recall@5 | 97.14% |

## Unanswerable-question retrieval behaviour

- Questions: `5`
- No-result rate: `0.00%`
- Retrieval false-positive rate: `100.00%`
- Mean top retrieval score: `0.4159`

## Interpretation note

Page-level metrics are the primary metrics because the project requires citations to the exact source page. Document-level metrics are included as supporting evidence. Unanswerable metrics only measure retrieval behaviour; final refusal quality must be assessed during answer-generation evaluation.
