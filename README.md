# MANTRA: Multi-Agent Network for Tracking & Reporting Analytics

Nama yang tampil di website: **Power BI Portal** (seluruh tampilan berbahasa Inggris). MANTRA tetap dipakai sebagai
nama project, folder, dan package Python (`mantra/`).

Portal analitik grup PT Merdeka Copper Gold. Satu portal berisi banyak dashboard. Setiap dashboard punya semantic
model Power BI, tampilan, logika query, dan **AI agent** sendiri. User login dengan **email + password** (opsional
juga akun Microsoft), dan dashboard yang bisa dibuka setiap user diatur **Super Admin** di halaman Admin. Detail
login, role, hak akses, migrasi database, backup & rollback: [docs/AUTH.md](docs/AUTH.md).

```
Browser ── login email + password ──> MANTRA (users & hak akses di instance/mantra.db)
   │
   ▼
Flask MANTRA ── core/ (login, registry, cache, pembatas query, mesin AI agent)
   │
   ├── /d/material-readiness/  ── service principal mantra-powerbi ──> semantic model Material Readiness
   ├── /d/pani-processing/     ── service principal mantra-powerbi ──> semantic model PANI - PRCS - Processing
   └── /d/<slug>/api/chat      ── AI agent dashboard itu (Gemini; provider bisa diganti)
```

Data dashboard **tidak** disimpan di MANTRA; semuanya dibaca langsung dari semantic model lewat `executeQueries`.
File `instance/mantra.db` berisi akun, hak akses dashboard, audit log, Favorites, dan History.

## Status dashboard

| Dashboard | Slug | Akun awal yang diberi akses | Status |
|---|---|---|---|
| Material Readiness | `material-readiness` | `pbi_pro_a@merdeka.com` | Siap. Angka identik dengan project lama (66 perbandingan) dan 8 pertanyaan acuan AI agent lulus |
| PROCESSING, EQUIPMENT, MINING & STOCKPILE PRODUCTION (PANI) | `pani-processing` | `pbi_pro_b@merdeka.com` | Siap. 4 halaman (Processing, Equipment, Mining, Production) dari model "PANI - PRCS - Processing". Angka dibandingkan langsung dengan measure HTML report: `python scripts/compare_pani_with_powerbi.py` (272 sama, 76 beda karena bug di report). DAX perbaikan untuk report dulu ada di `docs/powerbi_fixes/` (sekarang dihapus dari working tree, masih ada di riwayat git: `git restore docs/powerbi_fixes`); dengan `--fixed` (19 measure) hasilnya 348/348 sama |

## Struktur folder

