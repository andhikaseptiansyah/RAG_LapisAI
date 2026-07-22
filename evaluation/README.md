# LapisAI Evaluation Suite

This directory contains the verified ground-truth Q&A dataset and retrieval-quality evaluation for the **Enterprise Knowledge Assistant (RAG)** project.

## Files

| File | Purpose |
|---|---|
| `ground_truth.json` | Canonical machine-readable ground-truth dataset |
| `ground_truth.csv` | Spreadsheet-friendly dataset copy |
| `ground_truth.schema.json` | JSON Schema for dataset structure |
| `validate_ground_truth.py` | Validates structure, references, excerpts, and corpus coverage |
| `evaluate_retrieval.py` | Evaluates hybrid retrieval, reranking, and evidence filtering |
| `run_retrieval_evaluation.ps1` | Windows PowerShell launcher |
| `test_retrieval_metrics.py` | Tests metric calculations |
| `test_retrieval_improvements.py` | Tests bilingual expansion and negative-evidence rejection |
| `test_evidence_ground_truth.py` | Checks all 50 answerable source pages against evidence verification |
| `test_source_citations.py` | Verifies excerpts and PDF/DOCX/TXT location rules |
| `test_reranker_pipeline.py` | Verifies real cross-encoder ordering and the full 20+20 candidate union |
| `run_reranker_ablation.py` | Runs with/without-reranker evaluations and writes a comparison report |
| `results/` | Generated JSON, CSV, and Markdown reports |

## Dataset composition

- 60 total questions
- 50 answerable questions covering all 50 enterprise documents
- 10 deliberately unanswerable questions
- 40 development questions
- 20 fixed test questions
- 45 English questions
- 15 Indonesian questions

Personal CVs, cover letters, and web-development progress reports are excluded from the evaluation corpus.

## Split rule

Use `development` while adjusting retrieval weights, thresholds, expansion, reranking, or evidence verification. Use `test` only for final reporting. Repeatedly tuning against the test split converts it into a development set wearing a more impressive label.

## Metrics

The evaluator reports:

- Hit Rate@1, @3, and @5
- Precision@1, @3, and @5
- Recall@1, @3, and @5
- Mean Reciprocal Rank
- unanswerable no-result rate
- unanswerable retrieval false-positive rate

Page-level retrieval is primary because the project requires citation to the exact source page. Document-level results are supporting metrics.

## First-time setup

From the project root:

```powershell
python -m pip install -r .\backend\requirements.txt
```

The first run may download the embedding and cross-encoder models.

## Validate the ground truth

```powershell
python .\evaluation\validate_ground_truth.py
```

Expected final line:

```text
Validation passed.
```

## Run tests

```powershell
python .\evaluation\test_retrieval_metrics.py
python .\evaluation\test_retrieval_improvements.py
python .\evaluation\test_evidence_ground_truth.py
```

Expected final lines:

```text
Retrieval metric tests passed.
Retrieval improvement tests passed.
Evidence verifier accepted all 50 answerable ground-truth source pages.
Source citation tests passed.
Reranker pipeline tests passed.
```

## Development evaluation

```powershell
python .\evaluation\evaluate_retrieval.py --split development
```

If the ChromaDB collection is empty:

```powershell
python .\evaluation\evaluate_retrieval.py --split development --index-missing
```

The default configuration is:

| Option | Default |
|---|---:|
| `--split` | `development` |
| `--k` | `1,3,5` |
| `--candidate-k` | `20` |
| `--min-score` | `0.30` |
| reranker | enabled |
| reranker model | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| semantic candidates | 20 |
| BM25 candidates | 20 |
| final top-k | 5 |
| evidence verification | enabled |

## PowerShell launcher

```powershell
.\evaluation\run_retrieval_evaluation.ps1
```

Install dependencies through the launcher:

```powershell
.\evaluation\run_retrieval_evaluation.ps1 -InstallDependencies
```

Final test run:

```powershell
.\evaluation\run_retrieval_evaluation.ps1 -Split test
```

## Ablation evaluation

Disable the reranker while retaining evidence verification:

```powershell
python .\evaluation\evaluate_retrieval.py --split development --no-reranker
```

Disable evidence verification while retaining reranking:

```powershell
python .\evaluation\evaluate_retrieval.py --split development --no-evidence-verification
```

Automated ablation comparison:

```powershell
.\evaluation\run_reranker_ablation.ps1 -Split development
```

After tuning is complete, run the fixed test split once:

```powershell
.\evaluation\run_reranker_ablation.ps1 -Split test
```

These runs show whether reranking actually improves MRR/Hit@1/Recall and how much latency it adds, instead of crediting the whole pipeline through sheer optimism.

## Generated output

```text
evaluation/results/
├── retrieval_summary_<split>_<timestamp>.json
├── retrieval_results_<split>_<timestamp>.csv
├── retrieval_report_<split>_<timestamp>.md
├── retrieval_summary_latest.json
├── retrieval_results_latest.csv
└── retrieval_report_latest.md
```

The CSV includes:

- base hybrid score,
- reranker applied flag,
- reranker rank,
- reranker raw logit,
- reranker normalized score,
- evidence score,
- evidence-supported status,
- missing concepts,
- hard evidence failures,
- expected and retrieved documents/pages.

## Citation location convention

User-facing citations follow these rules:

- PDF: physical PDF page from PyMuPDF, starting at page 1.
- DOCX: exact non-empty paragraph range, for example `Paragraphs 11–20`; no physical page is claimed.
- TXT: exact source-line range, for example `Lines 51–100`; no physical page is claimed.

DOCX/TXT still use internal logical groups for chunk IDs and retrieval evaluation, but those internal group numbers are deliberately removed from the citation API and UI. Every source also stores a short verbatim `excerpt` selected from the retrieved chunk.

## Bilingual 3-model final evaluation

The final Project-1 comparison now uses 100 questions: 50 English and 50 Indonesian, including 10 deliberately unanswerable questions. See:

```text
evaluation/EVALUATION_3_MODELS.md
```

Validate the dataset:

```powershell
python .\evaluation\generation\run_three_model_evaluation.py --validate-only
```

Run Ollama, Gemini, and Groq with the same evaluation settings:

```powershell
python .\evaluation\generation\run_three_model_evaluation.py
```
