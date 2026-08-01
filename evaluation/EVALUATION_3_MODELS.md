# Evaluasi Ollama, Gemini, dan Groq

Pipeline ini membandingkan provider generation pada dataset dan retrieval
snapshot yang sama. Endpoint evaluasi hanya dapat diakses administrator dan
tidak menambah riwayat percakapan maupun query log aplikasi.

## Dataset aktif

| Bahasa | Total | Answerable | Unanswerable |
|---|---:|---:|---:|
| English | 50 | 45 | 5 |
| Indonesia | 50 | 45 | 5 |
| **Total** | **100** | **90** | **10** |

Sumber dataset adalah `datasets/qna_english_user.csv` dan
`datasets/qna_indonesia_user.csv`. Dataset final tidak memiliki pertanyaan
duplikat.

## Metrik

Retrieval:

- Precision@K, Recall@K, Hit@K, MRR, NDCG@K, dan Top-1 accuracy.
- Context precision/recall dan kecocokan dokumen rujukan.

Jawaban dan grounding:

- Token F1 dan expected-keyword coverage dari **jawaban saja**. Coverage pada
  pertanyaan serta question+answer tetap dicatat sebagai diagnostik kebocoran
  anotasi, bukan skor kualitas utama.
- Citation precision, recall, dan F1.
- Faithfulness serta answer relevance bila LLM judge diaktifkan.
- False-refusal rate, unanswerable safety rate, hallucination rate, dan
  generation failure rate.
- Average, median, dan P95 latency, termasuk estimasi sequential retrieval plus
  generation. Nilai ini bukan pengukuran wall-clock request tunggal.
- Interval kepercayaan Wilson 95% untuk metrik biner seperti false refusal,
  safety, Hit@K, Top-1, dan pipeline failure.

Perbandingan utama memakai macro average per bahasa agar English dan Indonesia
mendapat bobot seimbang. Latency dilaporkan terpisah dari skor kualitas.

Jika judge tersedia, komposisi overall score adalah:

```text
Overall = 35% Answer Quality
        + 30% Grounding
        + 20% Retrieval
        + 15% Safety
```

Tanpa judge, pipeline tetap menghasilkan deterministic score dan menandai skor
komposit sebagai belum lengkap.

## Persiapan `.env`

Konfigurasi minimum untuk Ollama:

```env
LAPISAI_EVAL_USERNAME=admin
LAPISAI_EVAL_PASSWORD=PASSWORD_ADMIN_LOKAL_ANDA
LAPISAI_LOGIN_URL=http://127.0.0.1:8000/api/auth/login
LAPISAI_HEALTH_URL=http://127.0.0.1:8000/health
LAPISAI_RETRIEVAL_DEBUG_URL=http://127.0.0.1:8000/api/admin/retrieval-debug
LAPISAI_EVALUATION_READINESS_URL=http://127.0.0.1:8000/api/admin/evaluation/readiness
LAPISAI_EVALUATION_CHAT_URL=http://127.0.0.1:8000/api/admin/evaluation/chat
LAPISAI_EVAL_TIMEOUT=240

# Pin tag atau digest immutable untuk run produksi yang dapat direproduksi.
OLLAMA_MODEL=qwen3-custom:2026-08-01
OLLAMA_SEED=42
```

Untuk provider eksternal, tambahkan key dan nama model masing-masing:

```env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash

GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
```

Untuk judge lokal yang kompatibel dengan OpenAI API:

```env
EVAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
EVAL_LLM_API_KEY=ollama
EVAL_LLM_MODEL=model-judge-independen:versi-terkunci
```

Judge harus berbeda dari model yang sedang dievaluasi. Evaluator akan berhenti
jika keduanya sama, kecuali `--allow-self-judge` diberikan secara eksplisit.
Jangan commit key, token, atau password asli.

## Urutan menjalankan

1. Jalankan backend:

   ```powershell
   python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000 --app-dir backend
   ```

2. Pastikan Ollama/provider aktif.
3. Upload dan index seluruh dokumen corpus.
4. Validasi dataset saja:

   ```powershell
   python .\evaluation\run_user_100_evaluation.py --models ollama --validate-only
   ```

5. Validasi corpus dan local index:

   ```powershell
   python .\evaluation\validate_user_100_setup.py
   ```

6. Jalankan Ollama terlebih dahulu:

   ```powershell
   python .\evaluation\run_user_100_evaluation.py `
     --models ollama `
     --skip-llm-judge `
     --output-dir .\evaluation\generation\results\ollama_100
   ```

Runner akan login, memeriksa health endpoint, lalu memastikan setiap dokumen
yang dirujuk 90 pertanyaan answerable benar-benar ada di Chroma collection
aktif. Proses berhenti dengan daftar dokumen yang kurang bila readiness gagal.

Lanjutkan checkpoint dengan output directory yang sama:

```powershell
python .\evaluation\run_user_100_evaluation.py `
  --models ollama `
  --skip-llm-judge `
  --resume `
  --output-dir .\evaluation\generation\results\ollama_100
```

Evaluasi tiga provider:

```powershell
python .\evaluation\run_user_100_evaluation.py `
  --models ollama gemini groq `
  --output-dir .\evaluation\generation\results\three_models_100
```

## Fairness

- Retrieval snapshot hanya dibuat satu kali per run.
- Setiap provider menerima ranked candidates dan generation contexts yang sama.
- Context fingerprint dicatat untuk mendeteksi perbedaan bukti antar-model.
- Provider yang gagal tidak diam-diam diganti provider lain.
- `--resume` memakai checkpoint yang sama dan tidak mengulang baris selesai.
- Hash dataset dan raw answer, git commit, versi build, context mode, serta
  status model tag mutable dicatat pada reproducibility manifest.
- Dataset 100 pertanyaan saat ini adalah development/regression set. Gunakan
  dataset terpisah dengan `--benchmark-role holdout` untuk estimasi final.

## Output

```text
evaluation/generation/results/<run>/
├── benchmark_leakage_audit.json
├── retrieval_snapshot.json
├── raw/
│   ├── input_answers_ollama.json
│   ├── input_answers_gemini.json
│   └── input_answers_groq.json
├── generation_results_<model>.csv
├── generation_summary_<model>.json
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

Jangan memilih model dari satu angka saja. Periksa retrieval, citation F1,
false-refusal, hallucination, generation failure, dan latency bersama-sama;
lalu audit manual kasus dengan confidence tinggi tetapi citation F1 rendah.
