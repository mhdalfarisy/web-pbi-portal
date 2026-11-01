# Alur Development Dashboard Picking Slip

Penjelasan tahapan development `mantra/dashboards/picking_slip/` di folder kerja **`web-pbi-portal`**: apa yang
dikerjakan di setiap tahap, file mana yang terlibat, dan kenapa dikerjakan begitu. Isinya penjelasan alur, tanpa kode.

Kelanjutannya (menaikkan hasil kerja ke staging dan live lewat folder `web-pbi-portal-dashboard`) ada di
**`PANDUAN_RILIS_PICKING_SLIP.md`**.

---

## 1. Gambaran besar

Picking Slip adalah **satu folder plug-in** di `mantra/dashboards/`. Website (Flask) menemukan folder ini sendiri saat
start, lalu otomatis:

- mendaftarkan alamat halamannya (`/d/picking-slip/`, `/d/picking-slip/detail`);
- memasang pengecekan login dan hak akses di setiap halamannya;
- menampilkan kartunya di halaman Reports dan sidebar;
- mencatatnya di database supaya Super Admin bisa memberi akses ke user.

Karena itu **tidak ada file inti (`mantra/core/`) yang diubah**. Semua pekerjaan ada di dalam folder `picking_slip/`,
ditambah test dan dokumentasi.

**Sumber data** bukan database SQL, melainkan **Power BI**: semantic model "All Site - SCM - Picking Slip" di workspace
ALLDATASET. Website mengirim query **DAX** lewat service principal `mantra-powerbi`. Database website (`mantra.db`) hanya
menyimpan akun, hak akses, dan log.

**Acuan tampilan** adalah dua measure HTML yang sudah dibuat di Power BI:

- `dax_picking_slip_summary_v9` → halaman **Summary**
- `dax_picking_slip_detail_header_v5` → halaman **Detail**

Setiap measure berisi tiga bagian: **data** (dibuat dengan DAX), **tampilan** (HTML + CSS), dan **logika**
(JavaScript untuk filter, grafik, dan tabel). Tugas development adalah memindahkan ketiganya ke struktur dashboard
MANTRA.

---

## 2. Peran setiap file

| File | Peran | Dipakai oleh |
|---|---|---|
| `__init__.py` | "KTP" dashboard: nama, kategori, ikon, warna, daftar halaman, AI agent | sistem plug-in website saat start |
| `queries.py` | semua query DAX ke Power BI, cache 10 menit, dan data rapi untuk AI | `routes.py`, `tools.py` |
| `routes.py` | alamat halaman: ambil data, lalu tampilkan template | website (Flask) |
| `templates/picking_slip/summary.html` | kerangka halaman Summary | `routes.py` |
| `templates/picking_slip/detail.html` | kerangka halaman Detail | `routes.py` |
| `templates/picking_slip/_ui.html` | potongan bersama: link CSS, data untuk browser, link JS | kedua halaman |
| `static/picking.css` | tampilan (warna, ukuran, tata letak) | browser |
| `static/picking.js` | logika di browser: filter, kartu KPI, grafik, tabel, tombol copy | browser |
| `tools.py` | fungsi yang boleh dipanggil AI agent (Ask AI) | mesin AI website |
| `prompts/system.md` | aturan untuk AI: pertanyaan apa memakai tool apa | mesin AI website |
| `prompts/data_dictionary.md` | kamus data untuk AI: tabel dan istilah | mesin AI website |
| `chat_cases.py` | pertanyaan uji untuk memeriksa jawaban AI | script uji AI |

Ada **dua jalur kerja** yang bertemu di `queries.py`:

```text
Jalur halaman :  browser → routes.py → queries.py → Power BI → template → picking.css + picking.js → tampil
Jalur AI      :  Ask AI  → mesin AI → tools.py   → queries.py (data yang sama)  → jawaban
```

Karena keduanya memakai data yang sama, angka yang dijawab AI selalu sama dengan angka di layar.

---

## 3. Alur saat halaman dibuka