```
run.py                     server development (laptop)
wsgi.py, gunicorn.conf.py  server staging & production (gunicorn), lihat docs/DEPLOY_SERVER.md
mantra/
  __init__.py              create_app(), CSRF
  config.py                baca .env
  portal.py                Home, Reports, Favorites, History, Settings
  admin.py                 halaman Super Admin: Users, Dashboard Access, katalog Dashboards, Audit Log
  core/
    auth.py                login (email + password, Entra opsional), session, role_required, can_open
    accounts.py            users, hak akses dashboard, permintaan lupa password, katalog dashboard, audit log
    common.py, errors.py   helper bersama (WIB, dax_str, logo); respons error Power BI (pesan umum + kode ref)
    registry.py            daftar dashboard (auto-discovery) + kontrak Dashboard / ChatSpec / Tool
    powerbi.py             service principal, Dataset per dashboard, pembatas query bersama
    cache.py, db.py        cache query; koneksi SQLite + migrasi + backup, Favorites & History
    prompts/base.md        aturan umum SEMUA AI agent
    chat/                  mesin AI agent: engine, provider (Gemini), prompt loader, pengaman parameter
  templates/
    base.html              kerangka SEMUA halaman: sidebar + top bar + area konten (lihat "Layout" di bawah)
    components/            sidebar.html, topbar.html
    portal/                halaman portal (extend portal/base.html), login, ganti password
    admin/                 halaman Super Admin
    dashboard/             kerangka halaman report: header biru, AI agent (extend dashboard/base.html)
  static/
    css/                   shell.css (token warna + sidebar/top bar), portal.css, dashboard.css
    js/                    shell.js (sidebar, loading, favorit), portal.js, dash-common.js, chat.js
  dashboards/
    _template/             kerangka dashboard baru (dipakai scripts/create_dashboard.py)
    material_readiness/    __init__.py (manifest), queries.py, routes.py, tools.py, prompts/, templates/, static/,
                           chat_cases.py (pertanyaan acuan AI agent)
    pani_processing/       4 halaman PANI (Processing, Equipment, Mining, Production) + AI agent
docs/
  AUTH.md                  login, RBAC, skema database, migrasi, backup & rollback, daftar route
  DEPLOY_SERVER.md         untuk tim infra: gunicorn, systemd, reverse proxy, .env server, backup/restore, log
  PANDUAN_DEVELOPMENT_BERURUTAN.md  jalur membangun dari nol (fase 0-14), link file, output nyata setiap cek
  panduan_development/     pendalaman: konsep teknologi, kode inti, logika bisnis dashboard
  development_playbook/    buku panduan development lengkap (mulai dari 00_START_HERE.md)
  ebook/                   semua isi docs/ sebagai satu PDF (bangun ulang: python docs/ebook/build_ebook.py)
tests/                     pytest (python -m pytest), lihat tests/README.md
  conftest.py              persiapan test: database sementara, akun dummy, tanpa Power BI/AI asli
  test_login_and_access.py login, hak akses dashboard, halaman Admin, akun terkunci, CSRF
  test_passwords_and_database.py  hash password, seed akun, migrasi & backup database, log tanpa secret
  test_forgot_password.py  alur lupa password
  test_errors_and_security.py     penanganan error, header keamanan, batas AI & data, cache
  test_server_config.py    APP_ENV staging/production, proxy, lokasi data, WAL, /healthz, log, gunicorn
scripts/                   perintah manual (python scripts/<nama>.py), lihat scripts/README.md
  manage_users.py          akun awal (seed), buat user, hak akses, reset password, role, backup database
  check_setup.py           cek .env, Entra (opsional), akses tiap semantic model, AI
  check_ai_agent.py        tes AI agent (statis + pertanyaan acuan)
  create_dashboard.py      buat dashboard baru dari _template
  build_production.sh      paket production tanpa docs/tests (staging & production), lihat docs/DEPLOY_SERVER.md
  release.sh               rilis: staging dulu (scripts/release.sh staging), lalu live (scripts/release.sh live)
  compare_pani_with_powerbi.py    bandingkan angka dashboard PANI dengan measure report Power BI (14 skenario
                           filter); --fixed menguji DAX di docs/powerbi_fixes (pulihkan dulu dari git, lihat di atas)
```

## Setup (laptop baru / clone ulang)

### 1. Install

Perintah di README ini untuk **macOS (zsh)**, platform development project ini. Padanan perintah Windows/PowerShell
(untuk referensi saja) ada di [docs/development_playbook/04_MACOS_VSCODE_SETUP.md](docs/development_playbook/04_MACOS_VSCODE_SETUP.md).

| Software | Versi teruji (macOS 26, Apple Silicon) | Install | Cek |
|---|---|---|---|
| Git | 2.50 (Apple Git) | `xcode-select --install` | `git --version` |
| Homebrew | 7.0 | https://brew.sh | `brew --version` |
| Python | 3.13.x (Homebrew `python@3.13`) | `brew install python@3.13` | `python3.13 --version` |

```bash
cd ~/Documents/Portfolio
git clone https://github.com/mhdalfarisy/web-pbi-portal.git
cd web-pbi-portal
python3.13 -m venv .venv            # pakai python3.13 eksplisit, bukan "python3" (bisa menunjuk versi/venv lain)
source .venv/bin/activate           # prompt diawali (.venv)
pip install -r requirements.txt
cp .env.example .env                # lalu isi (lihat langkah 2-4)
```

`.env` **tidak ada di GitHub**: simpan salinannya di tempat aman. `instance/mantra.db` dibuat & dimigrasi otomatis
saat start (database lama di-backup dulu ke `instance/backups/`).

### 2. Akun login

```bash
export MANTRA_SEED_PASSWORD='<password sementara>'   # atau: python scripts/manage_users.py seed --generate
python scripts/manage_users.py seed                  # pbi_premium (Super Admin), pbi_pro_a, pbi_pro_b
unset MANTRA_SEED_PASSWORD
```

Setiap akun wajib mengganti password sementara saat login pertama. User lain dibuat Super Admin di **Admin > Users**.
Di `.env`: `AUTH_DISABLED=0`.

**Lupa password**: link **Forgot password?** di halaman login. User mengisi email, permintaannya muncul di
**Admin > Users** (badge merah di menu). Super Admin membuka user itu, klik **Reset password**, lalu memberikan password
sementara lewat saluran aman; user wajib menggantinya saat login. Portal tidak mengirim email. Halaman ini selalu
menampilkan pesan yang sama (email terdaftar atau tidak) dan dibatasi 5 permintaan / 15 menit per IP.

