# Hotfix Upload Dokumen

Perubahan ini memperbaiki kegagalan unggah yang terlihat sebagai HTTP 409 ketika nama berkas sudah ada, termasuk berkas lama yang masih tertinggal di folder upload tetapi tidak tercatat dalam `documents_store.json`.

Perubahan utama:

- Frontend memeriksa konflik nama ke backend sebelum mengirim isi berkas.
- Konflik nama membuka dialog **Ganti dan Indeks Ulang**, bukan berhenti sebagai pesan error umum.
- Backend tetap mengembalikan kontrak konflik terstruktur sebagai perlindungan terhadap kondisi balapan.
- Penimpaan berkas lama mencadangkan isi berkas dan mengembalikannya jika indexing gagal.
- Pesan error FastAPI pada properti `detail` sekarang ditampilkan dengan benar oleh frontend.
- Pola nama pengguna diperbaiki agar valid pada browser yang menjalankan regular expression HTML dengan flag `v`.
- Duplikasi nama pengguna dicegah di frontend sebelum request akun dikirim.

Alur unggah baru:

1. Pilih PDF, DOCX, atau TXT.
2. Frontend memeriksa nama berkas melalui `/api/admin/documents/conflicts`.
3. Jika tidak ada konflik, backend langsung parsing, chunking, embedding, dan indexing.
4. Jika nama sudah ada, UI meminta konfirmasi.
5. Tombol **Ganti dan Indeks Ulang** mengirim persetujuan penimpaan dan mempertahankan ID dokumen lama jika tersedia.
