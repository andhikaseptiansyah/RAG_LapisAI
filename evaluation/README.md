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
menjalankan `audit_benchmark_leakage.py` dan menyimpan laporannya. Runner publik
sekarang menolak `--benchmark-role holdout` agar dataset publik tidak pernah
salah dilabeli sebagai hasil final.

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

Mulai dari build `rag-bilingual-eval-v19-20260802`, snapshot schema v4 mengukur
satu kali strict retrieval tanpa mengulang baseline diagnostik. Query semantic
multilingual di-embed dan dikirim ke Chroma secara batch, sedangkan reranker
memakai paling banyak dua query view. Gunakan output directory baru saat
membandingkan latency dengan build lama karena snapshot v3 dan v4 tidak setara.

## Output

Output baru dibuat di directory yang diberikan dan mencakup retrieval snapshot,
audit kebocoran benchmark, raw model answers, CSV per pertanyaan, JSON summary,
model comparison, chart, serta dashboard HTML. Summary menyertakan hash input,
versi build, referensi model, interval kepercayaan Wilson 95%, dan estimasi
latency sequential retrieval plus generation. Setiap report sekarang memiliki
quality gate `FINAL_ELIGIBLE` atau `DIAGNOSTIC_ONLY`; blocker final (misalnya
development set, judge tidak lengkap, model `:latest`, atau kebocoran benchmark)
ditulis eksplisit pada JSON, Markdown, CSV, dan dashboard.

Summary juga menampilkan rasio latency Indonesia terhadap English. Rasio ini
bersifat deskriptif karena dataset publik tidak mempunyai target EN-ID yang
sepenuhnya sepadan. Token F1, exact match, dan keyword coverage adalah metrik
leksikal. Parafrasa atau terjemahan yang benar dapat memperoleh angka lebih
rendah, sehingga kualitas semantik final tetap memerlukan judge independen.

Nama file perbandingan mengikuti jumlah model, misalnya
`comparison_1_model.*` atau `comparison_3_models.*`.

## Evaluasi final yang valid

Tidak perlu membuat CSV holdout secara manual. Pipeline baru membuat pasangan
EN-ID langsung dari Chroma aktif, meminta model kedua memeriksa ground truth,
mewajibkan persetujuan manusia, membekukan hash corpus dan seluruh artefak, lalu
menjalankan quality gate final:

```powershell
python .\evaluation\create_private_holdout.py
python .\evaluation\review_private_holdout.py --reviewer-name "Andika"
python .\evaluation\run_final_evaluation.py --models ollama
```

Keempat peran model harus berbeda dan memakai tag versi tetap: model yang
dievaluasi, author holdout, reviewer holdout, dan judge. Detail konfigurasi dan
aturan anti-leakage ada di `evaluation/FINAL_EVALUATION.md`.

File lama di `evaluation/results` atau `evaluation/generation/results` adalah
artefak eksperimen/regresi dan bukan hasil final setelah perubahan strict RAG.
Gunakan output dari run terbaru yang corpus, konfigurasi, dan modelnya tercatat.

Panduan regression: `evaluation/EVALUATION_3_MODELS.md`.
Panduan final: `evaluation/FINAL_EVALUATION.md`.
