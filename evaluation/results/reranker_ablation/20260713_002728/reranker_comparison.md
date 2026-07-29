# Reranker Ablation Comparison

- Split: `test`
- Candidate count per retriever: `20`
- Minimum final score: `0.3`

| Metric | Without reranker | With reranker | Delta |
|---|---:|---:|---:|
| page_mrr | 1.000000 | 0.855556 | -0.144444 |
| page_hit_at_1 | 1.000000 | 0.800000 | -0.200000 |
| page_recall_at_5 | 0.966667 | 0.866667 | -0.100000 |
| false_positive_rate | 1.000000 | 0.400000 | -0.600000 |
| mean_latency_ms | 273.287000 | 1317.494000 | +1044.207000 |

A positive delta is desirable for MRR, Hit@1, and Recall@5. A negative delta is desirable for false-positive rate. Latency is expected to increase and should be reported rather than hidden.
