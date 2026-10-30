# 28 — Parity, Known Issues & Handover

## 1. Matriks fitur (referensi = aplikasi saat ini, 26 Okt 2026; diperbarui 28 Okt 2026 di macOS)

Belum ada aplikasi hasil rebuild, sehingga kolom "Perilaku rebuild" = NOT RUN. Matriks ini adalah daftar uji
yang harus dipenuhi rebuild atau perubahan besar berikutnya.

| Fitur | Perilaku referensi | Test | Expected | Actual (referensi) | Status rebuild | Gap / tindakan |
|---|---|---|---|---|---|---|
| Startup | Server di `localhost:5001`, migrasi otomatis | smoke dok 22 | `/login` 200 | PASS | NOT RUN | — |
| Login password | Lockout, throttle, pesan generik | `test_login_and_access.py` + uji `curl` 28 Okt | lulus; kunci di gagal ke-5, pesan "locked" di percobaan ke-6 | PASS | NOT RUN | — |
| Password sementara & ganti | Wajib ganti; sesi lain logout | idem | lulus | PASS | NOT RUN | — |
| Lupa password | Ke Super Admin, respons sama | `test_forgot_password.py` | lulus | PASS | NOT RUN | — |
| Login Microsoft | Hanya email terdaftar | manual | berhasil | NOT RUN | NOT RUN | Butuh tenant |
| RBAC dashboard | Default deny, 403 URL langsung/API/static/chat | `test_login_and_access.py` | lulus | PASS | NOT RUN | — |
| Admin | Users, akses, status, reset, dashboards, audit | idem | lulus | PASS | NOT RUN | — |
| Favorites / History | Toggle; riwayat 100, dedup 30 menit | sebagian (akses favorit) | — | PASS (sebagian) | NOT RUN | `Proposed`: test history dedup |
| CSRF & header keamanan | 400 tanpa token; 3 header | test + smoke | lulus | PASS | NOT RUN | — |
| Migrasi & backup | Tidak menghapus data | `test_passwords_and_database.py` | lulus | PASS | NOT RUN | — |
| Error Power BI disembunyikan | 502 + ref | `test_errors_and_security.py` | lulus | PASS | NOT RUN | — |
| Material Readiness data | Sama dengan report (README: 66 perbandingan identik) | manual | sama | NOT RUN (sesi ini) | NOT RUN | Butuh Power BI |
| PANI data | README: 272 sama, 76 beda karena bug report | `compare_pani_with_powerbi.py` | sesuai | NOT RUN (sesi ini) | NOT RUN | Butuh Power BI |
| PANI tanggal & data kosong | Clamp, halaman no-data | `test_errors_and_security.py` | lulus | PASS | NOT RUN | — |
| AI guard & limit | `valid_options`, error tool, 429 | idem | lulus | PASS | NOT RUN | — |
| AI prompt valid | Placeholder & tool | `check_ai_agent.py --static` | SEMUA LULUS | PASS | NOT RUN | — |
| AI jawaban (grounding) | Pertanyaan acuan MR (README: 8 lulus) & PANI (5) | `check_ai_agent.py --dashboard` | lulus | NOT RUN (sesi ini) | NOT RUN | Butuh kuota Gemini |
| Generator dashboard | 9 file, placeholder terganti, tolak overwrite | sandbox (26 & 28 Okt) | sesuai | PASS (salinan); pesan langkah 1 & 3 masih memakai `\` | — | issue 17 |
| Tampilan responsif | 3 mode sidebar | manual | sesuai | NOT RUN | NOT RUN | Tidak ada test visual |

**Parity tidak bisa dinyatakan 100%**: fitur yang bergantung pada Power BI, Gemini, dan Entra belum diuji di sesi ini.

## 2. Known issues register

| # | Issue | Dampak | Bukti | Rekomendasi |
|---|---|---|---|---|
| 1 | Dashboard `ready=False` tetap punya route aktif (dijaga `_guard`) | User berizin bisa membuka halaman yang belum siap lewat URL | Uji sandbox dok 17; 28 Okt: Super Admin membuka `/d/coba-data/` (`ready=False`, ID dataset `TODO`) → 502, bukan "Coming soon" | `Proposed`: `_guard` menolak (404) jika `not dashboard.ready`, kecuali Super Admin |
| 2 | Throttle IP, rate limit chat, rate limit Power BI, cache di memori per proses | Reset saat restart, tidak berlaku lintas proses | `auth.py`, `chat/routes.py`, `powerbi.py` | Memadai untuk dev; tinjau bila deploy |
| 3 | Tool `lookup` Material Readiness membaca semua branch (termasuk yang tidak tampil di dashboard) | Cakupan data AI > cakupan halaman | `tools.py` deskripsi tool | Keputusan pemilik data |
| 4 | Pertanyaan chat tidak masuk audit log | Tidak ada jejak penggunaan AI | `chat/routes.py` | `Proposed`: audit `chat_question` |
| 5 | Tidak ada validasi otomatis atas teks jawaban akhir AI | Angka di jawaban bisa salah walau tool benar | `engine.py` | Andalkan `chat_cases.py`; `Proposed`: cek angka jawaban vs hasil tool |
| 6 | Logo dari host luar `i.ibb.co.com` | Tergantung host luar | `dashboard/base.html`, data model | Simpan logo lokal (sebagian dari data Power BI) |
| 7 | `instance/backups/` kosong/tidak ada | Tidak ada titik rollback DB | `ls instance` | `python scripts/manage_users.py backup` |
| 8 | Banyak perubahan belum di-commit (audit, cleanup, rename, playbook; 28 Okt: konversi dokumentasi ke macOS, `run_mantra.command`, `PANDUAN_DEVELOPMENT_BERURUTAN.md`, `panduan_development/`, `docs/ebook/`, judul dashboard PANI; 31 Okt: hapus `run_mantra.bat` & import mati, path `/` di pesan/teks UI) | Risiko kehilangan / sulit review | `git status` | Commit bertahap per tujuan |
| 9 | `docs/powerbi_fixes/` dihapus belum di-commit; `--fixed` tidak bisa jalan | Tooling PANI | `compare_pani_with_powerbi.py` | Pulihkan atau hapus opsi `--fixed` |
| 10 | Server yang berjalan (PID di port 5001) start sebelum perubahan hari ini | Kode terbaru belum dimuat | `lsof -nP -iTCP:5001 -sTCP:LISTEN`, smoke test | Restart server |
| 11 | `prompt.load` hanya mendeteksi nama tool "tidak dikenal" berpola `get_*` / `lookup*` | Nama tool lain yang salah ketik di prompt tidak terdeteksi (tool yang tidak disebut tetap terdeteksi) | `prompt.py` regex | Namai tool dengan awalan `get_` |
| 12 | Tidak ada test JS / visual | Regresi UI tidak terdeteksi otomatis | `tests/` | `Proposed`: smoke test browser |
| 13 | Prefix `.env` PANI (`PANI_PROCESSING_*`) tidak tercantum di `.env.example` | Developer tidak tahu bisa override | `.env.example` | Tambahkan komentar |
| 14 | Nama model Gemini default (`gemini-3.5-flash` dst.) belum diverifikasi terhadap API di sesi ini | AI bisa gagal jika model tidak tersedia | `config.py` | `check_setup.py` |
| 15 | Halaman processing PANI hanya teruji di jalur "data kosong" | Render dengan data belum teruji otomatis | `test_errors_and_security.py` | Tambah stub data |
| 16 | Kegagalan login ke-5 (yang mengunci akun) masih berpesan "Wrong email or password."; pesan "locked" baru tampil di percobaan ke-6 | User tidak tahu akunnya sudah terkunci sampai mencoba sekali lagi | Uji `curl` sandbox 28 Okt (6x login gagal `pbi_pro_b`); `accounts.authenticate` mengembalikan `invalid` saat mengunci | `Proposed`: kembalikan `locked` saat kegagalan yang memicu kunci (cek dampak ke enumerasi email dulu) |
| 17 | `scripts/create_dashboard.py` mencetak path gaya Windows (`work_order\queries.py`, `python scripts\check_setup.py`) | Membingungkan di macOS | Output sandbox 28 Okt (dok 17) | `Fixed` 31 Okt 2026: pesan memakai `Path.as_posix()` / `/` |
| 18 | Saat membangun dari nol, pytest tidak bisa dijalankan sebelum mesin AI + kedua dashboard ada | Tahap awal rebuild tidak punya test otomatis | Error `conftest.py` (`chat.routes`) dan `test_errors_and_security.py` (modul PANI), diuji 28 Okt; dok 21 §C | Cek manual per fase (dok 03, PANDUAN); `Proposed`: test fondasi yang tidak bergantung pada dashboard |
| 19 | Judul dashboard PANI diubah di kode menjadi "PROCESSING, EQUIPMENT, MINING & STOCKPILE PRODUCTION" (belum di-commit) | Teks di kartu, breadcrumb, History, katalog ikut berubah | `mantra/dashboards/pani_processing/__init__.py:16` | Dokumentasi sudah disesuaikan (28 Okt); commit bersama perubahan kode |

## 3. Ringkasan handover

**Urutan belajar:** dok 00 → 01 → 02 → 22 → 07 → 08 → 09 → 14 → 15 → 21 → (sesuai tugas) 16/17/18/19/20.

**Checklist development harian**
- [ ] `.venv` aktif, `git status` dicek
- [ ] Baseline `python -m pytest` (58 passed)
- [ ] Pilih workflow (dok 26)
- [ ] Ubah sekecil mungkin; file fondasi → analisis dampak
- [ ] Test terkait → semua test; prompt/tools → `check_ai_agent.py --static`
- [ ] Restart server, smoke test, cek console & log
- [ ] Update dokumentasi terkait
- [ ] Commit tanpa `.env` / `instance/`

**Roadmap pekerjaan lanjutan (prioritas)**
1. Backup database sekarang (issue 7), lalu commit perubahan yang tertunda secara bertahap (issue 8, 19).
2. Restart server agar kode terbaru dipakai (issue 10).
3. Jalankan `check_setup.py`, `check_ai_agent.py --dashboard material-readiness` dan `pani-processing`,
   `compare_pani_with_powerbi.py` untuk melengkapi matriks parity (butuh akses & kuota).
4. Putuskan issue 1, 3, 9, 16, 17.
5. Tambah test: history dedup, render processing PANI dengan data stub, audit chat (jika disetujui).
