# Comparison of 3 LLM Models (Bilingual Macro)

| Model | Model Name | Overall | Answer | Grounding | Retrieval | Safety | P@K | R@K | Hit@K | MRR | Token F1 | Faithfulness | Citation | Hallucination | Avg ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ollama | qwen3-custom:latest | 78.98 | 67.01 | 86.85 | 88.46 | 78.52 | 0.18 | 0.9 | 0.9 | 0.8537 | 0.4082 | 4.9762 | 0.62225 | 0.0119 | 7440.7992 |

## Retrieval-context consistency

- Questions checked: 100
- Context mismatches across models: 0

A zero mismatch count confirms that the three models were compared using identical retrieved evidence.

## Composite score

The primary comparison uses a bilingual macro average, so English and Indonesian receive equal weight despite different question counts.

Overall score = 35% answer quality + 30% grounding + 20% retrieval + 15% safety. Latency is reported separately and does not increase the quality score.
