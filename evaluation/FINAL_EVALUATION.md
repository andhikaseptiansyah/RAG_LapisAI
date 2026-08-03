# Evaluasi Final LapisAI

Workflow ini menghasilkan evaluasi yang dapat dipertanggungjawabkan. Ia tidak
memaksa skor menjadi 100. Skor tinggi hanya sah jika model memang menjawab
private holdout dengan benar.

## Yang diperbaiki

- Dataset 100 pertanyaan publik hanya boleh dipakai untuk development dan regression.
- Private holdout dibuat otomatis dari Chroma aktif. Tidak ada CSV yang harus dicari atau dibuat manual.
- Setiap soal memiliki pasangan English dan Indonesia dengan target yang sama.
- Soal answerable memiliki kutipan bukti persis dari corpus.
- Soal unanswerable diperiksa terhadap chunk corpus yang paling relevan.
- Author, reviewer, judge, dan model yang dievaluasi harus memakai empat model berbeda.
- Semua model final harus memakai tag versi tetap, bukan `:latest`.
- Seluruh soal wajib disetujui manusia sebelum final run.
- Hash corpus, CSV, review, manifest, raw answer, dan konfigurasi run dicatat.
- Perubahan artefak, kebocoran benchmark, self-judge, judge yang tidak lengkap, atau corpus yang berubah langsung menggagalkan final run.
- Snapshot schema v4 mengikat setiap jawaban pada fingerprint snapshot lengkap;
  resume stale atau campuran build otomatis ditolak dan dihitung ulang.
- Latency retrieval diukur dari satu strict retrieval. Baseline debug tidak
  dijalankan dua kali, semantic variants dibatch, dan reranker memakai maksimal
  dua query view.

## Verifikasi patch dan regression baru

Setelah instalasi, restart backend lalu cek build:

```powershell
(Invoke-RestMethod http://127.0.0.1:8000/health).buildVersion
```

Nilai yang benar adalah:

```text
rag-bilingual-eval-v19-20260802
```

Jalankan public regression ke folder baru agar latency v18 tidak tercampur:

```powershell
python .\evaluation\run_user_100_evaluation.py `
  --models ollama `
  --skip-llm-judge `
  --output-dir .\evaluation\generation\results\ollama_regression_v19
```

Status `DIAGNOSTIC_ONLY` pada command tersebut memang benar: dataset-nya publik,
judge dilewati, dan hasilnya bukan final holdout. Angka retrieval dan safety
tetap berguna untuk regression. Token F1 dan keyword coverage hanya mengukur
kemiripan leksikal, bukan otomatis menandakan jawaban faktual salah.

## 1. Siapkan empat model

Isi `.env` dengan empat checkpoint yang benar-benar berbeda. Jangan hanya
memberi empat nama kepada checkpoint yang sama.

```dotenv
# Model RAG yang dinilai
OLLAMA_MODEL=<evaluated-model:fixed-version>

# Model pembuat private holdout
HOLDOUT_AUTHOR_BASE_URL=http://127.0.0.1:11434/v1
HOLDOUT_AUTHOR_API_KEY=ollama
HOLDOUT_AUTHOR_MODEL=<author-model:fixed-version>

# Model independen untuk verifikasi ground truth
HOLDOUT_REVIEW_BASE_URL=http://127.0.0.1:11434/v1
HOLDOUT_REVIEW_API_KEY=ollama
HOLDOUT_REVIEW_MODEL=<reviewer-model:fixed-version>

# Model independen untuk menilai jawaban RAG
EVAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
EVAL_LLM_API_KEY=ollama
EVAL_LLM_MODEL=<judge-model:fixed-version>
```

Untuk Ollama, lihat model yang tersedia dengan `ollama list`. Jika model yang
dinilai masih memakai `:latest`, buat tag beku sebelum run. Contoh:

```powershell
ollama cp qwen3-custom:latest qwen3-custom:eval-20260802
```

Tag tetap membantu reproduksibilitas, tetapi jangan menimpa tag tersebut
setelah benchmark dibuat.

## 2. Pastikan corpus aktif

Jalankan backend dengan Chroma dan dokumen produksi yang memang ingin diuji.
Private holdout akan terikat pada fingerprint corpus ini. Jika corpus berubah,
holdout lama otomatis ditolak.

## 3. Buat private holdout otomatis

```powershell
python .\evaluation\create_private_holdout.py
```

Default-nya membuat 50 pasangan bilingual, terdiri dari 40 answerable dan 10
unanswerable. Output disimpan di folder `LapisAI_Private_Holdout` di samping
folder project, bukan di dalam repository. Jika proses terputus, lanjutkan:

```powershell
python .\evaluation\create_private_holdout.py --resume
```

## 4. Review manual seluruh pasangan

```powershell
python .\evaluation\review_private_holdout.py --reviewer-name "Andika"
```

Gunakan `a` hanya jika pertanyaan, terjemahan, jawaban, sumber, dan bukti benar.
Gunakan `r` jika ada masalah. Satu rejection saja membuat final run gagal. Buat
paket baru dengan seed dan folder baru setelah memperbaiki penyebabnya:

```powershell
python .\evaluation\create_private_holdout.py `
  --seed 20260803 `
  --output-dir "C:\Users\ANDIKA\Documents\LapisAI_Private_Holdout_v2"
```

## 5. Jalankan evaluasi final

Untuk Ollama saja:

```powershell
python .\evaluation\run_final_evaluation.py --models ollama
```

Untuk tiga provider dengan retrieval snapshot yang sama:

```powershell
python .\evaluation\run_final_evaluation.py --models ollama gemini groq
```

Command selesai sukses hanya jika comparison report berstatus
`FINAL_ELIGIBLE`. Hasil utama berada pada folder timestamp baru di
`evaluation\generation\results\final_<timestamp>`.

## Arti hasil

- `FINAL_ELIGIBLE` berarti proses benchmark lolos semua gate integritas.
- `DIAGNOSTIC_ONLY` berarti hasil boleh dipakai untuk debugging, bukan klaim final.
- Skor rendah pada run yang valid adalah temuan yang harus diperbaiki, bukan angka yang harus ditutupi.
- Setelah melihat hasil holdout, jangan tuning prompt, threshold, atau kode lalu memakai holdout yang sama sebagai hasil final. Pensiunkan holdout itu dan buat private holdout baru.

Regression sehari-hari tetap memakai:

```powershell
python .\evaluation\run_user_100_evaluation.py `
  --models ollama `
  --skip-llm-judge `
  --output-dir .\evaluation\generation\results\ollama_regression
```
