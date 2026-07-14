# LapisAI Retrieval Evaluation Report

Generated: `2026-07-12T17:30:35+00:00`

## Configuration

- Split: `test`
- k: `1, 3, 5`
- candidate_k: `20`
- minimum score: `0.3`
- reranker enabled: `True`
- reranker model: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- reranker candidates per retriever: `20`
- reranker weight: `0.65`
- evidence verification enabled: `True`
- evaluated questions: `20`
- indexed corpus files: `50/50`

## Primary results: page-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.8556 |
| Hit Rate@1 | 80.00% |
| Precision@1 | 80.00% |
| Recall@1 | 73.33% |
| Hit Rate@3 | 93.33% |
| Precision@3 | 31.11% |
| Recall@3 | 86.67% |
| Hit Rate@5 | 93.33% |
| Precision@5 | 18.67% |
| Recall@5 | 86.67% |

## Supporting results: document-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.8556 |
| Hit Rate@1 | 80.00% |
| Precision@1 | 80.00% |
| Recall@1 | 73.33% |
| Hit Rate@3 | 93.33% |
| Precision@3 | 31.11% |
| Recall@3 | 86.67% |
| Hit Rate@5 | 93.33% |
| Precision@5 | 18.67% |
| Recall@5 | 86.67% |

## Language Performance

### Id Query
- Evaluated: `15`
- Page MRR: `0.8556`


## Unanswerable-question retrieval behaviour

- Questions: `5`
- No-result rate: `60.00%`
- Retrieval false-positive rate: `40.00%`
- Mean top retrieval score: `0.1541`

## Interpretation note

Page-level metrics are the primary metrics because the project requires citations to the exact source page. Document-level metrics are included as supporting evidence. Unanswerable metrics only measure retrieval behaviour; final refusal quality must be assessed during answer-generation evaluation.
