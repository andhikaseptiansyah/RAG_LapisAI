# Query Logs Detail Frontend Patch

Patch ini menghubungkan halaman `Query Logs Detail` ke backend endpoint:

- `GET /api/admin/query-logs/dashboard?range=daily&page=1&limit=25`

Perubahan utama:

1. Menghapus data dummy/hardcoded dari `AdminQueryLogsDetail.tsx`.
2. Menambahkan fetch data real melalui `getQueryLogsDashboard()`.
3. Menampilkan loading state, error state, empty state, refresh button, pagination, selected log detail, retrieved documents, confidence, response time, dan performance summary dari response backend.
4. Format timestamp dibuat kompatibel dengan timestamp ISO dari backend Python/FastAPI.

Cara pakai:

1. Extract ZIP ini ke folder project React `RAG_LapisAI`.
2. Replace file `src/components/AdminQueryLogsDetail.tsx`.
3. Pastikan backend Python alias jalan di port 5000.
4. Jalankan frontend dengan `npm run dev`.
5. Buat minimal satu chat dari `/api/chat`, lalu buka menu Query Logs Detail.

Endpoint backend yang dibutuhkan:

- `GET /api/admin/query-logs/dashboard`
- `GET /api/admin/query-logs`

Kalau halaman kosong, biasanya belum ada query log. Jalankan chat dulu agar backend membuat log.
