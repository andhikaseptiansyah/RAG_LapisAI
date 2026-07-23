# Multilingual RAG Fix, 23 July 2026

## Problem

English questions could be answered, while equivalent Indonesian questions were often rejected before generation even though the indexed evidence was relevant.

## Root causes

1. The hybrid score always applied the fixed `68% semantic + 32% BM25` sum. When an Indonesian query searched an English document, BM25 frequently returned zero. The valid multilingual semantic score was therefore multiplied by `0.68` and could fall below the existing answerability gate.
2. Evidence verification relied heavily on literal token overlap for topics outside the manually defined concept dictionary. This made valid cross-language evidence appear unsupported.
3. Evidence excerpt selection could choose an arbitrary sentence when the question and source used different languages.
4. A local LLM that copied the source language could be rejected, then the verbatim extractive fallback could also be rejected because it remained in the source language.
5. Very short wrong-language answers such as `Two days per week.` could be treated as language-neutral.

## Changes

- Added `backend/retrieval/scoring.py` to normalize hybrid weights over relevance signals that are actually available.
- Preserved the original `68/32` blend when semantic and BM25 signals are both positive.
- Added the existing multilingual semantic score as a language-independent evidence signal.
- Kept hard concept conflicts, numeric constraints, evidence verification, and answerability checks active.
- Extended duration recognition to written English and Indonesian numbers.
- Kept compact cross-language chunks intact when literal sentence overlap is too weak for reliable excerpt selection.
- Added one minimal-evidence language retry before the extractive fallback.
- Strengthened output-language checking for short answers while retaining neutral values such as `50 GB` and `PostgreSQL 16`.
- Moved the ChromaDB import inside collection functions so unit tests that do not access the vector store can run without initializing ChromaDB.

## Thresholds

No retrieval or answer threshold was lowered. The following defaults remain unchanged:

```env
MIN_RESULT_SCORE=0.24
MIN_EVIDENCE_SCORE=0.58
ANSWERABILITY_MIN_TOP_SCORE=0.50
ANSWERABILITY_MIN_BASE_SCORE=0.30
MIN_ANSWER_CONFIDENCE=0.40
MIN_SOURCE_CONFIDENCE=0.30
```

## Reindex requirement

No reindex is required for this patch because the embedding model and vector collection are unchanged. Restart the backend so the Python modules are reloaded.

## Validation

Targeted multilingual and language tests:

```text
24 passed, 4 subtests passed
```

Full backend and evaluation suite:

```text
108 passed, 4 subtests passed, 1 unrelated pre-existing failure
```

The unrelated failure is `test_legacy_router_modules_are_removed`, because the uploaded package still contains legacy `backend/api/routes_admin.py`, `backend/api/routes_chat.py`, and `python-service/`. The active application uses only `routes_compat.py`; these legacy files were not removed as part of the multilingual fix.

Frontend build could not be completed in the validation environment because the npm package registry returned HTTP 503 while installing dependencies. No frontend source file was changed by this patch.
