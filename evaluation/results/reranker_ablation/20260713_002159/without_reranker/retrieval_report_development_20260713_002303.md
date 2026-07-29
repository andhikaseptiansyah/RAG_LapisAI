# LapisAI Retrieval Evaluation Report

Generated: `2026-07-12T17:23:03+00:00`

## Configuration

- Split: `development`
- k: `1, 3, 5`
- candidate_k: `20`
- minimum score: `0.3`
- reranker enabled: `False`
- reranker model: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- reranker candidates per retriever: `20`
- reranker weight: `0.65`
- evidence verification enabled: `True`
- evaluated questions: `40`
- indexed corpus files: `50/50`

## Primary results: page-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.9857 |
| Hit Rate@1 | 97.14% |
| Precision@1 | 97.14% |
| Recall@1 | 95.71% |
| Hit Rate@3 | 100.00% |
| Precision@3 | 33.33% |
| Recall@3 | 98.57% |
| Hit Rate@5 | 100.00% |
| Precision@5 | 20.00% |
| Recall@5 | 98.57% |

## Supporting results: document-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.9857 |
| Hit Rate@1 | 97.14% |
| Precision@1 | 97.14% |
| Recall@1 | 95.71% |
| Hit Rate@3 | 100.00% |
| Precision@3 | 33.33% |
| Recall@3 | 98.57% |
| Hit Rate@5 | 100.00% |
| Precision@5 | 20.00% |
| Recall@5 | 98.57% |

## Language Performance

### En Query
- Evaluated: `25`
- Page MRR: `0.9800`

### Id Query
- Evaluated: `10`
- Page MRR: `1.0000`


## Unanswerable-question retrieval behaviour

- Questions: `5`
- No-result rate: `80.00%`
- Retrieval false-positive rate: `20.00%`
- Mean top retrieval score: `0.0962`

## Interpretation note

Page-level metrics are the primary metrics because the project requires citations to the exact source page. Document-level metrics are included as supporting evidence. Unanswerable metrics only measure retrieval behaviour; final refusal quality must be assessed during answer-generation evaluation.
