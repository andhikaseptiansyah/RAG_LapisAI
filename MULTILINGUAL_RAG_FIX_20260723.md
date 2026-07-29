# Multilingual RAG Fix V5, 23 July 2026

## Masalah

Pertanyaan Inggris seperti:

```text
How quickly must a P1 IT incident be resolved?
```

berhasil menemukan jawaban, sedangkan pertanyaan Indonesia yang setara:

```text
Seberapa cepat insiden IT P1 harus diselesaikan?
```

kadang ditolak walaupun dokumen Inggris memuat bukti yang benar.

## Penyebab utama

Pipeline lama hanya menjalankan English bridge fallback jika `hybrid_search()` mengembalikan daftar kosong. Dalam kondisi tertentu, pencarian Indonesia mengembalikan kandidat yang terlihat relevan tetapi belum memenuhi status strict evidence. Karena daftarnya tidak kosong, fallback Inggris tidak dijalankan. Kandidat tersebut kemudian gagal pada context selection dan sistem memberi jawaban penolakan.

## Perubahan V5

- Fallback sekarang dijalankan ketika hasil utama tidak memiliki kandidat yang benar-benar strict dan aman untuk generation, bukan hanya ketika daftar hasil kosong.
- English bridge memakai candidate pool yang lebih luas untuk meningkatkan recall.
- Answerability gate pada query bridge tidak dijalankan dua kali.
- Semua kandidat bridge tetap diverifikasi ulang menggunakan pertanyaan Indonesia asli.
- Identitas penting seperti P1 versus P2, angka, durasi, dan subject constraint tetap diperiksa.
- Tidak ada threshold retrieval, evidence, confidence, atau answerability yang diturunkan.
- Build backend dinaikkan menjadi `rag-multilingual-v5-20260723` agar deployment aktif mudah diverifikasi.

## File utama yang berubah

```text
backend/api/chat_service.py
backend/api/build_info.py
backend/tests/test_language_bridge_fallback_v5.py
backend/tests/test_multilingual_query_variants_v3.py
```

## Validasi

Regression test khusus masalah Indonesia dan English bridge:

```text
13 passed
```

Python compile check juga berhasil.

Full backend test menghasilkan satu kegagalan lama yang tidak berkaitan dengan multilingual retrieval. Test tersebut mengharapkan penghapusan folder dan router legacy yang masih tersedia di paket asli.

## Cara menjalankan

Tidak perlu reindex karena model embedding dan koleksi ChromaDB tidak berubah.

1. Ganti source backend dengan versi perbaikan.
2. Hentikan proses backend lama.
3. Jalankan kembali FastAPI atau restart container/service deployment.
4. Buka endpoint `/health`.
5. Pastikan respons memuat:

```json
{
  "buildVersion": "rag-multilingual-v5-20260723"
}
```

6. Uji kembali kedua pertanyaan Inggris dan Indonesia.

Jika `/health` masih menunjukkan build V4, V3, atau tidak memiliki `buildVersion`, aplikasi masih mengakses backend lama. Ini cukup sering terjadi karena deployment, seperti manusia, kadang bersikeras hidup di masa lalu.