```text
User membuka /d/picking-slip/
   │
   ├─ 1. Website cek: sudah login? punya akses Picking Slip?        (otomatis, dari sistem plug-in)
   ├─ 2. routes.py memanggil queries.py untuk data halaman
   ├─ 3. queries.py: data masih di cache (< 10 menit)?
   │        ya    → langsung dipakai
   │        tidak → kirim query DAX ke Power BI, simpan ke cache
   ├─ 4. routes.py menyusun halaman dari template + data (dalam bentuk JSON)
   ├─ 5. Browser menerima halaman, lalu mengunduh picking.css dan picking.js
   └─ 6. picking.js membaca data → mengisi filter → menghitung kartu KPI → menggambar grafik & tabel

User memilih filter
   └─ picking.js menghitung ulang dan menggambar ulang di browser (tidak bertanya ke server lagi)
```

Server hanya bekerja **sekali** per halaman. Semua filter dikerjakan browser, sehingga terasa instan.

---

## 4. Tahapan development

### Tahap 0: Siapkan lingkungan kerja

**Tujuan:** memastikan titik awal bersih sebelum mengubah apa pun.

- Buka folder `web-pbi-portal`, pindah ke branch `develop`, ambil versi terbaru dari GitHub, aktifkan virtual
  environment Python.
- Jalankan semua test dan buka website lokal (`python run.py`, `http://localhost:5001`).

**Kenapa:** kalau ada yang rusak sebelum mulai, kamu tahu itu bukan akibat perubahanmu.

### Tahap 1: Pahami kebutuhan & sumber data

**Tujuan:** tahu persis apa yang mau ditampilkan dan dari mana datanya.

- Kumpulkan: link semantic model, nama measure halaman (Summary dan Detail), dan screenshot report Power BI.
- Dari link semantic model, catat **workspace ID** (setelah `groups/`) dan **dataset ID** (setelah `modeling/`).
- Minta `mantra-powerbi` ditambahkan sebagai **Contributor** di workspace itu. Tanpa ini, website tidak bisa membaca
  data (`Not Authorized`).

**Hasil:** workspace ALLDATASET, model "All Site - SCM - Picking Slip", dan dua measure acuan.

### Tahap 2: Ambil dan pelajari kode measure

**Tujuan:** mendapatkan "resep" lengkap kedua halaman.

- Isi measure tidak bisa dibaca lewat API biasa, karena teksnya disembunyikan. Yang bisa adalah **definisi model**
  lewat Fabric API (`getDefinition`), memakai service principal yang sama.
- Pelajari isinya:
  - bagian **data**: variabel-variabel `CONCATENATEX` (6 di Summary, 9 di Detail) yang menggabungkan baris tabel
    menjadi teks panjang;
  - bagian **tampilan**: `<style>` dan `<body>`;
  - bagian **logika**: `<script>`.

**Temuan penting:** measure Detail **gagal** di Power BI tanpa filter. Teks datanya sekitar 2,2 juta karakter,
sedangkan batas teks DAX sekitar 2,1 juta. Jadi measure tidak bisa dipakai apa adanya; datanya harus diambil dengan
cara lain (tahap 4).

### Tahap 3: Buat kerangka dashboard

**Tujuan:** mendapatkan folder dashboard dengan struktur standar.

- Jalankan `scripts/create_dashboard.py picking-slip "Picking Slip"`. Script menyalin `_template/` menjadi folder
  `picking_slip/` dengan semua file standar.
- Hapus file contoh yang tidak dipakai (`overview.html`, `static/.gitkeep`).

**Kenapa memakai generator:** strukturnya otomatis sama dengan dashboard lain (PANI, Material Readiness), sehingga
developer lain langsung paham.

### Tahap 4: Data (`queries.py`)

**Tujuan:** data yang **sama persis** dengan measure, tanpa terkena batas 2,1 juta karakter.

- Setiap variabel `CONCATENATEX ( tabel, teks satu baris, pemisah )` di measure diubah menjadi **query tabel biasa**
  dengan tabel dan rumus teks yang sama. Power BI mengembalikan satu baris per data, lalu Python yang menggabungkannya.
- Bagian measure yang hanya untuk "membungkus" teks ke dalam JavaScript (escape karakter) dibuang, karena data
  dikirim sebagai JSON.
- Semua DAX diketik di `queries.py`: dikelompokkan `SUMMARY` (6 query) dan `DETAIL` (9 query), plus jumlah company.
- Data disimpan di **cache 10 menit**, supaya Power BI tidak ditanya ulang setiap halaman dibuka.

**Cek wajib:** jalankan setiap query dan bandingkan dengan output measure asli. Untuk Picking Slip, **15 dari 15
kumpulan data identik** (contoh: 19.654 baris Summary, 13.658 baris Detail).

