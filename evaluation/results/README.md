# Retrieval Evaluation Results

This directory is populated by `evaluation/evaluate_retrieval.py`.

Each run generates:

- `retrieval_summary_<split>_<timestamp>.json`: overall and grouped metrics
- `retrieval_results_<split>_<timestamp>.csv`: per-question retrieval details
- `retrieval_report_<split>_<timestamp>.md`: concise report for documentation
- matching `*_latest.*` files containing the most recent run

No metric values are included in the repository before the evaluator is run against the local ChromaDB index.
