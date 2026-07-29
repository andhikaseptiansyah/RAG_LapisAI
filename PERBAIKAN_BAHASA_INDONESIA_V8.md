# Perbaikan Bahasa Indonesia V8

Log V7 menunjukkan retrieval sudah berhasil (`contexts=1`, confidence sekitar `0.831`). Kegagalan terjadi sesudah retrieval:

- jawaban Ollama ditolak oleh grounding validator sebagai `unsupported_claims`;
- fallback ekstraktif masih berbahasa Inggris sehingga ditolak untuk `language=ID`;
- Gemini kadang mengembalikan `503 UNAVAILABLE` karena model sedang padat.

V8 memperbaiki tahap generasi, bukan lagi retrieval:

1. Pertanyaan durasi yang memiliki satu nilai terverifikasi dijawab secara deterministik dari evidence sebelum memanggil LLM.
2. Nilai P1 dipisahkan dari P2 pada baris PDF yang tergabung.
3. Satuan dilokalkan ke bahasa jawaban, misalnya `4 hours` menjadi `4 jam` tanpa menerjemahkan atau menciptakan fakta baru.
4. Grounding validator menerima terjemahan Indonesia yang setara melalui alias konsep bilingual, tetapi tetap menolak tambahan klaim yang tidak ada di sumber.
5. Jika Gemini atau Groq tidak menghasilkan jawaban yang dapat dipakai, produksi otomatis mencoba Ollama dengan evidence yang sama.

Build yang benar:

```text
rag-multilingual-v8-20260723
```

Untuk kasus uji P1, respons harus memuat:

```json
{
  "answer": "4 jam.",
  "generation_mode": "verified_scalar",
  "language": "ID",
  "failure_stage": null
}
```
