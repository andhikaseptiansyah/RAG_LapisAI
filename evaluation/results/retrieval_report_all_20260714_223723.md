# LapisAI Retrieval Evaluation Report

Generated: `2026-07-14T15:37:23+00:00`

## Dataset

- Name: `Nusantara Dynamics Official Ground Truth Q&A`
- Version: `csv-official-30`
- Source format: `csv`
- Ground truth: `C:\Users\ANDIKA\Downloads\RAG_LapisAI\evaluation\ground_truth_qa.csv`
- Questions: `30`
- Answerable: `30`
- Unanswerable: `0`
- Indexed corpus files: `50/50`

## Configuration

- Split: `all`
- k: `1, 3, 5`
- candidate_k per retriever: `20`
- minimum final score: `0.24`
- reranker enabled: `True`
- reranker model: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- reranker weight: `0.25`
- evidence verification enabled: `True`
- answerability gate enabled: `True`

## Primary results: document-level retrieval

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

## Page-level retrieval

Not evaluated because `ground_truth_qa.csv` provides `source_document` but no source-page labels.

## Language performance

- `en`: questions `30`, document MRR `1.0000`

## Unanswerable-question evaluation

Not evaluated because the official CSV contains only answerable questions.

## Interpretation note

The official CSV labels one expected source document for each question. Therefore document-level MRR, Hit@k, Precision@k, and Recall@k are the valid primary retrieval metrics. Page-level and unanswerable metrics must not be inferred from missing labels.
