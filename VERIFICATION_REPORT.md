# Verification Report

## Passed locally

- TypeScript type-check and Vite production build: passed.
- Python syntax compilation: passed.
- `test_source_citations.py`: passed.
- `test_reranker_pipeline.py`: passed.
- `test_retrieval_metrics.py`: passed.
- `test_retrieval_improvements.py`: passed.
- `test_evidence_ground_truth.py`: passed without hard-rejecting answerable source sets.
- `test_indonesian_answer_gate.py`: passed with `FAQ_IT_Support.txt` as the source.

## Full reranker ablation

The automated development/test ablation scripts are included, but a live run was
not completed in the packaging environment because the Hugging Face model files
could not be downloaded there. Run this on the development machine after the
embedding and cross-encoder models are available:

```powershell
.\evaluation\run_reranker_ablation.ps1 -Split development
.\evaluation\run_reranker_ablation.ps1 -Split test
```

Do not reuse older retrieval scores as evidence for the new reranker. The new
reports must be generated from the updated code and the active ChromaDB index.