### Tahap 5: Alamat halaman (`routes.py`)

**Tujuan:** menghubungkan URL dengan data dan template.

- Dua alamat: `/d/picking-slip/` → Summary, dan `/d/picking-slip/detail` → Detail.
- Satu fungsi bantu dipakai keduanya: ambil data dari `queries.py`; kalau Power BI gagal, tampilkan halaman "Could not
  load data" lengkap dengan kode referensi untuk mencari error di log; kalau berhasil, tampilkan template.
- Login dan hak akses **tidak ditulis di sini**, karena sudah dipasang otomatis oleh sistem plug-in.

### Tahap 6: Template halaman

**Tujuan:** memindahkan `<body>` measure ke kerangka halaman MANTRA.

- Halaman memakai kerangka report bersama MANTRA (header biru, menu halaman, panel AI), bukan header milik measure.
  Desain dan ID elemen kedua header ternyata sama, jadi JavaScript measure tetap bekerja.
- Pembungkus `.dash` milik measure diganti pembungkus halaman: `ps-sum` (Summary) dan `ps-det` (Detail).
- Elemen yang berada **setelah** pembungkus `.dash` (kotak "Press Ctrl+C to copy" di Detail) tetap dimasukkan ke dalam
  pembungkus. Kalau tidak, kotak itu tampil di bawah tabel.
- `_ui.html` berisi potongan yang dipakai kedua halaman: link CSS, data untuk browser (dikirim sebagai JSON yang
  aman), dan link JS.

### Tahap 7: Tampilan & logika (`picking.css`, `picking.js`)

**Tujuan:** tampilan dan perilaku sama persis dengan measure, tanpa merusak bagian lain website.

**CSS:**
- diambil dari `<style>` kedua measure;
- semua aturan **dibatasi** ke pembungkus halaman (`ps-sum` / `ps-det`), supaya sidebar dan top bar MANTRA tidak
  berubah;
- aturan header dan `body` milik measure dibuang;
- karena CSS MANTRA memakai nama class yang sama (desainnya memang sama), ditambahkan aturan **pembatal**. Tanpa
  pembatal, filter Summary menyempit ke tengah.

**JavaScript:**
- diambil dari `<script>` kedua measure;
- setiap tempat measure menyisipkan data dari DAX diganti membaca data JSON dari server;
- JS kedua halaman digabung dalam satu file, lalu dijalankan sesuai halaman yang sedang dibuka;
- ditambah fungsi kecil yang memberi tahu AI agent halaman mana yang sedang dibuka;
- alamat logo `i.ibb.co` diganti `i.ibb.co.com` (aturan MANTRA, karena alamat lama diblokir di beberapa jaringan).

### Tahap 8: Manifest (`__init__.py`)

**Tujuan:** mendaftarkan dashboard ke website.

- Diisi: slug `picking-slip`, judul, deskripsi, kategori **Supply Chain**, ikon truk, warna oranye, dua halaman
  (Summary, Detail), urutan kartu, dan pengaturan AI agent.

**Hasil:** setelah website dijalankan ulang, kartu oranye **Picking Slip** muncul di halaman Reports.

### Tahap 9: AI agent (Ask AI)

**Tujuan:** user bisa bertanya dalam bahasa biasa dan mendapat angka yang sama dengan layar.

- **Data untuk AI** di `queries.py`: teks data yang sama dengan halaman diubah menjadi baris-baris rapi (19.654 baris
  Summary, 13.658 baris Detail), lengkap dengan nama company, status, dan WO.
- **4 tool** di `tools.py`:
  - ringkasan per status, kartu KPI, dan company;
  - top item;
  - cari picking slip;
  - detail satu picking slip.
- **Pembersih input AI**: misalnya "batutua tembaga" dikenali sebagai `BTR`, dan "backorder" sebagai `Backorder`.
  Nilai yang tidak dikenal ditolak dengan daftar pilihan yang valid.
- **Prompt**: `system.md` (tool mana untuk pertanyaan apa, aturan menghitung) dan `data_dictionary.md` (istilah).
  Setiap tool wajib disebut di prompt; kalau lupa, website menolak start, jadi kesalahan langsung ketahuan.
- **Pertanyaan uji** di `chat_cases.py`: jumlah backorder, top item, detail PS, dan pertanyaan di luar topik.

