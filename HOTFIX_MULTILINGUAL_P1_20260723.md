# Hotfix Multilingual Retrieval P1

Tanggal: 23 Juli 2026

## Gejala

Pertanyaan Inggris berikut dijawab dengan benar:

`How quickly must a P1 IT incident be resolved?`

Namun pertanyaan Indonesia yang setara ditolak:

`Seberapa cepat insiden IT P1 harus diselesaikan?`

## Akar masalah

1. Kamus konsep hanya mengenali susunan `insiden P1`, bukan `insiden IT P1`.
2. Intent durasi hanya mengenali pola seperti `berapa lama`, bukan `seberapa cepat` atau `harus diselesaikan`.
3. Akibatnya, query Indonesia tidak memperoleh istilah jembatan Inggris yang diperlukan oleh BM25 dan evidence verifier.
4. Jika model generasi tetap menyalin kalimat bukti Inggris, fallback verbatim ikut ditolak oleh pemeriksa bahasa.
5. Paket perbaikan terdahulu memiliki folder root ganda sehingga file aktif mungkin tidak tertimpa saat diekstrak.

## Perbaikan

- Menambahkan alias dua bahasa dan variasi urutan kata untuk insiden P1 dan P2.
- Menambahkan intent durasi untuk `seberapa cepat`, `waktu penyelesaian`, `target penyelesaian`, `harus diselesaikan`, dan padanan Inggrisnya.
- Query Indonesia kini diperluas dengan istilah seperti `P1 IT incident`, `resolution time`, dan `resolved within`.
- Evidence Inggris `P1 IT incidents must be resolved within 4 hours` kini dikenali sebagai konsep `incident_p1` dan `processing_time`.
- Bukti P2 tetap ditolak untuk pertanyaan P1, meskipun semantic score dibuat sangat tinggi.
- Menambahkan fallback scalar terverifikasi. Jika model dua kali memakai bahasa sumber, satu nilai eksplisit yang sudah lolos evidence gate dilokalkan. Contoh: `four hours` menjadi `4 jam`.

## Threshold

Tidak ada threshold yang diturunkan. Nilai berikut tetap:

- `MIN_RESULT_SCORE=0.24`
- `MIN_EVIDENCE_SCORE=0.58`
- `ANSWERABILITY_MIN_TOP_SCORE=0.50`
- `ANSWERABILITY_MIN_BASE_SCORE=0.30`
- `MIN_ANSWER_CONFIDENCE=0.40`
- `MIN_SOURCE_CONFIDENCE=0.30`

## Instalasi

1. Hentikan frontend dan backend.
2. Cadangkan file `.env` aktif.
3. Ekstrak paket baru. Paket ini hanya memiliki satu folder root `RAG_LapisAI-main`.
4. Ganti proyek lama dengan isi folder tersebut. Jangan menaruhnya sebagai subfolder kedua.
5. Kembalikan `.env` aktif bila diperlukan.
6. Jalankan ulang backend dan frontend.
7. Lakukan hard refresh pada browser.

Reindex dokumen tidak diperlukan karena embedding model dan nama collection tidak berubah.
