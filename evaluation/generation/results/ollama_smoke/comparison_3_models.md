# Comparison of 3 LLM Models (Bilingual Macro)

| Model | Model Name | Overall | Answer | Grounding | Retrieval | Safety | P@K | R@K | Hit@K | MRR | Token F1 | Faithfulness | Citation | Hallucination | Avg ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ollama | qwen3-custom:latest | 66.94 | 53.72 | 62.22 | 88.46 | 78.52 | 0.18 | 0.9 | 0.9 | 0.8537 | 0.40770000000000006 | None | 0.62225 | None | 12635.8454 |

## Retrieval-context consistency

- Questions checked: 100
- Context mismatches across models: 0

A zero mismatch count confirms that the three models were compared using identical retrieved evidence.

## Composite score

The primary comparison uses a bilingual macro average, so English and Indonesian receive equal weight despite different question counts.

Overall score = 35% answer quality + 30% grounding + 20% retrieval + 15% safety. Latency is reported separately and does not increase the quality score.
