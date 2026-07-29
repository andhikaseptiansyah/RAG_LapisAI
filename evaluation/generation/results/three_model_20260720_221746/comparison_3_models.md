# Comparison of 3 LLM Models

| Model | Model Name | Token F1 | Keyword | Faithfulness | Relevance | Citation | False refusal | Unanswerable safety | Hallucination | Failure rate | Avg ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ollama | qwen3-custom:latest | 0.4244 | 0.6574 | 4.101 | 3.9596 | 0.9111 | 0.0111 | 0.6 | 0.0303 | 0.01 | 10136.8878 |
| gemini | gemini-2.0-flash | 0.3147 | 0.6519 | 3.9798 | 3.9192 | 0.9111 | 0.0111 | 0.6 | 0.0202 | 0.01 | 8193.7072 |
| openai | gpt-4o | 0.3147 | 0.6519 | 3.9798 | 3.9192 | 0.9111 | 0.0111 | 0.6 | 0.0202 | 0.01 | 6785.7307 |

## Retrieval-context consistency

- Questions checked: 100
- Context mismatches across models: 0

A zero mismatch count confirms that the three models were compared using identical retrieved evidence.
