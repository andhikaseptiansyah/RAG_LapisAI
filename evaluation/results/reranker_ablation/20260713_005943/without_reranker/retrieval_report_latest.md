# LapisAI Retrieval Evaluation Report

Generated: `2026-07-12T18:00:33+00:00`

## Configuration

- Split: `test`
- k: `1, 3, 5`
- candidate_k: `20`
- minimum score: `0.3`
- reranker enabled: `False`
- reranker model: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- reranker candidates per retriever: `20`
- reranker weight: `0.25`
- evidence verification enabled: `True`
- evaluated questions: `20`
- indexed corpus files: `50/50`

## Primary results: page-level retrieval

| Metric | Value |
|---|---:|
| MRR | 1.0000 |
| Hit Rate@1 | 100.00% |
| Precision@1 | 100.00% |
| Recall@1 | 93.33% |
| Hit Rate@3 | 100.00% |
| Precision@3 | 35.56% |
| Recall@3 | 96.67% |
| Hit Rate@5 | 100.00% |
| Precision@5 | 21.33% |
| Recall@5 | 96.67% |

## Supporting results: document-level retrieval

| Metric | Value |
|---|---:|
| MRR | 1.0000 |
| Hit Rate@1 | 100.00% |
| Precision@1 | 100.00% |
| Recall@1 | 93.33% |
| Hit Rate@3 | 100.00% |
| Precision@3 | 35.56% |
| Recall@3 | 96.67% |
| Hit Rate@5 | 100.00% |
| Precision@5 | 21.33% |
| Recall@5 | 96.67% |

## Language Performance

### Id Query
- Evaluated: `15`
- Page MRR: `1.0000`


## Unanswerable-question retrieval behaviour

- Questions: `5`
- No-result rate: `0.00%`
- Retrieval false-positive rate: `100.00%`
- Mean top retrieval score: `0.6187`

## Interpretation note

Page-level metrics are the primary metrics because the project requires citations to the exact source page. Document-level metrics are included as supporting evidence. Unanswerable metrics only measure retrieval behaviour; final refusal quality must be assessed during answer-generation evaluation.
