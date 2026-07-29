# Installation — P1 Citation & Cross-Encoder Reranker

## Replace an existing project

Copy the patch files over the project root, preserving their directory paths.
Then install/update dependencies and restart the backend:

```powershell
pip install -r backend\requirements.txt
$env:PYTHONPATH = "backend"
uvicorn api.main:app --reload
```

The new reranker model is downloaded on first use:

```text
cross-encoder/ms-marco-MiniLM-L-6-v2
```

Reindexing is not required solely for this patch because the embedding model and
chunk metadata format are unchanged. Reindex only when ChromaDB is empty or the
existing index is incomplete:

```powershell
$env:PYTHONPATH = "backend"
python backend\scripts\reindex_corpus.py
```

## Tests

```powershell
$env:PYTHONPATH = "backend"
python evaluation\test_source_citations.py
python evaluation\test_reranker_pipeline.py
python evaluation\test_retrieval_metrics.py
python evaluation\test_retrieval_improvements.py
python evaluation\test_evidence_ground_truth.py
```

## Reranker evaluation

```powershell
.\evaluation\run_reranker_ablation.ps1 -Split development
```

After configuration is frozen:

```powershell
.\evaluation\run_reranker_ablation.ps1 -Split test
```