### 2b. Microsoft Entra (opsional): login dengan akun Microsoft (app registration `MANTRA Portal`)

Hanya untuk email yang sudah terdaftar & aktif di MANTRA; hak akses tetap dari database (app roles tidak dipakai).

1. entra.microsoft.com > App registrations > New registration: name `MANTRA Portal`, Single tenant,
   Redirect URI **Web** `http://localhost:5001/auth/callback` (port = `PORT` di `.env`, default 5001).
2. Catat Application (client) ID dan Directory (tenant) ID > `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`.
3. Certificates & secrets > New client secret > salin **Value** > `ENTRA_CLIENT_SECRET`.
4. Enterprise applications > MANTRA Portal > Properties > **Assignment required = Yes**, lalu Users and groups.

### 3. Microsoft Entra + Power BI: akses data (app registration `mantra-powerbi`)

1. New registration `mantra-powerbi` (Single tenant, tanpa redirect URI) > secret > `PBI_CLIENT_ID`,
   `PBI_CLIENT_SECRET`. Tenant sama, jadi `PBI_TENANT_ID` boleh kosong. Tidak perlu API permission.
2. Groups > `sg-powerbi-api` > Members > tambahkan `mantra-powerbi` (berlaku ~15 menit).
3. Power BI > setiap workspace dashboard > Manage access > tambahkan `mantra-powerbi` sebagai **Contributor**.

### 4. AI agent

`GEMINI_API_KEY` dari https://aistudio.google.com/apikey (key khusus MANTRA). Kosong = tombol "Ask AI" disembunyikan.
AI agent menjawab dalam bahasa pertanyaan user (default Inggris). Batas `CHAT_MAX_PER_MINUTE` pertanyaan per user.

### 5. Cek dan jalankan

```bash
python scripts/check_setup.py                 # semua harus OK (PANI menunggu akses workspace)
pip install -r requirements-dev.txt; python -m pytest   # tes login & hak akses (database sementara)
python scripts/check_ai_agent.py --static       # cek prompt semua AI agent (gratis)
python run.py                                 # buka http://localhost:5001 (bukan 127.0.0.1)
```

Semua perintah di atas memakai Python dari `.venv` (aktifkan dulu `source .venv/bin/activate`, atau panggil
`.venv/bin/python`). Python global tidak punya dependency-nya dan gagal dengan
`ImportError: cannot import name 'genai' from 'google'`.

Debugger Werkzeug + auto reload hanya aktif kalau `FLASK_DEBUG=1` di `.env` (default mati, karena debugger bisa
menjalankan kode di server). Kalau portal dibuka lewat HTTPS, `SESSION_COOKIE_SECURE=1` wajib.

Atau **double-click `run_mantra.command`** dari Finder. Server berjalan
di jendela Terminal sendiri, jadi tidak ikut berhenti kalau terminal VS Code ditutup, dan jendelanya tetap terbuka kalau
server berhenti supaya pesannya bisa dibaca. Kalau macOS menolak membukanya, klik kanan > Open sekali (atau
`chmod +x run_mantra.command`). Saat server berhenti, `run.py` selalu mencetak penyebabnya (Ctrl+C / terminal ditutup, atau crash).

**Mode development tanpa login**: `AUTH_DISABLED=1` di `.env` membuat siapa pun masuk sebagai Super Admin tanpa
akun. Untuk mencoba tampilan user biasa, pakai `AUTH_DISABLED=0` dan login sebagai `pbi_pro_a` / `pbi_pro_b`.
Jangan dipakai di production.

Foto latar halaman login (opsional): simpan sebagai `mantra/static/img/login-bg.jpg`. Kalau file tidak ada,
halaman login memakai gradien bawaan (tidak ada request 404).

## Menambah dashboard

```bash
python scripts/create_dashboard.py work-order "Work Order"
```

Lalu ikuti petunjuk yang dicetak:

1. Isi `workspace_id` & `dataset_id` di `mantra/dashboards/work_order/queries.py`.
2. Start Flask (dashboard otomatis masuk katalog), lalu beri akses user di **Admin > Users**.
3. Beri `mantra-powerbi` akses ke workspace-nya, lalu jalankan `check_setup.py`.
4. Bangun query (`queries.py`), halaman (`templates/`, `static/`), tool agent (`tools.py`), prompt (`prompts/`),
   dan pertanyaan acuan (`chat_cases.py`).
5. Ubah `ready=True` di `__init__.py`, lalu restart Flask.

