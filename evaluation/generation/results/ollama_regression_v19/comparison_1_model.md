# Evaluation of 1 LLM Model (Bilingual Macro)

> Report status: **DIAGNOSTIC_ONLY**

## Quality gate

Final-use blockers:
- ollama: Benchmark is a development/regression set, not a blind holdout.
- ollama: Independent LLM-judge coverage is incomplete; faithfulness, answer relevance, and hallucination metrics are not final.
- ollama: The evaluated model reference is mutable; pin a versioned tag or digest.
- Benchmark leakage audit found exact overlap in 54 item(s).

Warnings:
- Only one model was evaluated; this is a model diagnostic, not a comparative ranking.

| Model | Model Name | Overall | Deterministic | Answer | Grounding | Retrieval | Safety | Score Status | Judge Coverage | P@K | R@K | Hit@K | MRR | NDCG@K | Token F1 | Faithfulness | Citation F1 | Hallucination | Avg generation ms | Estimated E2E ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ollama | qwen3-custom:latest | None | 88.94 | 68.58 | 100.0 | 99.68 | 100.0 | INCOMPLETE_MISSING_JUDGE | 0.0 | 0.2022 | 1.0 | 1.0 | 0.9944500000000001 | 0.9959 | 0.59105 | None | 1.0 | None | 3999.9384 | 10498.9839 |

## Retrieval-context consistency

- Status: not_applicable
- Questions checked: 0
- Expected questions: 0
- Context mismatches across models: 0

## Composite score

The primary comparison uses a bilingual macro average, so English and Indonesian receive equal weight despite different question counts.

Overall score = 35% answer quality + 30% grounding + 20% retrieval + 15% safety. Latency is reported separately and does not increase the quality score.

If the LLM judge is skipped, fails, or has incomplete coverage, Overall is intentionally left empty; deterministic_score remains available for diagnostics only.

## Language comparison

English and Indonesian scores are descriptive by-language slices, not a controlled language-gap test, because the question sets do not use equivalent source targets.
