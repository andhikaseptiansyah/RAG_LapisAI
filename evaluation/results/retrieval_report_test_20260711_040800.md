# LapisAI Retrieval Evaluation Report

Generated: `2026-07-10T21:08:00+00:00`

## Configuration

- Split: `test`
- k: `1, 3, 5`
- candidate_k: `10`
- minimum score: `0.5`
- reranker enabled: `True`
- evidence verification enabled: `True`
- evaluated questions: `20`
- indexed corpus files: `50/50`

## Primary results: page-level retrieval

| Metric | Value |
|---|---:|
| MRR | 1.0000 |
| Hit Rate@1 | 100.00% |
| Precision@1 | 100.00% |
| Recall@1 | 100.00% |
| Hit Rate@3 | 100.00% |
| Precision@3 | 33.33% |
| Recall@3 | 100.00% |
| Hit Rate@5 | 100.00% |
| Precision@5 | 20.00% |
| Recall@5 | 100.00% |

## Supporting results: document-level retrieval

| Metric | Value |
|---|---:|
| MRR | 1.0000 |
| Hit Rate@1 | 100.00% |
| Precision@1 | 100.00% |
| Recall@1 | 100.00% |
| Hit Rate@3 | 100.00% |
| Precision@3 | 33.33% |
| Recall@3 | 100.00% |
| Hit Rate@5 | 100.00% |
| Precision@5 | 20.00% |
| Recall@5 | 100.00% |

## Language Performance

### En Query
- Evaluated: `12`
- Page MRR: `1.0000`

### Id Query
- Evaluated: `3`
- Page MRR: `1.0000`


## Unanswerable-question retrieval behaviour

- Questions: `5`
- No-result rate: `100.00%`
- Retrieval false-positive rate: `0.00%`
- Mean top retrieval score: `0.0000`

## Interpretation note

Page-level metrics are the primary metrics because the project requires citations to the exact source page. Document-level metrics are included as supporting evidence. Unanswerable metrics only measure retrieval behaviour; final refusal quality must be assessed during answer-generation evaluation.
