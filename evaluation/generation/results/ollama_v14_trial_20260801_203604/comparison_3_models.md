# Comparison of 1 LLM Model (Bilingual Macro)

| Model | Model Name | Overall | Deterministic | Answer | Grounding | Retrieval | Safety | Status | P@K | R@K | Hit@K | MRR | NDCG@K | Token F1 | Faithfulness | Citation F1 | Hallucination | Avg ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ollama | qwen3-custom:latest | None | 82.94 | 66.26 | 85.19 | 99.03 | 95.93 | INCOMPLETE_MISSING_JUDGE | 0.2 | 1.0 | 1.0 | 0.98335 | 0.9877 | 0.5363 | None | 0.85185 | None | 4811.4985 |

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
