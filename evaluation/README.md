# Evaluasi LapisAI

Folder ini berisi dataset dan pipeline benchmark untuk mengukur retrieval,
kualitas jawaban, grounding/sitasi, safety pada pertanyaan unanswerable, serta
latency model.

Dataset aktif:

| Bahasa | Total | Answerable | Unanswerable |
|---|---:|---:|---:|
| English | 50 | 45 | 5 |
| Indonesia | 50 | 45 | 5 |
| **Total** | **100** | **90** | **10** |

File yang digunakan:

- `datasets/qna_english_user.csv`
- `datasets/qna_indonesia_user.csv`
- `datasets/dataset_audit_user.json`

Dataset ini diperlakukan sebagai **development/regression set**, bukan blind
holdout, karena sebagian pertanyaan sudah muncul di test atau kode aktif. Runner
menjalankan `audit_benchmark_leakage.py` dan menyimpan laporannya. Untuk dataset
baru yang benar-benar tertutup, gunakan `--benchmark-role holdout`; run akan
gagal jika ada pertanyaan atau expected answer yang ditemukan di kode.

## Validasi dataset saja

Perintah ini tidak membutuhkan backend, corpus, Chroma, atau Ollama:

```powershell
python .\evaluation\run_user_100_evaluation.py --models ollama --validate-only
```

## Validasi runtime

Setelah dokumen di-upload dan di-index:

```powershell
python .\evaluation\validate_user_100_setup.py
```

Saat benchmark dimulai, pipeline juga memanggil endpoint readiness terproteksi.
Evaluasi dihentikan bila collection kosong atau salah satu dokumen rujukan tidak
ada di Chroma aktif. Guard ini mencegah skor rendah palsu akibat corpus yang
belum lengkap.

## Evaluasi Ollama terlebih dahulu

```powershell
python .\evaluation\run_user_100_evaluation.py `
  --models ollama `
  --skip-llm-judge `
  --output-dir .\evaluation\generation\results\ollama_100
```

Lanjutkan checkpoint dengan menambahkan `--resume`. Hapus
`--skip-llm-judge` setelah judge model independen dikonfigurasi bila
faithfulness dan answer relevance berbasis judge diperlukan. Evaluator menolak
self-judge secara default. `--allow-self-judge` hanya untuk eksperimen yang
secara eksplisit menerima keterbatasan tersebut.

## Output

Output baru dibuat di directory yang diberikan dan mencakup retrieval snapshot,
audit kebocoran benchmark, raw model answers, CSV per pertanyaan, JSON summary,
model comparison, chart, serta dashboard HTML. Summary menyertakan hash input,
versi build, referensi model, interval kepercayaan Wilson 95%, dan estimasi
latency sequential retrieval plus generation. Setiap report sekarang memiliki
quality gate `FINAL_ELIGIBLE` atau `DIAGNOSTIC_ONLY`; blocker final (misalnya
development set, judge tidak lengkap, model `:latest`, atau kebocoran benchmark)
ditulis eksplisit pada JSON, Markdown, CSV, dan dashboard.

Nama file perbandingan mengikuti jumlah model, misalnya
`comparison_1_model.*` atau `comparison_3_models.*`. Untuk workflow publikasi,
tambahkan `--require-final-report` agar command gagal bila quality gate final
belum terpenuhi.

File lama di `evaluation/results` atau `evaluation/generation/results` adalah
artefak eksperimen/regresi dan bukan hasil final setelah perubahan strict RAG.
Gunakan output dari run terbaru yang corpus, konfigurasi, dan modelnya tercatat.

Panduan lengkap: `evaluation/EVALUATION_3_MODELS.md`.
