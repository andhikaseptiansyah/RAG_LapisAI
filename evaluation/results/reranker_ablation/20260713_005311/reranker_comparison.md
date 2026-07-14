# Reranker Ablation Comparison

- Split: `development`
- Candidate count per retriever: `20`
- Minimum final score: `0.3`
- Reranker model: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- Reranker weight: `0.25`
- Ranking strategy: `blended hybrid + cross-encoder`

| Metric | Without reranker | With reranker | Delta |
|---|---:|---:|---:|
| page_mrr | 0.985714 | 1.000000 | +0.014286 |
| page_hit_at_1 | 0.971429 | 1.000000 | +0.028571 |
| page_recall_at_5 | 0.985714 | 0.985714 | +0.000000 |
| false_positive_rate | 0.200000 | 0.200000 | +0.000000 |
| mean_latency_ms | 261.034000 | 1143.415000 | +882.381000 |

A positive delta is desirable for MRR, Hit@1, and Recall@5. A negative delta is desirable for false-positive rate. Latency is expected to increase and should be reported rather than hidden.
