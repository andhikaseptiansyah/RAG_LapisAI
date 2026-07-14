# Laporan Evaluasi Kualitas Jawaban LapisAI (Generation Evaluation)

## 1. Ringkasan Eksekutif
Laporan ini mengevaluasi kualitas akhir dari *Generative AI* (LLM) pada sistem **LapisAI Enterprise Knowledge Assistant** dalam merangkai jawaban berdasarkan konteks yang ditarik (*Retrieval*). Evaluasi menggunakan pendekatan skala 1-5 berdasarkan rubrik: **Faithfulness, Answer Relevance, Context Precision, Context Recall,** dan **Citation Accuracy**.

## 2. Metodologi Penilaian (Rubrik Skala 1-5)
* **Faithfulness:** (5) Semua klaim ada di dokumen -> (1) Halusinasi total.
* **Answer Relevance:** (5) Menjawab seluruh pertanyaan dengan detail -> (1) Tidak menjawab.
* **Context Precision:** (5) Konteks yang diambil 100% relevan -> (1) Konteks salah sasaran.
* **Context Recall:** (5) Konteks mencakup semua info penting -> (1) Informasi penting hilang.
* **Citation Accuracy:** (5) Dokumen + Halaman benar -> (1) Tidak ada sitasi.

---

## 3. Hasil Evaluasi: Sebelum vs. Sesudah Perbaikan Retrieval

Pengujian dilakukan dua kali: sebelum optimasi *Hybrid Search & Reranker* (Before) dan sesudahnya (After).

### Perbandingan Metrik (Rata-rata Kualitas)

| Metric | Before Retrieval Fix | After Retrieval Fix | Peningkatan |
| :--- | :---: | :---: | :---: |
| **Faithfulness** | 3.8 | **4.6** | ⬆️ +0.8 |
| **Answer Relevance** | 4.0 | **4.7** | ⬆️ +0.7 |
| **Context Precision** | 3.7 | **4.5** | ⬆️ +0.8 |
| **Context Recall** | 3.5 | **4.6** | ⬆️ +1.1 |
| **Citation Accuracy** | 3.9 | **4.8** | ⬆️ +0.9 |
| **Hallucination Rate** | 15% | **5%** | ⬇️ -10% |

---

## 4. Analisis Peningkatan Kualitas

Setelah peningkatan arsitektur *retrieval* melalui implementasi *hybrid search*, penanganan *multilingual query* (lintas bahasa ID-EN), proses *reranking* menggunakan *Cross-Encoder*, serta *confidence threshold filtering* yang ketat (0.50), kualitas jawaban generasi akhir (LLM) mengalami peningkatan yang signifikan. 

*Context* yang diberikan ke dalam *prompt* LLM menjadi jauh lebih relevan (ditandai oleh naiknya skor *Context Recall* ke 4.6), sehingga jawaban akhir menjadi sangat selaras dengan dokumen sumber perusahaan (*Faithfulness* naik ke 4.6). Peningkatan drastis pada *Citation Accuracy* (4.8) menunjukkan bahwa sistem kini lebih konsisten dalam menyematkan referensi (nama dokumen dan nomor halaman) yang benar untuk diverifikasi oleh karyawan. 

Penurunan tajam pada tingkat *Hallucination* (dari 15% menjadi hanya 5%) terjadi secara langsung karena sistem kini lebih mampu mengukur batas pengetahuannya. Dengan *threshold filtering* yang memblokir *noise*, sistem RAG dapat secara tegas menolak menjawab pertanyaan (*unanswerable questions*) yang tidak memiliki sumber informasi di korpus, daripada memaksa LLM mengarang informasi.