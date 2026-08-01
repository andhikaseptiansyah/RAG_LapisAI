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
`--skip-llm-judge` setelah judge model dikonfigurasi bila faithfulness dan
answer relevance berbasis judge diperlukan.

## Output

Output baru dibuat di directory yang diberikan dan mencakup retrieval snapshot,
raw model answers, CSV per pertanyaan, JSON summary, model comparison, chart,
serta dashboard HTML.

File lama di `evaluation/results` atau `evaluation/generation/results` adalah
artefak eksperimen/regresi dan bukan hasil final setelah perubahan strict RAG.
Gunakan output dari run terbaru yang corpus, konfigurasi, dan modelnya tercatat.

Panduan lengkap: `evaluation/EVALUATION_3_MODELS.md`.
