# Language, Upload, and Admin UI Hotfix

This package addresses the issues reported after the previous patch.

## Changes

- The response language now follows the explicit UI choice. `ID` always requests Bahasa Indonesia and `EN` always requests English. Automatic detection is used only for `AUTO` or an omitted language.
- Every LLM provider receives a mandatory language instruction. A wrong-language response triggers one language-repair request. A response that still uses the wrong language is rejected instead of being displayed.
- The original Admin Upload layout has been restored, including the repository and queue workflow.
- Duplicate uploads no longer end at a generic HTTP 409 banner. The client checks filename conflicts before upload and opens a replace-confirmation dialog. A server-side 409 also reopens the same dialog.
- Confirmed replacements are sent through `replaceFilenamesJson`, including stale files that exist on disk but are missing from document metadata.
- The invalid HTML username pattern was replaced with a pattern that is valid under the browser `v` regular-expression mode.
- Admin-facing pages, labels, dialogs, loading states, and error messages use English.

## Required restart

After replacing the project files, stop both development servers and start them again. A running backend or Vite process does not automatically load all Python and routing changes.

Backend example:

```bash
cd backend
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend example:

```bash
npm install
npm run dev
```

If the browser still shows an older interface, perform a hard reload and clear the Vite cache if necessary.

## Validation performed

- Python `compileall`: passed.
- Backend unit suite: 14 tests passed.
- TypeScript/TSX syntax parsing: 39 files passed.
- Full Vite build and live indexing were not executed in this environment because Node dependencies, ChromaDB, embedding models, reranker models, and external LLM services were unavailable.
