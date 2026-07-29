# Perbaikan Bahasa Indonesia V6

Build: `rag-multilingual-v6-20260723`

## Masalah V5

V5 sudah mencoba query Inggris ketika query Indonesia gagal. Namun query Inggris masih melewati reranker dan verifikasi awal sebelum kandidat divalidasi kembali menggunakan pertanyaan Indonesia. Kandidat yang benar dapat hilang pada tahap awal tersebut.

## Perbaikan V6

1. Jalankan retrieval utama dengan pertanyaan asli.
2. Jika tidak ada bukti ketat, jalankan query Inggris natural.
3. Jika hasil bridge normal belum aman, ambil union kandidat mentah dari semantic search dan BM25.
4. Validasi seluruh kandidat mentah menggunakan pertanyaan Indonesia asli.
5. Terapkan answerability gate dan threshold yang sama.
6. Gunakan kandidat hanya jika subjek, angka, durasi, dan batasan pertanyaan cocok.

Contoh:

- Pertanyaan: `Seberapa cepat insiden IT P1 harus diselesaikan?`
- Bridge: `How quickly must a P1 IT incident be resolved?`
- Jawaban aman: `4 jam.`

## Menjalankan backend yang benar

Klik kanan `START_BACKEND_FIXED_V6.ps1`, lalu pilih **Run with PowerShell**.

Skrip akan memeriksa port 8000. Jika backend LapisAI lama masih aktif, skrip menghentikannya lalu menjalankan build V6 dari folder yang benar.

Verifikasi melalui:

`http://127.0.0.1:8000/api/health`

Nilai `buildVersion` harus:

`rag-multilingual-v6-20260723`
