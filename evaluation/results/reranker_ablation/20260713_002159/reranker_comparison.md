# Reranker Ablation Comparison

- Split: `development`
- Candidate count per retriever: `20`
- Minimum final score: `0.3`

| Metric | Without reranker | With reranker | Delta |
|---|---:|---:|---:|
| page_mrr | 0.985714 | 0.971429 | -0.014285 |
| page_hit_at_1 | 0.971429 | 0.971429 | +0.000000 |
| page_recall_at_5 | 0.985714 | 0.957143 | -0.028571 |
| false_positive_rate | 0.200000 | 0.000000 | -0.200000 |
| mean_latency_ms | 136.015000 | 1224.536000 | +1088.521000 |

A positive delta is desirable for MRR, Hit@1, and Recall@5. A negative delta is desirable for false-positive rate. Latency is expected to increase and should be reported rather than hidden.
