# LapisAI Retrieval Evaluation Report

Generated: `2026-07-10T17:52:30+00:00`

## Configuration

- Split: `all`
- k: `1, 3, 5`
- candidate_k: `20`
- minimum score: `0.22`
- evaluated questions: `60`
- indexed corpus files: `50/50`

## Primary results: page-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.9000 |
| Hit Rate@1 | 90.00% |
| Precision@1 | 90.00% |
| Recall@1 | 90.00% |
| Hit Rate@3 | 90.00% |
| Precision@3 | 30.00% |
| Recall@3 | 90.00% |
| Hit Rate@5 | 90.00% |
| Precision@5 | 18.00% |
| Recall@5 | 90.00% |

## Supporting results: document-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.9000 |
| Hit Rate@1 | 90.00% |
| Precision@1 | 90.00% |
| Recall@1 | 90.00% |
| Hit Rate@3 | 90.00% |
| Precision@3 | 30.00% |
| Recall@3 | 90.00% |
| Hit Rate@5 | 90.00% |
| Precision@5 | 18.00% |
| Recall@5 | 90.00% |

## Unanswerable-question retrieval behaviour

- Questions: `10`
- No-result rate: `10.00%`
- Retrieval false-positive rate: `90.00%`
- Mean top retrieval score: `0.4318`

## Interpretation note

Page-level metrics are the primary metrics because the project requires citations to the exact source page. Document-level metrics are included as supporting evidence. Unanswerable metrics only measure retrieval behaviour; final refusal quality must be assessed during answer-generation evaluation.
