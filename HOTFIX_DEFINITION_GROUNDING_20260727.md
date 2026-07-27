# Hotfix Definition Grounding

Tanggal: 27 Juli 2026

## Masalah

Pertanyaan definisi seperti `what is SOP` dapat menghasilkan jawaban yang tidak didukung dokumen. Dokumen `SOP_Travel_Booking.pdf` hanya memuat aturan perjalanan, tetapi sistem menganggap kemunculan kata `SOP` pada judul sebagai bukti definisi. Akibatnya confidence naik dan sumber yang hanya mirip topik tetap ditampilkan.

## Akar masalah

1. Deteksi definisi menerima potongan teks yang sekadar memuat istilah.
2. Answerability belum mewajibkan bukti definisi eksplisit.
3. Grounding hanya memeriksa isi jawaban, tetapi belum membedakan antara tipe jawaban yang ada pada output dan tipe bukti yang tersedia pada dokumen.
4. Pembuat sitasi masih memiliki fallback ke sumber yang relevan secara topik saat tidak ada sumber yang mendukung klaim akhir.

## Perbaikan

- Pertanyaan definisi sekarang menghasilkan requirement `answer_definition`.
- Bukti harus memuat definisi eksplisit, misalnya:
  - `SOP stands for Standard Operating Procedure`;
  - `SOP adalah singkatan dari Standard Operating Procedure`;
  - `Standard Operating Procedure (SOP)`.
- Judul seperti `Nusantara Dynamics SOP - Travel Booking` dan label seperti `SOP (Travel Booking)` tidak dianggap sebagai definisi.
- Grounding menolak jawaban saat model menyebut definisi yang tidak tersedia pada bukti.
- Pruning tidak lagi mempertahankan sebagian jawaban jika tipe bukti utama tidak tersedia.
- Sitasi tidak ditampilkan bila tidak ada sumber yang benar-benar mendukung jawaban.
- Klaim relasional umum, seperti `SOP digunakan untuk mengatur proses bisnis`, memakai ambang dukungan yang lebih ketat.
- Padanan konsep remote work Indonesia-Inggris ditambahkan agar validasi sitasi bilingual yang benar tidak ikut terblokir oleh aturan yang lebih ketat.

## Perilaku setelah hotfix

Jika indeks hanya memuat dokumen perjalanan dan pengguna bertanya `what is SOP`, sistem harus mengembalikan refusal ter-grounding:

> Informasi tersebut tidak ditemukan dengan bukti yang cukup pada dokumen yang telah diindeks.

Hasil tersebut memakai confidence `0`, tanpa sumber, dan tidak memanggil model untuk menebak definisi dari pengetahuan umum.

Jika dokumen benar-benar memuat `Standard Operating Procedure (SOP)`, jawaban definisi tetap diperbolehkan dan sumbernya ditampilkan.

## Verifikasi

- 93 pengujian backend lulus.
- 4 subtest lulus.
- 1 pengujian lama tetap gagal karena mengharuskan `backend/api/routes_admin.py` tidak ada. File tersebut sudah tersedia pada arsip awal dan tidak terkait hotfix ini.
