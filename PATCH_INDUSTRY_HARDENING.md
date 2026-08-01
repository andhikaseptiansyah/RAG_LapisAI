# LapisAI Industry Hardening Patch

Paket ZIP ini hanya berisi file baru atau file yang diperbaiki. Ekstrak ke root
project LapisAI dan pertahankan struktur direktorinya. Buat backup project aktif
sebelum menimpa file.

## Perubahan utama

- Validator grounding bilingual menerima parafrasa Indonesia yang sah, tetapi
  tetap menolak angka, produk, peran persetujuan, dan cara pelaporan yang salah.
- Angka rentang seperti `IDR 10-50 million` dibuktikan sebagai dua endpoint dan
  peran persetujuannya diikat pada tier lokal yang sama.
- Sitasi memakai threshold khusus yang lebih ketat dan hanya menampilkan sumber
  yang mendukung klaim jawaban.
- Nama file yang dinarasikan model dihapus dari isi jawaban. Sitasi tetap dikirim
  melalui metadata terstruktur.
- Ollama memakai seed tetap. Untuk produksi, ganti tag `:latest` dengan tag atau
  digest model yang immutable.
- `.env`, backup `.env`, dan variasi file rahasia lain diabaikan oleh Git,
  sementara `.env.example` tetap dilacak.
- Keyword coverage evaluasi sekarang mengukur jawaban saja. Pipeline juga
  mencatat diagnostik prompt leakage, interval kepercayaan Wilson 95%, estimasi
  latency sequential, serta reproducibility manifest dengan hash input.
- Evaluator menolak self-judge secara default dan runner mengaudit kebocoran
  benchmark. Dataset saat ini harus diperlakukan sebagai development/regression
  set, bukan blind holdout.

## Konfigurasi baru

Tambahkan atau pertahankan nilai berikut pada `.env` lokal. Jangan menyalin
rahasia ke `.env.example`.

```env
CITATION_MIN_CLAIM_SUPPORT=0.50
OLLAMA_SEED=42
```

## Verifikasi cepat

```bash
PYTHONPATH=backend python evaluation/validate_user_100_setup.py --dataset-only
python evaluation/audit_benchmark_leakage.py \
  --ground-truth evaluation/datasets/qna_english_user.csv \
  --ground-truth evaluation/datasets/qna_indonesia_user.csv \
  --role development
python -m py_compile \
  backend/api/grounding_validator.py \
  backend/api/answer_formatter.py \
  evaluation/generation/evaluate_generation.py
```

Jalankan test backend lengkap pada environment project yang sudah memasang
`backend/requirements.txt` dan `backend/requirements-dev.txt`:

```bash
PYTHONPATH=backend pytest -q backend/tests
```

Re-index corpus tidak diperlukan karena patch ini tidak mengubah embedding atau
format index. Jalankan evaluasi model ulang karena definisi metric dan aturan
sitasi berubah.