**Kenapa AI tidak menulis DAX sendiri:** supaya angkanya pasti benar dan aman. AI hanya boleh memanggil tool yang sudah
disiapkan.

### Tahap 10: Test

**Tujuan:** memastikan fitur baru benar dan fitur lama tidak rusak.

- Test baru `tests/test_picking_slip.py` (8 test):
  - DAX ada di `queries.py`
  - data digabung dengan benar
  - kedua halaman memakai header MANTRA dan data yang aman
  - halaman butuh login dan akses
  - tool AI menjawab dari data dan menolak nilai asing
- Dua test lama diperbarui karena jumlah dashboard bertambah dari 2 menjadi 3. Ini **disengaja**: test lama
  "mengunci" jumlah dashboard, jadi ikut diubah saat dashboard ditambah.

### Tahap 11: Uji di laptop

**Tujuan:** melihat hasil akhir dengan data asli sebelum menyimpan.

- Jalankan semua test (85 lulus) dan cek statis AI agent (lulus).
- Uji AI ke Gemini sungguhan dengan 4 pertanyaan uji (lulus).
- Buka kedua halaman di browser dan cek:
  - header dan judul benar
  - filter penuh dari kiri ke kanan
  - kartu, grafik, dan tabel terisi dan berubah saat filter dipilih
  - tidak ada error di Console browser (F12)
  - tombol Ask AI menjawab
  - dashboard lain tetap normal

### Tahap 12: Dokumentasi

**Tujuan:** developer lain tahu dashboard ini ada dan cara mengujinya.

- `README.md`: baris Picking Slip di tabel status dashboard, struktur folder, dan daftar test.
- `struktur_folder.md`: penjelasan folder `picking_slip/` dan file test-nya.
- `tests/README.md`: isi `test_picking_slip.py`.

### Tahap 13: Simpan ke Git & GitHub

**Tujuan:** perubahan tercatat dan ter-backup.

- Cek file yang berubah, simpan semua sebagai satu commit dengan pesan yang jelas, lalu kirim ke GitHub
  (`mhdalfarisy/web-pbi-portal`, branch `develop`).

**Setelah ini:** naikkan ke staging dan live mengikuti **`PANDUAN_RILIS_PICKING_SLIP.md`**.

### Tahap 14: Beri akses user (setelah live)

- Dashboard baru hanya bisa dibuka **Super Admin**. User lain diberi akses lewat **Admin → Users → Manage → centang
  Picking Slip → Save access**. Akses di staging dan live diatur terpisah.

---

## 5. Masalah yang ditemui & solusinya

| Masalah | Penyebab | Solusi |
|---|---|---|
| Isi measure tidak bisa dibaca | API biasa menyembunyikan teks measure | ambil definisi model lewat Fabric API (tahap 2) |
| Measure Detail gagal di Power BI | teks data melebihi batas DAX sekitar 2,1 juta karakter | ambil data per tabel, gabung di Python (tahap 4) |
| Akses Power BI ditolak | `mantra-powerbi` belum anggota workspace | tambahkan sebagai Contributor (tahap 1) |
| Filter Summary menyempit ke tengah | CSS MANTRA dengan nama class sama ikut berlaku | aturan pembatal di CSS (tahap 7) |
| Kotak "Press Ctrl+C to copy" tampil di bawah tabel | elemen itu terpotong keluar pembungkus halaman | potong HTML dengan menghitung pasangan `<div>` (tahap 6) |
| Halaman Detail error setelah merapikan DAX | satu baris DAX tertulis dua kali | jalankan semua query setiap selesai mengubah `queries.py` (tahap 4) |
| Satu logo header tidak tampil | alamat `i.ibb.co` diblokir di beberapa jaringan | ganti ke `i.ibb.co.com` (tahap 7) |
| Test lama gagal (`3 == 2`) | jumlah dashboard bertambah | perbarui 2 test lama (tahap 10) |

---

## 6. Kalau measure di Power BI berubah

1. Ambil ulang kode measure (tahap 2).
2. Bagian data berubah → sesuaikan DAX di `queries.py`, lalu bandingkan lagi hasilnya dengan measure (tahap 4).
3. Tampilan atau logika berubah → pindahkan ulang bagian yang berubah ke template, CSS, atau JS (tahap 6–7).
4. Lanjutkan test, uji di laptop, simpan, dan rilis (tahap 10–13, lalu panduan rilis).
