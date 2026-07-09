# RAG Answer Quality Patch

Patch ini memperbaiki jawaban chatbot yang terlalu panjang, terlihat seperti copy-paste chunk, dan mudah halu saat konteks retrieval lemah.

File yang berubah:

- `api/answer_formatter.py` baru: formatter jawaban grounded, singkat, berbasis potongan kalimat dari chunk.
- `api/routes_chat.py`: endpoint `/chat` memakai formatter baru.
- `api/routes_compat.py`: endpoint `/api/chat` frontend lama memakai formatter baru.
- `retrieval/hybrid_search.py`: skor retrieval dinormalisasi 0-1, keyword search ikut membaca nama file, dan hasil lemah difilter.
- `src/services/chatService.ts`: confidence untuk tampilan chat dikonversi dari 0-1 menjadi persen.
- `src/hooks/useChat.ts`: confidence percakapan lama juga dikonversi dari 0-1 menjadi persen.

Efek setelah patch:

- Jawaban lebih pendek dan rapi dalam format Markdown.
- Chatbot tidak memaksakan jawaban ketika konteks dokumen tidak relevan.
- Sumber dokumen tetap ditampilkan.
- Confidence tampil 0-100%, bukan 0.8%.

Setelah replace file, restart backend dan frontend.

Backend:

```powershell
cd C:\Users\ANDIKA\Downloads\RAG_LapisAI\backend
python -m uvicorn api.main:app --host 127.0.0.1 --port 5000 --log-level debug
```

Frontend:

```powershell
cd C:\Users\ANDIKA\Downloads\RAG_LapisAI
npm run dev
```
