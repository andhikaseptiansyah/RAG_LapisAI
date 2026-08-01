# Comparison of 1 LLM Model (Bilingual Macro)

| Model | Model Name | Overall | Deterministic | Answer | Grounding | Retrieval | Safety | Status | P@K | R@K | Hit@K | MRR | NDCG@K | Token F1 | Faithfulness | Citation F1 | Hallucination | Avg ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ollama | qwen3-custom:latest | None | 85.08 | 67.92 | 89.63 | 99.03 | 97.41 | INCOMPLETE_MISSING_JUDGE | 0.2 | 1.0 | 1.0 | 0.98335 | 0.9877 | 0.5621 | None | 0.8963 | None | 4774.2970000000005 |

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
