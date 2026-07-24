# Perubahan Jawaban RAG V10

Versi build: `rag-bilingual-grounding-v10-20260724`

## Perilaku baru

- Jawaban dimulai dengan fakta yang langsung menjawab pertanyaan.
- Jika dokumen memiliki penjelasan pendukung, model menyusunnya menjadi paragraf
  2–4 kalimat tanpa menambah pengetahuan dari luar dokumen.
- Sistem mencoba memakai sedikitnya dua konteks yang kuat, relevan, dan tidak
  berulang. Jika konteks kedua tidak relevan, sistem tidak memaksakannya.
- Hingga tiga sumber dapat dikembalikan dan ditampilkan pada panel sitasi.
- Pertanyaan nilai tunggal tetap memiliki fallback deterministik. Jika model
  gagal atau salah bahasa, angka yang telah diverifikasi masih dapat diberikan
  tanpa halusinasi.
- Kalimat penutup generik di bawah jawaban dihapus. Hanya pertanyaan lanjutan
  yang benar-benar dibentuk dari dataset yang akan ditampilkan.
- Validator grounding sekarang mengenali parafrasa bilingual untuk masa
  percobaan, evaluasi kinerja, pengakuan insiden, dan eskalasi insiden.
- Klausa bersyarat seperti "jika belum diselesaikan dalam 2 jam" tidak lagi
  dipotong menjadi fragmen yang kemudian salah ditolak.

## Contoh target

Pertanyaan:

> Berapa nilai RTO dan RPO pada rencana pemulihan bencana?

Jika bukti mendukung nilai dan definisinya, bentuk jawaban yang diharapkan:

> Rencana pemulihan bencana menetapkan RTO 4 jam dan RPO 1 jam. RTO menunjukkan
> batas waktu pemulihan layanan setelah gangguan, sedangkan RPO menunjukkan batas
> kehilangan data yang masih dapat diterima.

Kalimat kedua hanya boleh muncul jika pengertian tersebut benar-benar ada pada
konteks yang lolos verifikasi.

## Hasil validasi

- Tes khusus perilaku jawaban panjang dan multi-sumber: lulus.
- TypeScript `--noEmit`: lulus.
- Build produksi Vite: lulus.
- Seluruh suite: 142 tes lulus; satu tes lama terkait keberadaan
  `backend/api/routes_admin.py` masih gagal dan tidak berhubungan dengan perubahan
  generasi jawaban ini.
