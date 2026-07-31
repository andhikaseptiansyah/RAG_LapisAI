# Comparison of 3 LLM Models (Bilingual Macro)

| Model | Model Name | Overall | Answer | Grounding | Retrieval | Safety | P@K | R@K | Hit@K | MRR | Token F1 | Faithfulness | Citation | Hallucination | Avg ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ollama | qwen3-custom:latest | 71.07 | 57.77 | 70.0 | 87.22 | 82.74 | 0.17554999999999998 | 0.87775 | 0.87775 | 0.8611 | 0.4516 | None | 0.7 | None | 9085.9321 |

## Retrieval-context consistency

- Questions checked: 100
- Context mismatches across models: 0

A zero mismatch count confirms that the three models were compared using identical retrieved evidence.

## Composite score

The primary comparison uses a bilingual macro average, so English and Indonesian receive equal weight despite different question counts.

Overall score = 35% answer quality + 30% grounding + 20% retrieval + 15% safety. Latency is reported separately and does not increase the quality score.
