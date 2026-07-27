# Real-Time Chat Progress

The chat interface now displays operational progress emitted by the active RAG pipeline. It does not rotate placeholder phrases or expose model chain-of-thought.

## Transport

The frontend sends chat requests to:

```text
POST /api/chat/stream
Accept: text/event-stream
```

The server returns Server-Sent Events over the same authenticated request:

- `ready`: the stream is connected.
- `progress`: one real pipeline stage changed state.
- `result`: the final chat response.
- `error`: the request failed or was cancelled.

The original `POST /api/chat` endpoint remains available for compatibility.

## Progress stages

Depending on the request and configuration, the backend can emit:

1. Question analysis and selected language/provider.
2. Semantic search.
3. BM25 keyword search.
4. Hybrid candidate union.
5. Initial answerability check.
6. Cross-encoder reranking.
7. Evidence validation for concepts, dates, numbers, and terms.
8. Final answerability check.
9. Bilingual retrieval fallback, only when it is actually used.
10. Context selection with document, page, paragraph, and confidence metadata.
11. Answer generation with the active provider.
12. Grounding validation or deterministic grounded fallback.
13. Citation preparation.

Document chunking and document embedding are not chat stages. They remain part of upload and reindex operations only.

## Lifecycle rules

- Pressing Stop aborts the browser stream, signals backend cancellation, and clears progress immediately.
- Losing network connectivity clears progress and cancels the active query.
- Progress is cleared before the final answer is rendered.
- A disconnected client sets the backend cancellation event.
- Progress payloads contain operational stage names, aggregate counts, source locations, and confidence values. They do not contain prompts, embeddings, hidden reasoning, or chain-of-thought.
