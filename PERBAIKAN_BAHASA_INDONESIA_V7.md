# Perbaikan Bahasa Indonesia V7

Build: `rag-multilingual-v7-20260723`

## Masalah yang diperbaiki

Pertanyaan Inggris berhasil menemukan dokumen, sedangkan pertanyaan Indonesia yang setara ditolak. V6 sudah membuat English bridge, tetapi proses bridge belum benar-benar identik dengan jalur pertanyaan Inggris yang berhasil. Selain itu, kandidat bridge masih membawa metadata evidence dan answerability dari pemeriksaan sebelumnya.

## Perubahan V7

1. Pertanyaan Indonesia tetap mencoba retrieval asli terlebih dahulu.
2. Jika tidak ada kandidat strict, sistem membuat natural English bridge.
3. Bridge dijalankan melalui pipeline penuh yang sama dengan pertanyaan Inggris langsung, termasuk reranker, evidence verifier, dan answerability gate.
4. Seluruh metadata evidence dan answerability lama dibuang sebelum kandidat diperiksa kembali menggunakan pertanyaan Indonesia asli.
5. Respons chat sekarang mengembalikan `failure_stage`, `retrieval_mode`, `retrieval_query`, `buildVersion`, dan `chatServiceSha256` untuk diagnosis runtime.
6. Skrip startup V7 selalu menghentikan backend lama di port 8000 dan menghapus `__pycache__` sebelum menjalankan kode baru.

## Instalasi yang disarankan

Gunakan paket patch agar `backend/chroma_db`, `backend/uploads/files`, `.env`, akun, dan riwayat percakapan yang sudah ada tidak terhapus.

1. Matikan backend dan frontend.
2. Ekstrak isi `RAG_LapisAI_PATCH_V7.zip` ke folder proyek aktif. Izinkan overwrite.
3. Jalankan `START_BACKEND_FIXED_V7.ps1`.
4. Pada terminal lain, jalankan `CHECK_BACKEND_FIXED_V7.ps1`.
5. Pastikan health menampilkan build V7 dan `chatServiceSha256`.
6. Jalankan `TEST_P1_INDONESIA_V7.ps1` untuk menguji backend tanpa melibatkan frontend.
7. Setelah tes backend berhasil, restart frontend dan lakukan hard refresh `Ctrl + Shift + R`.

## Hasil yang diharapkan

Pertanyaan:

`Seberapa cepat insiden IT P1 harus diselesaikan?`

Jawaban minimal yang valid:

`4 jam.`

Respons juga harus memiliki source `SOP_IT_Incident_Handling.pdf`, confidence di atas 0, dan retrieval mode `natural_language_bridge` atau `original`.
