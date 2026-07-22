# Evaluasi 3 Model — 50 English + 50 Indonesia

Dataset final:

- `evaluation/datasets/qna_english_50.csv`: 50 pertanyaan (45 answerable, 5 unanswerable)
- `evaluation/datasets/qna_indonesia_50.csv`: 50 pertanyaan (45 answerable, 5 unanswerable)
- Total: 100 pertanyaan; setiap model menghasilkan 100 jawaban
- Model: `ollama`, `gemini`, dan `groq`

## 1. Jalankan backend

Dari folder utama proyek:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000 --app-dir backend
```

Pastikan Ollama aktif dan `.env` berisi API key Gemini/Groq.

## 2. Validasi dataset tanpa memanggil model

```powershell
python .\evaluation\generation\run_three_model_evaluation.py --validate-only
```

Hasil yang benar:

- 100 pertanyaan
- EN: 50
- ID: 50
- Answerable: 90
- Unanswerable: 10

## 3. Jalankan evaluasi lengkap

```powershell
python .\evaluation\generation\run_three_model_evaluation.py
```

Atau menggunakan PowerShell launcher:

```powershell
.\evaluation\run_three_model_evaluation.ps1
```

Proses melakukan 300 request jawaban (100 pertanyaan × 3 model), lalu memakai satu judge yang sama untuk seluruh model.

## 4. Melanjutkan proses yang terputus

```powershell
python .\evaluation\generation\run_three_model_evaluation.py --resume
```

File mentah disimpan setelah setiap pertanyaan, sehingga evaluasi panjang tidak harus dimulai dari awal.

## 5. Evaluasi cepat tanpa LLM judge

```powershell
python .\evaluation\generation\run_three_model_evaluation.py --skip-llm-judge
```

Mode ini tetap menghitung Token F1, keyword coverage, source/citation accuracy, refusal safety, dan latency, tetapi tidak menghitung faithfulness/relevance semantik.

## Output

```text
evaluation/generation/results/three_model_<timestamp>/
├── raw/
│   ├── input_answers_ollama.json
│   ├── input_answers_gemini.json
│   └── input_answers_groq.json
├── generation_results_ollama.csv
├── generation_results_gemini.csv
├── generation_results_groq.csv
├── generation_summary_ollama.json
├── generation_summary_gemini.json
├── generation_summary_groq.json
├── comparison_3_models.csv
├── comparison_3_models.json
└── comparison_3_models.md
```

`comparison_3_models.csv` berisi hasil keseluruhan, bahasa Inggris, dan bahasa Indonesia untuk setiap model.

## Metrik

- Normalized Exact Match
- Token F1
- Expected-keyword coverage
- Faithfulness (1–5)
- Answer relevance (1–5)
- Context precision/recall
- Citation accuracy
- False-refusal rate pada pertanyaan answerable
- Unanswerable safety rate
- Hallucination rate
- Average/median/P95 response time
- Retrieval-context consistency lintas model

Untuk perbandingan yang adil, jangan mengubah dokumen, ChromaDB, retrieval weight, prompt, `top-k`, atau judge model selama tiga model dievaluasi.
