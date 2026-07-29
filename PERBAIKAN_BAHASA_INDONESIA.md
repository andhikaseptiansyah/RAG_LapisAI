# Catatan Perbaikan Jawaban Bahasa Indonesia

## Gejala

Pertanyaan Bahasa Indonesia yang sebenarnya memiliki jawaban di corpus dikembalikan sebagai:

> Informasi tersebut tidak ditemukan dengan bukti yang cukup pada dokumen yang telah diindeks.

Kasus utama menggunakan dokumen `FAQ_IT_Support.txt`, tetapi hasil chat berhenti pada `retrieval-refusal` sebelum jawaban dikirim ke Ollama.

## Penyebab

1. `ENABLE_EVIDENCE_VERIFICATION=false` membuat bukti kuat pada chunk tidak ikut menaikkan score.
2. Reranker menerima pertanyaan Bahasa Indonesia mentah, sedangkan corpus mayoritas berbahasa Inggris.
3. Query expansion belum mengenali pola `lupa password` dan `berapa lama maksimal prosesnya`.
4. Confidence lama terlalu bergantung pada literal keyword overlap, sehingga pertanyaan Indonesia terhadap sumber Inggris mudah ditolak.
5. `answer_formatter.py` membaca threshold langsung dari environment sebelum project `.env` dipastikan dimuat.
6. Alias pendek memakai substring matching; contoh `rpo` dapat salah terbaca pada kata `corporate`.

## File yang diperbaiki

- `.env`
- `.env.example`
- `backend/uploads/config.py`
- `backend/retrieval/query_expansion.py`
- `backend/retrieval/hybrid_search.py`
- `backend/retrieval/evidence_verifier.py`
- `backend/api/answer_formatter.py`
- `evaluation/test_retrieval_improvements.py`
- `evaluation/test_evidence_ground_truth.py`
- `evaluation/test_indonesian_answer_gate.py`

## Konfigurasi final

```env
MIN_RESULT_SCORE=0.30

ENABLE_RERANKER=true
RERANKER_CANDIDATES=30
RERANKER_WEIGHT=0.25

ENABLE_EVIDENCE_VERIFICATION=true
MIN_EVIDENCE_SCORE=0.45
EVIDENCE_WEIGHT=0.25

MIN_ANSWER_CONFIDENCE=0.56
MIN_SOURCE_CONFIDENCE=0.30
```

## Hasil regression test

```text
Retrieval metric tests passed.
Retrieval improvement tests passed.
Evidence verifier did not hard-reject any answerable ground-truth source set.
Indonesian password-reset answer gate passed: confidence=0.7603, source=FAQ_IT_Support.txt
```

## Catatan deployment

Perubahan query expansion dan confidence tidak membutuhkan reindex karena embedding model dan struktur chunk tidak berubah. Reindex hanya diperlukan apabila ChromaDB kosong/tidak lengkap atau corpus belum pernah diindeks di komputer yang digunakan.
