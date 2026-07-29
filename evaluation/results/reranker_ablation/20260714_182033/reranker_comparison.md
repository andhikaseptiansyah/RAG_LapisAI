# Reranker Ablation Comparison

- Dataset: `Nusantara Dynamics Official Ground Truth Q&A`
- Ground truth: `C:\Users\ANDIKA\Downloads\RAG_LapisAI\evaluation\ground_truth_qa.csv`
- Questions: `30`
- Primary retrieval level: `document`
- Candidate count per retriever: `20`
- Minimum final score: `0.3`
- Reranker model: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- Reranker weight: `0.25`

| Metric | Without reranker | With reranker | Delta |
|---|---:|---:|---:|
| mrr | 0.983333 | 1.000000 | +0.016667 |
| hit_at_1 | 0.966667 | 1.000000 | +0.033333 |
| hit_at_3 | 1.000000 | 1.000000 | +0.000000 |
| recall_at_5 | 1.000000 | 1.000000 | +0.000000 |
| mean_latency_ms | 1126.265000 | 2326.592000 | +1200.327000 |

False-positive retrieval was not evaluated because the official CSV contains no unanswerable questions.

A positive delta is desirable for MRR, Hit@1, Hit@3, and Recall@5. Latency should be reported separately and not hidden.
