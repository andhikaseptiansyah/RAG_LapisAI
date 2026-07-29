LapisAI Bilingual Evaluation Patch v11
======================================

Tujuan
------
Memperbaiki false refusal dan generation failure pada evaluasi Bahasa Indonesia,
serta tiga kegagalan Bahasa Inggris yang terjadi walaupun dokumen relevan sudah
berada di hasil retrieval.

Patch hanya mengganti 10 file terkait retrieval, answerability, evaluation, dan test.
Patch tidak mengubah dataset CSV, ChromaDB, dokumen, akun, password, .env, atau frontend.

Perbaikan utama
---------------
1. Context selection hanya menerima kandidat yang benar-benar lolos evidence dan
   answerability gate. Kandidat non-strict tidak lagi dapat menggusur bukti valid.
2. Ditambahkan natural English bridge untuk intent enterprise Bahasa Indonesia,
   antara lain calendar sharing, access card, parking, payroll, onboarding,
   phishing, lost laptop, software access, BYOD, password policy, dan travel.
3. Evidence verifier memahami bentuk kata Bahasa Indonesia seperti "mereset kata
   sandi" dan "mencabut akses".
4. Retrieval-debug menggunakan pipeline bilingual yang sama dengan chat.
5. Evaluasi mengunci snapshot kandidat retrieval sehingga satu model selalu
   dievaluasi dengan bukti yang sama dan tidak melakukan retrieval ulang diam-diam.
6. Override skor rendah dikalibrasi: hanya bukti literal yang sangat kuat yang
   boleh melewati score floor; kandidat generik tetap ditolak.
7. Build version menjadi rag-bilingual-eval-v11-20260729.

Pemasangan
----------
1. Hentikan backend dengan Ctrl+C.
2. Ekstrak ZIP patch ke folder biasa, jangan langsung menimpa project.
3. Jalankan PowerShell:

powershell -ExecutionPolicy Bypass -File .\apply_patch.ps1 `
  -ProjectRoot "C:\Users\ANDIKA\Downloads\RAG_LapisAI-main" `
  -RunTests

Jika pytest belum tersedia, jalankan tanpa -RunTests.

Menjalankan backend
-------------------
cd "C:\Users\ANDIKA\Downloads\RAG_LapisAI-main"

python -m uvicorn api.main:app `
  --host 127.0.0.1 `
  --port 8000 `
  --app-dir backend `
  --env-file .env

Verifikasi build
----------------
Invoke-RestMethod http://127.0.0.1:8000/health

Pastikan buildVersion:
rag-bilingual-eval-v11-20260729

Evaluasi ulang
--------------
PENTING: hapus hasil smoke lama agar retrieval_snapshot.json lama tidak digunakan.
Jangan gunakan -Resume pada run pertama setelah patch.

Remove-Item ".\evaluation\generation\results\ollama_smoke" `
  -Recurse -Force -ErrorAction SilentlyContinue

powershell -ExecutionPolicy Bypass `
  -File .\evaluation\run_ollama_evaluation.ps1 `
  -TopK 5 `
  -SkipLlmJudge `
  -OutputDir ".\evaluation\generation\results\ollama_smoke"

Jika smoke sudah baik, evaluasi final:

Remove-Item ".\evaluation\generation\results\ollama_final" `
  -Recurse -Force -ErrorAction SilentlyContinue

powershell -ExecutionPolicy Bypass `
  -File .\evaluation\run_ollama_evaluation.ps1 `
  -TopK 5 `
  -OutputDir ".\evaluation\generation\results\ollama_final"

Jika LLM judge belum dikonfigurasi, tambahkan -SkipLlmJudge pada evaluasi final.

Target pemeriksaan
------------------
- generation_failure_rate harus turun tajam dari 30%.
- ID generation_failure_rate harus turun dari 54%.
- ID false_refusal_rate harus turun dari 60%.
- EN-011, EN-027, EN-044 tidak boleh lagi kosong konteks.
- Pertanyaan unanswerable tetap harus ditolak tanpa sitasi.

Catatan
-------
Tidak ada patch yang dapat dijamin menghasilkan 100% sebelum dijalankan terhadap
ChromaDB dan model Ollama pada komputer target. Patch ini memperbaiki akar masalah
yang terlihat pada retrieval_snapshot.json dan generation_results_ollama.csv.
