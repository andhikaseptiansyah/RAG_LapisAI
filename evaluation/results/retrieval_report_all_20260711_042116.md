# LapisAI Retrieval Evaluation Report

Generated: `2026-07-10T21:21:16+00:00`

## Configuration

- Split: `all`
- k: `1, 3, 5`
- candidate_k: `10`
- minimum score: `0.5`
- reranker enabled: `True`
- evidence verification enabled: `True`
- evaluated questions: `60`
- indexed corpus files: `50/50`

## Primary results: page-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.9600 |
| Hit Rate@1 | 96.00% |
| Precision@1 | 96.00% |
| Recall@1 | 93.00% |
| Hit Rate@3 | 96.00% |
| Precision@3 | 32.00% |
| Recall@3 | 93.00% |
| Hit Rate@5 | 96.00% |
| Precision@5 | 19.20% |
| Recall@5 | 93.00% |

## Supporting results: document-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.9600 |
| Hit Rate@1 | 96.00% |
| Precision@1 | 96.00% |
| Recall@1 | 93.00% |
| Hit Rate@3 | 96.00% |
| Precision@3 | 32.00% |
| Recall@3 | 93.00% |
| Hit Rate@5 | 96.00% |
| Precision@5 | 19.20% |
| Recall@5 | 93.00% |

## Language Performance

### En Query
- Evaluated: `25`
- Page MRR: `0.9600`

### Id Query
- Evaluated: `25`
- Page MRR: `0.9600`


## Unanswerable-question retrieval behaviour

- Questions: `10`
- No-result rate: `90.00%`
- Retrieval false-positive rate: `10.00%`
- Mean top retrieval score: `0.0575`

## Interpretation note

Page-level metrics are the primary metrics because the project requires citations to the exact source page. Document-level metrics are included as supporting evidence. Unanswerable metrics only measure retrieval behaviour; final refusal quality must be assessed during answer-generation evaluation.
