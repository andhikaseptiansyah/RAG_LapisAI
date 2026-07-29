# Evaluasi 3 Model LapisAI

Evaluasi ini membandingkan **Ollama, Gemini, dan Groq** pada pertanyaan dan bukti retrieval yang sama.

## Dataset pengguna

Dataset aktif berasal dari:

- `evaluation/datasets/raw_user/qna_english.csv`
- `evaluation/datasets/raw_user/qna_indonesia.csv`

Sebelum evaluasi, dataset dibersihkan oleh `evaluation/prepare_evaluation_dataset.py`.
Satu duplikat persis pada pertanyaan **How long are audit logs retained?** digabung agar tidak menggandakan bobot satu kasus.

Dataset final:

| Bahasa | Total | Answerable | Unanswerable |
|---|---:|---:|---:|
| Inggris | 74 | 69 | 5 |
| Indonesia | 15 | 10 | 5 |
| **Total** | **89** | **79** | **10** |

Audit tersedia di `evaluation/datasets/dataset_audit_user.json`.

## Requirement Project 1 yang dicakup

Evaluasi mencakup dua lapisan:

1. **Retrieval quality**
   - Precision@K
   - Recall@K
   - Hit@K
   - Mean Reciprocal Rank atau MRR
   - Context precision dan context recall

2. **Answer quality**
   - Token F1
   - Expected-keyword coverage
   - Faithfulness 1–5
   - Answer relevance 1–5
   - Citation accuracy
   - False-refusal rate
   - Unanswerable safety rate
   - Hallucination rate
   - Generation failure rate
   - Average, median, dan P95 latency

Faithfulness dan answer relevance memakai **satu judge model yang sama** untuk semua provider. Gunakan `--skip-llm-judge` bila judge belum tersedia. Metrik deterministik tetap dihitung.

## Keadilan perbandingan

- Satu snapshot retrieval dibuat sebelum ketiga model dijalankan.
- Snapshot tersebut dipakai untuk menghitung Precision@K, Recall@K, Hit@K, dan MRR.
- Karena ketiga model memakai pipeline retrieval yang sama, metrik retrieval seharusnya sama. Perbedaan antar-model terutama terlihat pada jawaban, grounding, safety, dan latency.
- Fingerprint konteks generasi dibandingkan antar-model.
- Perbandingan utama memakai **bilingual macro average**. Bahasa Inggris dan Indonesia mendapat bobot sama meskipun jumlah pertanyaannya berbeda.
- Latency ditampilkan terpisah dan tidak menaikkan skor kualitas.

Skor komposit:

```text
Overall = 35% Answer Quality
        + 30% Grounding
        + 20% Retrieval
        + 15% Safety
```

## Persiapan

Tambahkan konfigurasi ke `.env`:

```env
GEMINI_API_KEY=...
GROQ_API_KEY=...

LAPISAI_EVAL_USERNAME=admin
LAPISAI_EVAL_PASSWORD=...

OLLAMA_MODEL=qwen3-custom:latest
GEMINI_MODEL=gemini-3.5-flash
GROQ_MODEL=llama-3.3-70b-versatile
```

Untuk LLM judge lokal:

```env
EVAL_LLM_BASE_URL=http://localhost:11434/v1
EVAL_LLM_API_KEY=ollama
EVAL_LLM_MODEL=qwen3-custom:latest
```

## Jalankan backend

```powershell
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000 --app-dir backend
```

Endpoint evaluasi khusus tersedia di:

```text
POST /api/admin/evaluation/chat
```

Endpoint ini hanya dapat dipakai admin dan **tidak menyimpan percakapan atau query log**, sehingga benchmark tidak mengotori data aplikasi.

## Validasi dataset

```powershell
python .\evaluation\generation\run_three_model_evaluation.py --validate-only
```

Hasil yang benar:

```text
Total: 89
English: 74
Indonesia: 15
Answerable: 79
Unanswerable: 10
```

## Jalankan evaluasi penuh

```powershell
python .\evaluation\generation\run_three_model_evaluation.py
```

Atau:

```powershell
.\evaluation\run_three_model_evaluation.ps1
```

Linux atau macOS:

```bash
./evaluation/run_three_model_evaluation.sh
```

Evaluasi melakukan:

- 89 retrieval snapshot
- 89 jawaban Ollama
- 89 jawaban Gemini
- 89 jawaban Groq
- Sampai 267 penilaian judge bila LLM judge diaktifkan

## Melanjutkan proses

```powershell
python .\evaluation\generation\run_three_model_evaluation.py --resume
```

Checkpoint disimpan setelah setiap pertanyaan.

## Evaluasi tanpa LLM judge

```powershell
python .\evaluation\generation\run_three_model_evaluation.py --skip-llm-judge
```

## Output

```text
evaluation/generation/results/three_model_<timestamp>/
├── retrieval_snapshot.json
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
├── comparison_3_models.md
└── charts/
    ├── 01_overall_model_score.png
    ├── 02_retrieval_quality.png
    ├── 03_answer_and_grounding.png
    ├── 04_safety_quality.png
    ├── 05_average_latency.png
    ├── 06_language_comparison.png
    └── evaluation_dashboard.html
```

## Membaca hasil

Jangan memilih model hanya dari satu skor.

- Pilih **retrieval score** tinggi bila sumber sering gagal ditemukan.
- Pilih **grounding score** tinggi bila risiko hallucination menjadi perhatian utama.
- Pilih **safety score** tinggi bila pertanyaan unanswerable harus ditolak dengan benar.
- Gunakan diagram latency untuk menilai pengalaman pengguna.
- Periksa baris dengan confidence tinggi tetapi citation accuracy rendah secara manual.
