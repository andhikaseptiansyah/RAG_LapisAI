# Multilingual V4 Final

Build: `rag-multilingual-v4-20260723`

## Root cause fixed

1. The Indonesian query was rejected before generation, while the equivalent natural English sentence retrieved the SOP with a much stronger score.
2. Earlier bridge queries were long keyword lists. V4 retries retrieval with one concise natural English question only after the original query fails.
3. The SOP excerpt contains three durations: P1 acknowledgement in 15 minutes, P1 resolution in 4 hours, and P2 resolution in 8 hours. V4 selects a scalar using both the requested action and priority code, so the Indonesian P1 resolution question returns `4 jam.` rather than refusing or selecting another duration.
4. Legacy alternative routers and `python-service` were removed. The only active backend is `backend/api/main.py` with `routes_compat.py`.

No retrieval, evidence, answerability, answer-confidence, or source-confidence threshold was reduced.

## Start backend on Windows PowerShell

From the project root:

```powershell
cd backend
$env:PYTHONPATH = "."
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

The terminal must print:

```text
[BUILD] active_backend=rag-multilingual-v4-20260723
```

Verify the running build:

```text
http://127.0.0.1:8000/api/health
```

Expected field:

```json
{"buildVersion":"rag-multilingual-v4-20260723"}
```

Run the exact live regression test from the project root:

```powershell
python tools/verify_multilingual_v4.py --api-url http://127.0.0.1:8000 --username YOUR_USERNAME --password YOUR_PASSWORD
```

The verifier must report `PASS`, answer `4 jam`, source `SOP_IT_Incident_Handling.pdf`, and retrieval mode `natural_language_bridge` when the original Indonesian retrieval is rejected.
