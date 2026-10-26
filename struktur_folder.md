Web App MANTRA/
│
├── run.py                      Entry point: menjalankan website di http://localhost:5001
├── run_mantra.bat              Launcher double-click: menjalankan run.py di jendela sendiri
├── requirements.txt            Daftar library Python yang dibutuhkan aplikasi
├── requirements-dev.txt        Library tambahan untuk developer (pytest)
├── pytest.ini                  Pengaturan pytest (folder test, output ringkas)
├── .env                        Konfigurasi & SECRET asli (Power BI, Entra, Gemini). Tidak ada di GitHub
├── .env.example                Contoh isi .env beserta penjelasan setiap variabel
├── .gitignore                  Daftar file/folder yang tidak masuk git (.env, .venv, instance/, cache)
├── README.md                   Panduan utama: setup, menjalankan, menambah dashboard, troubleshooting
│
├── docs/
│   └── AUTH.md                 Dokumentasi login, role, hak akses, skema database, migrasi, backup & rollback
│
├── instance/                   DATA RUNTIME (dibuat otomatis, jangan dihapus)
│   └── mantra.db               Database SQLite: akun user, hak akses dashboard, audit log, Favorites, History
│
├── mantra/                     KODE APLIKASI WEBSITE (Flask)
│   ├── __init__.py             Merakit aplikasi (create_app): pasang semua modul, CSRF, header keamanan, halaman error
│   ├── config.py               Membaca .env lalu menjadikannya pengaturan aplikasi
│   ├── portal.py               Halaman Home, Reports, Favorites, History, Settings
│   ├── admin.py                Halaman Super Admin: kelola user, hak akses, katalog dashboard, audit log
│   │
│   ├── core/                   FONDASI BERSAMA (dipakai semua dashboard)
│   │   ├── __init__.py         Penanda package
│   │   ├── auth.py             Login (email+password / Microsoft), logout, lupa & ganti password, cek hak akses
│   │   ├── accounts.py         Logika akun: buat user, hash password, kunci akun, role, hak akses, audit log
│   │   ├── db.py               Koneksi SQLite, migrasi otomatis + backup, Favorites & History
│   │   ├── registry.py         Mendeteksi otomatis semua dashboard di folder dashboards/ dan memasang pengaman akses
│   │   ├── powerbi.py          Koneksi ke Power BI (token Microsoft + menjalankan query DAX), batas query per menit
│   │   ├── cache.py            Menyimpan hasil query sementara supaya Power BI tidak di-query berulang
│   │   ├── errors.py           Pesan error standar saat Power BI gagal (detail hanya ke log server)
│   │   ├── common.py           Helper kecil: zona waktu WIB, format waktu "Last Update", escape teks DAX, URL logo
│   │   ├── prompts/
│   │   │   └── base.md         Aturan umum untuk SEMUA AI agent
│   │   └── chat/               MESIN AI AGENT
│   │       ├── __init__.py     Penanda package
│   │       ├── routes.py       Endpoint chat /d/<dashboard>/api/chat + batas pertanyaan per user
│   │       ├── engine.py       Menjalankan satu pertanyaan: susun prompt, panggil AI, jalankan tools
│   │       ├── providers.py    Penghubung ke penyedia AI (Gemini + model cadangan)
│   │       ├── prompt.py       Membaca & memvalidasi file prompt, mengisi placeholder (tanggal, bulan, dll.)
│   │       └── guards.py       Memvalidasi parameter dari AI supaya tidak menjawab dari data yang salah
│   │
│   ├── dashboards/             DASHBOARD (1 folder = 1 report di portal)
│   │   ├── __init__.py         Penanda package
│   │   │
│   │   ├── _template/          KERANGKA dashboard baru (dipakai scripts/create_dashboard.py, tidak tampil di portal)
│   │   │   ├── __init__.py         Contoh manifest DASHBOARD
│   │   │   ├── queries.py          Contoh query ke Power BI
│   │   │   ├── routes.py           Contoh halaman
│   │   │   ├── tools.py            Contoh tool AI agent
│   │   │   ├── chat_cases.py       Contoh pertanyaan uji AI
│   │   │   ├── prompts/system.md, data_dictionary.md   Contoh prompt AI
│   │   │   ├── templates/__NAME__/overview.html        Contoh halaman HTML
│   │   │   └── static/.gitkeep     Supaya folder static kosong tetap ada di git
│   │   │
│   │   ├── material_readiness/ DASHBOARD MATERIAL READINESS (kesiapan material PO/SO per work order)
│   │   │   ├── __init__.py         Manifest: nama, URL, menu halaman, AI agent, warna kartu
│   │   │   ├── queries.py          Query DAX ke semantic model + olah filter + export
│   │   │   ├── routes.py           Halaman Summary (/), Detail (/detail), API data & export
│   │   │   ├── tools.py            Tool AI agent (chart, KPI, breakdown, baris data, lookup work order)
│   │   │   ├── chat_cases.py       Pertanyaan acuan untuk menguji AI agent
│   │   │   ├── prompts/system.md       Aturan khusus AI agent dashboard ini
│   │   │   ├── prompts/data_dictionary.md  Kamus tabel, kolom & istilah untuk AI
│   │   │   ├── templates/material_readiness/summary.html, detail.html   Tampilan halaman
│   │   │   └── static/summary.js, detail.js   Chart, slicer & tabel di browser
│   │   │
│   │   └── pani_processing/    DASHBOARD PANI (4 halaman: Processing, Equipment, Mining, Production)
│   │       ├── __init__.py         Manifest dashboard
│   │       ├── queries.py          Query DAX + perhitungan angka (direkonstruksi dari report Power BI)
│   │       ├── routes.py           4 halaman + filter tanggal dari URL
│   │       ├── tools.py            Tool AI agent (metrik, tren, equipment, mining, stockpile)
│   │       ├── chat_cases.py       Pertanyaan acuan untuk menguji AI agent
│   │       ├── prompts/system.md, data_dictionary.md   Aturan & kamus data AI agent
│   │       ├── templates/pani_processing/
│   │       │   ├── _ui.html        Komponen bersama: bar filter tanggal, ikon, script
│   │       │   └── processing.html, equipment.html, mining.html, production.html   Tampilan 4 halaman
│   │       └── static/pani.css, pani.js   Gaya & chart (sparkline, bar + garis)
│   │
│   ├── templates/              TAMPILAN HTML BERSAMA (Jinja)
│   │   ├── base.html           Kerangka SEMUA halaman: sidebar + top bar + area konten
│   │   ├── components/
│   │   │   ├── sidebar.html    Menu kiri (Home, Reports, Favorites, History, Settings, Admin)
│   │   │   └── topbar.html     Bar atas (breadcrumb, favorit, tombol Ask AI, user)
│   │   ├── portal/
│   │   │   ├── base.html           Kerangka halaman portal
│   │   │   ├── bare.html           Kerangka tanpa sidebar (ganti password wajib, error sebelum login)
│   │   │   ├── _auth_layout.html   Kerangka halaman login & lupa password
│   │   │   ├── _ui.html            Komponen: ikon, logo, kartu report
│   │   │   ├── home.html, reports.html, favorites.html, history.html, settings.html   Halaman portal
│   │   │   ├── login.html, forgot_password.html, change_password.html   Halaman akun
│   │   │   └── denied.html, error.html   Halaman "akses ditolak" & error umum
│   │   ├── admin/
│   │   │   ├── users.html, user_new.html, user_detail.html   Daftar, tambah & detail user
│   │   │   ├── temp_password.html  Menampilkan password sementara (sekali saja)
│   │   │   ├── dashboards.html     Katalog dashboard (aktif/nonaktif)
│   │   │   ├── audit.html          Audit log
│   │   │   └── _ui.html, _audit_table.html   Komponen: label role/status, tabel audit
│   │   └── dashboard/
│   │       ├── base.html       Kerangka halaman report: header biru, menu halaman, panel AI agent
│   │       ├── _icons.html     Ikon SVG untuk report
│   │       ├── empty.html      Halaman "belum ada data"
│   │       └── error.html      Halaman "gagal memuat data dari Power BI"
│   │
│   └── static/                 FILE BROWSER BERSAMA
│       ├── css/
│       │   ├── shell.css       Warna dasar, sidebar, top bar, loading (semua halaman)
│       │   ├── portal.css      Gaya halaman portal, login & admin
│       │   └── dashboard.css   Gaya isi report & panel AI agent
│       ├── js/
│       │   ├── shell.js        Sidebar ringkas/drawer, loading pindah halaman, tombol favorit
│       │   ├── portal.js       Pencarian & filter kategori di halaman Reports
│       │   ├── dash-common.js  Fungsi bersama halaman report (format angka, warna status, header)
│       │   └── chat.js         Panel AI agent: kirim pertanyaan & tampilkan jawaban
│       └── img/
│           └── mantra-mark.svg Logo MANTRA
│
├── scripts/                    PERINTAH MANUAL (bukan bagian website)
│   ├── README.md               Penjelasan setiap script
│   ├── manage_users.py         Kelola akun dari terminal: akun awal, reset password, role Super Admin, backup DB
│   ├── check_setup.py          Cek .env, login Microsoft, akses Power BI, API AI
│   ├── check_ai_agent.py       Uji AI agent (--static gratis; --dashboard pakai kuota Gemini)
│   ├── create_dashboard.py     Buat folder dashboard baru dari _template
│   └── compare_pani_with_powerbi.py   Bandingkan angka PANI di MANTRA dengan report Power BI asli
│
├── tests/                      TEST OTOMATIS (python -m pytest), bukan bagian website
│   ├── README.md               Penjelasan setiap file test
│   ├── conftest.py             Persiapan test: database sementara, akun dummy, blokir layanan luar
│   ├── test_login_and_access.py        Login, hak akses dashboard, halaman Admin, akun terkunci, CSRF
│   ├── test_passwords_and_database.py  Hash password, seed akun, migrasi & backup DB, log tanpa secret
│   ├── test_forgot_password.py         Alur lupa password
│   └── test_errors_and_security.py     Penanganan error, header keamanan, batas AI & data, cache
│
├── .venv/                      Python + semua library (dibuat: python -m venv .venv). Jangan dihapus
├── .pytest_cache/              Cache pytest (otomatis, boleh dihapus)
└── __pycache__/ (10 folder)    Bytecode Python (otomatis, boleh dihapus)

Urutan belajar yang saya rekomendasikan
01

Pahami struktur

Folder, file, fungsi, dan dependency.


02

Jalankan aplikasi

Python, .venv, requirements, .env, Flask, dan localhost.


03

Pelajari fondasi

Application factory, configuration, database, login, dan authorization.


04

Pelajari frontend

Jinja inheritance, sidebar, topbar, CSS, dan JavaScript.


05

Pelajari dashboard

Manifest, registry, routes, queries, Power BI, dan data contract.


06

Pelajari AI agent

Chat UI, engine, provider, prompt, tools, dan guards.


07

Praktik pengembangan

Ubah satu halaman, lalu buat halaman baru.


08

Praktik integrasi

Buat dashboard baru melalui mekanisme yang telah diverifikasi.


09

Validasi

Pytest, smoke test, security test, dan regression.


10

Dokumentasikan

Perbarui playbook, changelog, dan catatan known issues.