Struktur model bisa dibaca langsung:
`python scripts/check_setup.py --dashboard work-order --dax "EVALUATE INFO.VIEW.COLUMNS()"`

## Layout

Semua halaman memakai `templates/base.html`, jadi sidebar MANTRA (Home, Reports, Favorites, History, Settings) dan
top bar selalu tampil, termasuk di halaman report. Report bukan iframe Power BI: halamannya dirender Flask dari data
semantic model, dan tampil di area konten di sebelah kanan sidebar.

```
base.html ── sidebar + top bar + <main class="content"> + loader
  ├── portal/base.html      Home, Reports, Favorites, History, Settings, error  (+ portal.css, portal.js)
  └── dashboard/base.html   halaman report: header biru, AI agent             (+ dashboard.css, dash-common.js)
```

- Di halaman report, menu **Reports** aktif, nama report tampil di bawahnya, dan top bar berisi breadcrumb
  `Reports › <report> › <halaman>` serta tombol bintang favorit.
- Sidebar: desktop (>= 1200px) bisa diringkas jadi ikon lewat tombol menu (pilihan disimpan di browser); tablet
  (900-1199px) selalu ringkas; mobile (< 900px) jadi drawer.
- Halaman report baru cukup `{% extends "dashboard/base.html" %}` dan mengisi blok `content` (opsional: `title`, `head`,
  `main_title`, `pill`, `desc`, `stat_note`, `scripts`). Breakpoint CSS isi report pakai `@container dash (...)`,
  bukan `@media`, supaya mengikuti lebar area report setelah sidebar.
- Warna, ukuran sidebar (`--sidebar-w`) dan tinggi top bar (`--topbar-h`) ada di `:root` pada `static/css/shell.css`.

## AI agent

Prompt setiap agent = `mantra/core/prompts/base.md` (aturan umum) + `mantra/dashboards/<nama>/prompts/*.md`
(`system.md` lebih dulu, lalu kamus data). Petunjuk placeholder ada di komentar bagian atas tiap file. Prompt dibaca
saat start, jadi **restart Flask** setelah mengubahnya. Salah ketik placeholder atau nama tool membuat aplikasi
gagal start dengan pesan yang jelas.

```bash
python scripts/check_ai_agent.py --static                          # semua agent, tanpa kuota AI
python scripts/check_ai_agent.py --dashboard material-readiness    # + pertanyaan acuan (pakai kuota)
```

Mengganti provider (mis. OpenAI): tambahkan class di `mantra/core/chat/providers.py` dengan method
`chat(system, history, message, tools, call_tool, max_rounds)`, daftarkan di `PROVIDERS`, lalu ubah `AI_PROVIDER`
di `.env`. Dashboard dan tools tidak perlu diubah.

## Kalau ada masalah

| Gejala | Solusi |
|---|---|
| "This Microsoft account is not registered or is inactive" | Login Entra butuh akun portal dengan email yang sama (Admin > Users) |
| "Your account has not been given access to Power BI Portal" | User belum di-assign di Enterprise applications > MANTRA Portal > Users and groups |
| Login berhasil tapi tidak ada dashboard | User belum diberi akses. Super Admin: Admin > Users > Manage > centang dashboard (langsung berlaku) |
| "Wrong email or password" terus | Akun mungkin terkunci 15 menit setelah 5 kali gagal. User bisa klik **Forgot password?**; Super Admin me-reset password |
| Lupa password Super Admin terakhir | `python scripts/manage_users.py reset-password --email <email>` di server (permintaan Forgot password butuh Super Admin lain) |
| `AADSTS50011` redirect URI mismatch | Buka lewat `http://localhost:5001`, dan pastikan redirect URI di app registration persis `http://localhost:5001/auth/callback` (port sama dengan `PORT` di `.env`) |
| Port 5001 sudah dipakai | `lsof -nP -iTCP:5001 -sTCP:LISTEN` untuk melihat prosesnya (server MANTRA lama → `kill <PID>`), atau ganti `PORT` di `.env` (mis. 5002) dan ubah juga redirect URI di Entra. Jangan pakai 5000: di macOS dipakai AirPlay Receiver |
| Dashboard "Could not load data from Power BI" | Cari kode referensi (ref) yang tampil di log server untuk detail error, lalu `python scripts/check_setup.py` |
| "The AI service is busy" | Kuota Gemini habis atau model penuh. Coba lagi, atau pakai API key khusus MANTRA |
| "Too many questions" di AI agent | Batas `CHAT_MAX_PER_MINUTE` per user tercapai; tunggu satu menit |
| Perubahan prompt tidak terbaca | Restart `python run.py` |
