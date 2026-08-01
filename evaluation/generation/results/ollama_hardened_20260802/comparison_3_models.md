# Comparison of 1 LLM Model (Bilingual Macro)

| Model | Model Name | Overall | Deterministic | Answer | Grounding | Retrieval | Safety | Status | P@K | R@K | Hit@K | MRR | NDCG@K | Token F1 | Faithfulness | Citation F1 | Hallucination | Avg generation ms | Estimated E2E ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ollama | qwen3-custom:latest | None | 85.67 | 64.97 | 94.45 | 99.36 | 98.15 | INCOMPLETE_MISSING_JUDGE | 0.2022 | 1.0 | 1.0 | 0.9889 | 0.9918 | 0.5558 | None | 0.94445 | None | 4368.0078 | 15372.560599999999 |

## Retrieval-context consistency

- Status: not applicable (only one model)
- Questions checked: 0
- Context mismatches across models: 0

## Composite score

The primary comparison uses a bilingual macro average, so English and Indonesian receive equal weight despite different question counts.

Overall score = 35% answer quality + 30% grounding + 20% retrieval + 15% safety. Latency is reported separately and does not increase the quality score.

If the LLM judge is skipped or fails, Overall is intentionally left empty and score_status is INCOMPLETE_MISSING_JUDGE; deterministic_score remains available for diagnostics.

## Language comparison

English and Indonesian scores are descriptive by-language slices, not a controlled language-gap test, because the question sets do not use equivalent source targets.
