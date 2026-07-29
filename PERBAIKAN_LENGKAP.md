# Ringkasan perbaikan

## Frontend

- Menambahkan route `/admin/staff`.
- Menyamakan definisi role menjadi `user`, `staff`, dan `admin`.
- Menambahkan form pembuatan akun dengan pilihan role.
- Menambahkan edit nama, username, dan role.
- Menambahkan perubahan kata sandi dan penghapusan akun.
- Melindungi akun administrator dari tindakan manajemen akun biasa.
- Mengubah halaman upload agar menjelaskan indexing sinkron.
- Mengubah aksi batch menjadi indexing ulang yang benar-benar diproses backend.
- Menyeragamkan istilah antarmuka ke bahasa Indonesia.

## Backend

- Menjadikan pilihan bahasa UI sebagai sumber utama bahasa jawaban.
- Menambahkan endpoint umum `PATCH /api/admin/users/{user_id}`.
- Menambahkan dukungan pembuatan akun `user` dan `staff`.
- Menambahkan pemeriksaan administrator pada dokumen, dashboard, dan log pertanyaan.
- Menghapus registrasi endpoint lama tanpa autentikasi.
- Menghapus router lama dan folder `python-service`.
- Menambahkan validasi dasar isi PDF, DOCX, dan TXT.
- Menjadikan upload langsung melakukan indexing.
- Menjadikan endpoint batch indexing benar-benar melakukan indexing ulang.
- Menyatukan lokasi seluruh file JSON di direktori backend.
- Menambahkan migrasi data lama dari root proyek.
- Menghapus kredensial bawaan yang mudah ditebak.
- Menghapus modul OpenAI lama yang tidak digunakan, backup kode, dan backup `.env`.
- Menambahkan autentikasi token pada skrip evaluasi yang memanggil `/api/chat`.
- Menghitung rata-rata waktu respons query log dari data aktual.

## Validasi

- Seluruh file Python lolos `compileall`.
- Seluruh file TypeScript dan TSX lolos pemeriksaan sintaks parser TypeScript.
- Tujuh pengujian unit ringan berhasil.
- Import runtime FastAPI penuh tetap membutuhkan dependensi pada `backend/requirements.txt`, termasuk ChromaDB dan Sentence Transformers.
