# Comparison of 2 LLM Models (Bilingual Macro)

> Report status: **DIAGNOSTIC_ONLY**

## Quality gate

Final-use blockers:
- groq: Benchmark is a development/regression set, not a blind holdout.
- groq: Independent LLM-judge coverage is incomplete; faithfulness, answer relevance, and hallucination metrics are not final.
- ollama: Benchmark is a development/regression set, not a blind holdout.
- ollama: Independent LLM-judge coverage is incomplete; faithfulness, answer relevance, and hallucination metrics are not final.
- Benchmark leakage audit found exact overlap in 54 item(s).

| Model | Model Name | Overall | Deterministic | Answer | Grounding | Retrieval | Safety | Score Status | Judge Coverage | P@K | R@K | Hit@K | MRR | NDCG@K | Token F1 | Faithfulness | Citation F1 | Hallucination | Avg generation ms | Estimated E2E ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| groq | llama-3.3-70b-versatile | None | 83.59 | 54.24 | 98.89 | 99.68 | 100.0 | INCOMPLETE_MISSING_JUDGE | 0.0 | 0.2022 | 1.0 | 1.0 | 0.9944500000000001 | 0.9959 | 0.257 | None | 0.9889 | None | 2633.303 | 9144.1091 |
| ollama | qwen3-custom:eval-20260803 | None | 88.94 | 68.58 | 100.0 | 99.68 | 100.0 | INCOMPLETE_MISSING_JUDGE | 0.0 | 0.2022 | 1.0 | 1.0 | 0.9944500000000001 | 0.9959 | 0.59105 | None | 1.0 | None | 4092.4352 | 10603.241300000002 |

## Retrieval-context consistency

- Status: checked
- Questions checked: 100
- Expected questions: 100
- Context mismatches across models: 0

A zero mismatch count confirms that the compared models used identical retrieved evidence.

## Composite score

The primary comparison uses a bilingual macro average, so English and Indonesian receive equal weight despite different question counts.

Overall score = 35% answer quality + 30% grounding + 20% retrieval + 15% safety. Latency is reported separately and does not increase the quality score.

If the LLM judge is skipped, fails, or has incomplete coverage, Overall is intentionally left empty; deterministic_score remains available for diagnostics only.

## Language comparison

English and Indonesian scores are descriptive by-language slices, not a controlled language-gap test, because the question sets do not use equivalent source targets.
