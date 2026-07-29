# Reranker Ablation Comparison

- Split: `test`
- Candidate count per retriever: `20`
- Minimum final score: `0.3`
- Reranker model: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- Reranker weight: `0.25`
- Ranking strategy: `blended hybrid + cross-encoder`

| Metric | Without reranker | With reranker | Delta |
|---|---:|---:|---:|
| page_mrr | 0.933333 | 1.000000 | +0.066667 |
| page_hit_at_1 | 0.933333 | 1.000000 | +0.066667 |
| page_recall_at_5 | 0.900000 | 0.966667 | +0.066667 |
| false_positive_rate | 0.000000 | 0.200000 | +0.200000 |
| mean_latency_ms | 293.888000 | 1355.304000 | +1061.416000 |

## Unanswerable absolute counts

- Total unanswerable questions: `5`
- Without reranker — correctly rejected: `5`, false positives: `0`
- With reranker — correctly rejected: `4`, false positives: `1`

A positive delta is desirable for MRR, Hit@1, and Recall@5. A negative delta is desirable for false-positive rate. Latency is expected to increase and should be reported rather than hidden.
