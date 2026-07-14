# LapisAI Retrieval Evaluation Report

Generated: `2026-07-12T18:24:49+00:00`

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
- answerability gate enabled: `True`
- answerability min top score: `0.4`
- answerability min evidence score: `0.5`
- answerability min score margin: `0.015`
- require supported evidence: `False`
- evaluated questions: `20`
- indexed corpus files: `50/50`

## Primary results: page-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.9333 |
| Hit Rate@1 | 93.33% |
| Precision@1 | 93.33% |
| Recall@1 | 86.67% |
| Hit Rate@3 | 93.33% |
| Precision@3 | 33.33% |
| Recall@3 | 90.00% |
| Hit Rate@5 | 93.33% |
| Precision@5 | 20.00% |
| Recall@5 | 90.00% |

## Supporting results: document-level retrieval

| Metric | Value |
|---|---:|
| MRR | 0.9333 |
| Hit Rate@1 | 93.33% |
| Precision@1 | 93.33% |
| Recall@1 | 86.67% |
| Hit Rate@3 | 93.33% |
| Precision@3 | 33.33% |
| Recall@3 | 90.00% |
| Hit Rate@5 | 93.33% |
| Precision@5 | 20.00% |
| Recall@5 | 90.00% |

## Language Performance

### Id Query
- Evaluated: `15`
- Page MRR: `0.9333`


## Unanswerable-question retrieval behaviour

- Questions: `5`
- Correctly rejected: `5`
- False positives: `0`
- No-result rate: `100.00%`
- Retrieval false-positive rate: `0.00%`
- False-positive IDs: `-`
- Mean top retrieval score: `0.0000`

## Interpretation note

Page-level metrics are the primary metrics because the project requires citations to the exact source page. Document-level metrics are included as supporting evidence. Unanswerable metrics only measure retrieval behaviour; final refusal quality must be assessed during answer-generation evaluation.
