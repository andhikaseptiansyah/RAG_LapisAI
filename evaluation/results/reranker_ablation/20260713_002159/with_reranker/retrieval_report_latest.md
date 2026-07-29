# LapisAI Retrieval Evaluation Report

Generated: `2026-07-12T17:26:34+00:00`

## Configuration

- Split: `development`
- k: `1, 3, 5`
- candidate_k: `20`
- minimum score: `0.3`
- reranker enabled: `True`
- reranker model: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- reranker candidates per retriever: `20`
- reranker weight: `0.65`
- evidence verification enabled: `True`
- evaluated questions: `40`
- indexed corpus files: `50/50`

## Primary results: page-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.9714 |
| Hit Rate@1 | 97.14% |
| Precision@1 | 97.14% |
| Recall@1 | 95.71% |
| Hit Rate@3 | 97.14% |
| Precision@3 | 32.38% |
| Recall@3 | 95.71% |
| Hit Rate@5 | 97.14% |
| Precision@5 | 19.43% |
| Recall@5 | 95.71% |

## Supporting results: document-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.9714 |
| Hit Rate@1 | 97.14% |
| Precision@1 | 97.14% |
| Recall@1 | 95.71% |
| Hit Rate@3 | 97.14% |
| Precision@3 | 32.38% |
| Recall@3 | 95.71% |
| Hit Rate@5 | 97.14% |
| Precision@5 | 19.43% |
| Recall@5 | 95.71% |

## Language Performance

### En Query
- Evaluated: `25`
- Page MRR: `0.9600`

### Id Query
- Evaluated: `10`
- Page MRR: `1.0000`


## Unanswerable-question retrieval behaviour

- Questions: `5`
- No-result rate: `100.00%`
- Retrieval false-positive rate: `0.00%`
- Mean top retrieval score: `0.0000`

## Interpretation note

Page-level metrics are the primary metrics because the project requires citations to the exact source page. Document-level metrics are included as supporting evidence. Unanswerable metrics only measure retrieval behaviour; final refusal quality must be assessed during answer-generation evaluation.
