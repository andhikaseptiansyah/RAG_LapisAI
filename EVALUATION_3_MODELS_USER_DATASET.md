# Implementasi Evaluasi 3 Model

Fitur evaluasi tiga model telah disiapkan untuk dataset pertanyaan pengguna.

## Perubahan utama

- Dataset Inggris dan Indonesia pengguna dimasukkan ke `evaluation/datasets/raw_user/`.
- Satu pertanyaan duplikat digabung. Dataset final berisi 89 pertanyaan unik.
- Ditambahkan endpoint admin khusus evaluasi yang tidak menyimpan chat atau query log.
- Ditambahkan retrieval snapshot bersama agar perbandingan Ollama, Gemini, dan Groq adil.
- Ditambahkan Precision@K, Recall@K, Hit@K, dan MRR.
- Ditambahkan skor komposit answer quality, grounding, retrieval, dan safety.
- Skor utama memakai bilingual macro average.
- Ditambahkan enam diagram PNG dan satu dashboard HTML.

## Status verifikasi

- Validasi dataset berhasil: 89 total, 79 answerable, 10 unanswerable.
- Pengujian perubahan evaluasi dan endpoint berhasil.
- Evaluasi model penuh tidak dijalankan di paket ini karena membutuhkan backend aktif, dokumen yang sudah diindeks, Ollama, serta API key Gemini dan Groq.

Lihat `evaluation/EVALUATION_3_MODELS.md` untuk perintah lengkap.
