# 02 — Project Structure & File Inventory

Status per 26 Oktober 2026. `Verified` = isi file dibaca. `Tested` = perilakunya dicakup test yang lulus
(`python -m pytest`, 58 passed) atau uji runtime di sesi ini. Test disebut dengan nama file di `tests/`.

## Struktur

```
Web App MANTRA/
├── run.py · run_mantra.bat · requirements.txt · requirements-dev.txt · pytest.ini
├── .env (secret, tidak di git) · .env.example · .gitignore · README.md
├── docs/            AUTH.md · development_playbook/
├── instance/        mantra.db (runtime) · backups/ (dibuat otomatis saat migrasi / backup manual)
├── mantra/          aplikasi Flask
│   ├── __init__.py · config.py · portal.py · admin.py
│   ├── core/        auth · accounts · db · registry · powerbi · cache · errors · common · prompts/base.md · chat/
│   ├── dashboards/  _template/ · material_readiness/ · pani_processing/
│   ├── templates/   base.html · components/ · portal/ · admin/ · dashboard/
│   └── static/      css/ · js/ · img/
├── scripts/         manage_users · check_setup · check_ai_agent · create_dashboard · compare_pani_with_powerbi
├── tests/           conftest · test_login_and_access · test_passwords_and_database · test_forgot_password · test_errors_and_security
└── .venv/ · __pycache__/ · .pytest_cache/   (generated)
```

## Tingkat risiko file

| Tingkat | File | Aturan |
|---|---|---|
| **Fondasi** (analisis dampak dulu) | `mantra/__init__.py`, `config.py`, `core/auth.py`, `core/accounts.py`, `core/db.py`, `core/registry.py`, `core/powerbi.py`, `core/cache.py`, `core/errors.py`, `core/chat/*.py`, `core/prompts/base.md`, `templates/base.html`, `templates/components/*`, `templates/dashboard/base.html`, `static/css/shell.css`, `static/js/shell.js`, `static/js/chat.js`, `tests/conftest.py` | Dipakai semua halaman/dashboard. Jalankan seluruh test + cek semua dashboard |
| **Sering diubah** (harian) | `dashboards/<x>/queries.py`, `routes.py`, `tools.py`, `prompts/*.md`, `chat_cases.py`, `templates/<x>/*.html`, `static/*` dashboard, `templates/portal/*.html`, `static/css/portal.css`, `static/css/dashboard.css` | Dampak terbatas pada satu dashboard / halaman |
| **Operasional** | `scripts/*.py`, `.env`, `docs/*` | Tidak memengaruhi runtime website (kecuali `.env`) |

---

## A. Root

| Path | Status | Fungsi utama | Isi & tanggung jawab | Input | Output | Dependency | Dipanggil oleh | Berkaitan dengan | Test terkait | Kapan diubah | Risiko perubahan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `run.py` | Verified, Tested (server berjalan di 5001) | Entry point | `app = create_app()`; `app.run(host="localhost", port=Config.PORT, debug=Config.DEBUG)`; cetak status login/debug dan penyebab server berhenti | `.env` lewat `Config` | Dev server Werkzeug | `mantra.create_app`, `Config` | Developer, `run_mantra.bat` | Semua | — | Jarang (mis. pesan startup) | Host/port salah → redirect Entra gagal |
| `run_mantra.bat` | Verified | Launcher double-click | `cd` ke folder, cek `.venv\Scripts\python.exe`, jalankan `run.py`, `pause` | — | Jendela server | `.venv`, `run.py` | User (Explorer) | Startup | — | Jarang | Path venv berubah → gagal start |
| `requirements.txt` | Verified | Dependency runtime | Flask, msal, requests, python-dotenv, google-genai, httpx (dengan batas atas versi mayor) | — | — | pip | `pip install -r` | Semua | Seluruh pytest | Tambah library baru | Upgrade mayor bisa merusak API |
| `requirements-dev.txt` | Verified | Dependency dev | `-r requirements.txt` + pytest | — | — | pip | Developer | Test | — | Tambah tool dev | Rendah |
| `pytest.ini` | Verified | Konfigurasi pytest | `testpaths = tests`, `addopts = -q` | — | — | pytest | `python -m pytest` | Test | — | Jarang | Test tidak ditemukan |
| `.env` | Existing (isi tidak dibaca: secret) | Konfigurasi & secret asli | Nilai variabel | — | Environment | python-dotenv | `config.py` | Semua | — | Setup / ganti kredensial | Secret bocor jika di-commit |
| `.env.example` | Verified | Template `.env` | 23 variabel + penjelasan | — | — | — | Developer | Setup | `test_passwords_and_database` (perilaku `.env`) | Variabel baru di `config.py` | Dokumentasi tidak sinkron |
| `.gitignore` | Verified | Pengecualian git | `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `instance/`, `.claude/`, `.pytest_cache/` | — | — | git | git | Keamanan | — | Folder runtime baru | Secret/DB ikut ter-commit |
| `README.md` | Verified | Panduan utama | Setup, struktur, menambah dashboard, layout, AI, troubleshooting | — | — | — | Developer | Semua | — | Perubahan perilaku/command | Panduan menyesatkan |

## B. `mantra/` (aplikasi)

| Path | Status | Fungsi utama | Isi & tanggung jawab | Input | Output | Dependency | Dipanggil oleh | Berkaitan dengan | Test terkait | Kapan diubah | Risiko perubahan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `mantra/__init__.py` | Verified, Tested | Application factory | `create_app(test_config)`: config, `db.init_app`, register blueprint `auth`/`portal`/`chat`/`admin`, `registry.init_app`, `accounts.sync_dashboards`; `before_request` CSRF; `after_request` header keamanan; `context_processor` (`csrf_token`, `current_user`, `dashboard`, `chat_enabled`, `report_favorite`, `pending_resets`); error handler 400/404/500 | `Config`, `test_config` | Objek Flask | semua modul core | `run.py`, `tests/conftest.py`, scripts | Semua | `test_errors_and_security` (`create_app` dua kali, header, CSRF non-ASCII, 404), `test_login_and_access` (CSRF) | Blueprint/hook global baru | **Tinggi**: semua request |
| `mantra/config.py` | Verified, Tested | Konfigurasi | Baca `.env` (`override=True`, `.env` menang atas env terminal), `AUTH_DISABLED` hanya dari file `.env`, class `Config` | `.env`, `os.environ` | `Config`, `ENV_OVERRIDDEN` | python-dotenv | `__init__`, `powerbi`, `auth`, `providers`, `chat/routes`, queries | Semua | `test_passwords_and_database` (`auth_disabled...`, `env_file_wins...`) | Variabel baru | Tinggi: default salah |
| `mantra/portal.py` | Verified, Tested | Halaman portal | Blueprint `portal`: `/`, `/reports`, `/favorites`, `/history`, `/settings`, `POST /api/favorites/<slug>` | session, DB, registry | HTML / JSON | `auth`, `db`, `registry`, `providers` | Browser | Home, Reports, ... | `test_login_and_access` | Halaman portal baru | Sedang |
| `mantra/admin.py` | Verified, Tested | Halaman Super Admin | Blueprint `admin` (`/admin/...`): users, new user, detail, access, status, reset password, dismiss reset, dashboards, audit. Semua `@admin_required` | form, DB | HTML / redirect 303 | `accounts`, `registry`, `auth` | Browser | Admin | `test_login_and_access`, `test_forgot_password` | Fitur admin baru | Tinggi (keamanan) |

## C. `mantra/core/`

| Path | Status | Fungsi utama | Isi & tanggung jawab | Input | Output | Dependency | Dipanggil oleh | Berkaitan dengan | Test terkait | Kapan diubah | Risiko perubahan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `core/auth.py` | Verified, Tested | Login & otorisasi | Blueprint `auth`: `/login`, `/forgot-password`, `/account/password`, `/auth/microsoft`, `/auth/callback`, `POST /logout`. `current_user()` (baca ulang DB tiap request, cek `session_version`), `can_open`, `login_required`, `role_required`/`admin_required`, `require_password_change` (before_app_request), throttle per IP, `_safe_next` | form, session, Entra | session, redirect | `accounts`, msal, `Config` | Semua blueprint, registry | Login, semua halaman | `test_login_and_access`, `test_forgot_password` | Kebijakan login | **Sangat tinggi** |
| `core/accounts.py` | Verified, Tested | Logika akun | CRUD user, `authenticate` (lockout 5x/15 menit, dummy hash), kebijakan password (min 10, huruf+angka, tanpa nama email), `set_password` (naikkan `session_version`), lupa password, role (`super_admin` hanya lewat CLI), katalog (`sync_dashboards`), hak akses (`allowed_slugs`, `set_access`), audit log (`audit`, `describe_audit`) | DB | rows, `AccountError` | `db`, werkzeug.security | auth, admin, registry, scripts | Login, Admin, Audit | `test_login_and_access`, `test_passwords_and_database`, `test_forgot_password` | Aturan akun | Sangat tinggi |
| `core/db.py` | Verified, Tested | SQLite | `MIGRATIONS` (3 versi, `PRAGMA user_version`), `migrate()` + backup otomatis, `get_db()` per request, Favorites, History (simpan 100, dedup 30 menit) | `APP_DB` | koneksi, rows | sqlite3 | accounts, portal, registry, scripts | Semua data portal | `test_passwords_and_database` (migrasi + backup) | Skema baru (tambah migrasi di akhir) | Sangat tinggi: data user |
| `core/registry.py` | Verified, Tested | Plug-in dashboard | Dataclass `Dashboard`, `ChatSpec`, `Tool`; auto-discovery `mantra/dashboards/*` (kecuali `_`); `_guard` (login + `can_open` + catat History) di setiap route dashboard; `visible_for`, `current`, `manifests` | modul dashboard | daftar dashboard | `accounts`, `auth`, `db`, `chat.prompt` | `create_app`, portal, admin, chat, scripts | Reports, semua dashboard | `test_login_and_access` (403 URL langsung, static, API), `test_errors_and_security` | Field manifest baru | Tinggi |
| `core/powerbi.py` | Verified (diblokir di test) | Klien Power BI | `Dataset` (ID bisa ditimpa `.env`), `PowerBI` (MSAL client credentials, `requests.Session` per thread, timeout), `_RateLimiter` global, `execute_query` (parse `results[0].tables[0].rows`, nama kolom dibersihkan), `PowerBIError`, `DATA_ERRORS` | DAX, kredensial | list of dict | msal, requests, `Config` | queries semua dashboard, `check_setup` | Semua data | `test_errors_and_security` (error tidak bocor; request di-stub) | Jarang | Tinggi: semua dashboard |
| `core/cache.py` | Verified, Tested | Cache memori | `Cache(ttl, size=300).get(key, load)` → `(data, waktu)`; satu `load()` per key saat bersamaan; error tidak di-cache | key, fungsi load | `(data, ts)` | threading | queries | Kecepatan, kuota | `test_errors_and_security` (cache) | Jarang | Data basi / beban Power BI |
| `core/errors.py` | Verified, Tested | Error data standar | `log_data_error` (kode ref 8 hex, detail ke log), `data_error_page` (502 HTML), `data_error_json`, `data_error_text` | exception | respons 502 | `common` | routes dashboard, chat | Halaman error | `test_errors_and_security` | Jarang | Kebocoran ID workspace |
| `core/common.py` | Verified | Helper | `WIB`, `now_wib`, `stamp_info`, `dax_str` (escape `"`), `fix_logo_url` | nilai | nilai | datetime | queries, errors, engine | Header "Last Update", DAX | tidak langsung | Jarang | DAX injection jika `dax_str` dilewati |
| `core/prompts/base.md` | Verified, Tested (`check_ai_agent --static`) | Aturan umum AI | Role, 8 aturan umum, format jawaban; placeholder `{{today}}` dll. Komentar HTML tidak dikirim | — | teks prompt | — | `chat/prompt.py` | Semua AI agent | `check_ai_agent.py --static` | Aturan perilaku AI | Semua agent berubah |
| `core/chat/routes.py` | Verified, Tested | Endpoint chat | `POST /d/<slug>/api/chat`: cek dashboard punya chat & ready, login (401), `can_open` (403 + audit), rate limit per user (429), provider (503), validasi body, panggil `engine.answer` | JSON `{message, history, context, filters}` | JSON `{answer, tools, model}` | `engine`, `providers`, `auth`, `accounts`, `registry` | `chat.js` | Panel AI | `test_login_and_access` (chat dilindungi), `test_errors_and_security` (rate limit, error tool) | Kontrak chat | Tinggi (keamanan & biaya) |
| `core/chat/engine.py` | Verified, Tested (provider palsu) | Orkestrasi | `answer()`: `parse_dash`, `call_tool` (cari tool, `clean_args`, jalankan, `add_hint`, tangkap `ToolArgError`/`DATA_ERRORS`/exception lain), render prompt, `provider.chat`; batas pesan 1000, history 20, 6 putaran tool | pesan, history, filter | `(text, used, model)` | prompt, providers, guards, errors | chat routes | AI | `test_errors_and_security` | Loop agent | Tinggi |
| `core/chat/providers.py` | Verified (Gemini asli NOT RUN) | Adapter AI | `GeminiProvider` (timeout 20 dtk, tanpa retry SDK, fallback model pada 429/500/503/504/transport error, function calling manual), `PROVIDERS`, `configured()`, `get()` | prompt, tools | teks + model | google-genai, httpx | engine, `create_app`, portal | AI | `test_errors_and_security` (provider palsu) | Provider baru | Sedang |
| `core/chat/prompt.py` | Verified, Tested | Prompt loader | `load()` saat start: `base.md` + `prompts/*.md` (system.md dulu), hapus komentar, validasi placeholder & nama tool; `render()` mengisi placeholder | file .md | `chat.template` | — | registry, engine, scripts | AI | `check_ai_agent.py --static` | Placeholder baru | App gagal start jika prompt salah |
| `core/chat/guards.py` | Verified, Tested | Validasi parameter AI | `ToolArgError` (+ `valid_options`), `resolve` (cocok persis / tanpa awalan / unik), `resolve_week`, `add_hint` (hasil kosong) | nilai dari AI | nilai asli / error | re | tools dashboard, engine | AI | `check_ai_agent.py --static`, `test_errors_and_security` | Aturan pencocokan | Jawaban AI dari data salah |
| `core/__init__.py`, `core/chat/__init__.py` | Verified | Penanda package | Docstring saja | — | — | — | — | — | — | — | — |

## D. `mantra/dashboards/`

| Path | Status | Fungsi utama | Isi & tanggung jawab | Input | Output | Dependency | Dipanggil oleh | Berkaitan dengan | Test terkait | Kapan diubah | Risiko perubahan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `dashboards/__init__.py` | Verified | Package dashboard | Docstring: aturan folder `_` dan perintah membuat dashboard | — | — | — | `registry.module_names` | Discovery | — | — | — |
| `_template/**` (9 file) | Verified, Tested (generator diuji di salinan) | Kerangka dashboard baru | Manifest `ready=False`, query contoh `INFO.VIEW.TABLES()`, 1 halaman, 1 tool `get_tables`, prompt, chat case; placeholder `__SLUG__`, `__NAME__`, `__TITLE__`, `__ENV__` | — | — | core | `scripts/create_dashboard.py` | Dashboard baru | uji generator (dok 17) | Pola standar berubah | Dashboard baru ikut salah |
| `material_readiness/__init__.py` | Verified | Manifest | `DASHBOARD`: slug `material-readiness`, pages Summary/Detail, `ChatSpec` (5 tools, placeholder `branches`, `companies`), order 10 | — | `Dashboard` | registry, queries, tools, routes | registry | Kartu Reports | `test_login_and_access` | Halaman/AI baru | Dashboard hilang |
| `material_readiness/queries.py` | Verified | Query & aturan data | `DATASET`, kolom/VIEWS, branch FP & ME, `summary_cube`, `company_logos`, `parse_filters`, `detail` (paging, KPI), `export_tsv`, `kpi`, `breakdown`, `lookup` (semua branch), cache | filter | rows | core.powerbi, cache, common | routes, tools, chat_cases | Summary, Detail, AI | `test_errors_and_security` (error tidak bocor) | Aturan bisnis | Angka berubah |
| `material_readiness/routes.py` | Verified, Tested (jalur error & akses) | Halaman | `/` (summary, SSR + `window.SUMMARY`), `/detail`, `/api/detail` (JSON), `/api/detail/export` (TSV) | query string | HTML/JSON/TSV | queries, errors | Browser | Summary, Detail | `test_login_and_access`, `test_errors_and_security` | Halaman/API baru | Kontrak JS |
| `material_readiness/tools.py` | Verified, Tested (static) | Tools AI | 5 `Tool`, `clean_args` (type/status/company/week), `parse_dash` (year/month/company), `prompt_values`, `SUGGESTIONS` | args AI | dict | queries, guards | engine | AI | `check_ai_agent --static` | Kemampuan AI baru | Jawaban AI salah |
| `material_readiness/chat_cases.py` | Verified (NOT RUN: butuh Gemini) | Pertanyaan acuan AI | 8 kasus `case_*`, jawaban acuan dihitung dari queries saat tes | — | `CASES` | queries, tools | `check_ai_agent --dashboard` | Regresi AI | — | Perilaku AI baru | — |
| `material_readiness/prompts/system.md`, `data_dictionary.md` | Verified, Tested (static) | Prompt dashboard | Aturan khusus & kamus data | — | teks | — | `chat/prompt.py` | AI | `check_ai_agent --static` | Istilah/aturan baru | AI menjawab keliru |
| `material_readiness/templates/material_readiness/summary.html`, `detail.html` | Verified | Tampilan | Extend `dashboard/base.html`, embed `window.SUMMARY` / `window.DETAIL` | payload | HTML | `_icons.html` | routes | Summary, Detail | validasi kompilasi template | UI | Kontrak dengan JS |
| `material_readiness/static/summary.js`, `detail.js` | Verified | Logika browser | Summary: chart & slicer di browser dari cube; Detail: `fetch` ke `/api/detail`, export, state di URL; keduanya mendefinisikan `window.DashContext`/`DashFilters` untuk chat | payload/JSON | DOM | `dash-common.js` | template | Summary, Detail | — (tidak ada test JS) | UI/filter | Halaman rusak tanpa error server |
| `pani_processing/__init__.py` | Verified | Manifest | slug `pani-processing`, 4 pages, `ChatSpec` 6 tools, order 20 | — | `Dashboard` | registry | registry | Reports | `test_login_and_access` | — | — |
| `pani_processing/queries.py` | Verified, Tested (stub) | Query & perhitungan | 7 tabel model, bounds per halaman, `date_range` (clamp), processing/equipment/mining/production, format angka, company header, refresh model | tanggal | dict | core.powerbi, cache, common | routes, tools, chat_cases, `compare_pani_with_powerbi` | 4 halaman, AI | `test_errors_and_security` (tanggal ekstrem, model kosong) | Aturan bisnis | Angka beda dengan report |
| `pani_processing/routes.py` | Verified, Tested (stub) | 4 halaman | `/`, `/equipment` (`?status=`), `/mining`, `/production`; filter `?start=&end=`; halaman kosong `dashboard/empty.html`; `context_processor` `fmt/sgn/tone/arrow` | query string | HTML | queries, errors | Browser | PANI | `test_errors_and_security` | Halaman baru | — |
| `pani_processing/tools.py` | Verified, Tested (static) | Tools AI | 6 tools, `clean_args` (period/status/metric), `parse_dash` (page/start/end) | args | dict | queries, guards | engine | AI | `check_ai_agent --static` | — | — |
| `pani_processing/chat_cases.py` | Verified (NOT RUN) | Pertanyaan acuan | 5 kasus | — | `CASES` | queries | `check_ai_agent` | AI | — | — | — |
| `pani_processing/prompts/*.md` | Verified, Tested (static) | Prompt dashboard | Aturan & kamus data PANI | — | — | — | prompt.py | AI | static | — | — |
| `pani_processing/templates/pani_processing/_ui.html` | Verified | Komponen PANI | Macro `filters` (bar tanggal), `picon`, `scripts` (embed `window.PANI` + `pani.js`) | — | HTML | `_icons.html` | 4 template | PANI | render via test stub | — | Semua halaman PANI |
| `pani_processing/templates/.../processing.html`, `equipment.html`, `mining.html`, `production.html` | Verified, Tested (render dengan data stub kosong, kecuali processing: hanya halaman kosong) | Tampilan 4 halaman | Extend `dashboard/base.html`, panggil `Pani.spark/combo` | `d`, `bounds`, `payload` | HTML | `_ui.html`, `pani.css/js` | routes `_page()` | PANI | `test_errors_and_security` | UI | — |
| `pani_processing/static/pani.css`, `pani.js` | Verified | Gaya & chart PANI | `window.Pani` = `{P, fmtN, spark, combo, onResize}`; header company; `DashContext`/`DashFilters` | `window.PANI` | SVG | `dash-common.js` | template | PANI | — | UI | — |

## E. `mantra/templates/` (shared)

| Path | Status | Fungsi utama | Isi & tanggung jawab | Input | Output | Dependency | Dipanggil oleh | Berkaitan dengan | Test terkait | Kapan diubah | Risiko perubahan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `base.html` | Verified, Tested | Kerangka semua halaman | meta `csrf-token`, `favorite-url`, `shell.css`, sidebar, top bar, `<main class="content">`, loader, `shell.js`; blok `styles`, `head`, `main`, `overlays`, `layer_scripts` | `report`, globals | HTML | `components/*` | `portal/base.html`, `dashboard/base.html` | **Semua** | semua test yang merender halaman | Layout global | **Sangat tinggi** |
| `components/sidebar.html`, `topbar.html` | Verified, Tested | Navigasi global | Menu portal + Admin (hanya Super Admin) + badge reset; top bar: breadcrumb report, favorit, tombol Ask AI, user, ganti password, logout (POST + CSRF) | `report`, `current_user` | HTML | `portal/_ui.html` | `base.html` | Semua | `test_login_and_access` | Menu baru | Sangat tinggi |
| `portal/base.html` | Verified, Tested | Kerangka portal | `portal.css`, flash message, banner `AUTH_DISABLED`, `portal.js` | — | — | `base.html` | halaman portal & admin | Portal | ya | — | Tinggi |
| `portal/bare.html`, `_auth_layout.html` | Verified, Tested | Kerangka tanpa sidebar | `bare`: ganti password wajib, error tanpa login; `_auth_layout`: login & lupa password (foto latar opsional) | — | — | — | login, forgot, change_password, error | Login | `test_login_and_access`, `test_forgot_password`, `test_errors_and_security` | — | — |
| `portal/_ui.html` | Verified | Macro UI | `icon(name)` (29 ikon), `brand`, `merdeka`, `ms_logo`, `report_card`, `mantra_mark` | — | — | — | hampir semua template portal/admin | Ikon dashboard (`Dashboard.icon`) | — | Ikon baru | Ikon hilang |
| `portal/home, reports, favorites, history, settings.html` | Verified, Tested | Halaman portal | Kartu report, filter, daftar riwayat, status konfigurasi (Super Admin) | context dari `portal.py` | HTML | `_ui.html` | `portal.py` | Portal | `test_login_and_access` | Fitur portal | Sedang |
| `portal/login, forgot_password, change_password, denied, error.html` | Verified, Tested | Halaman akun & error | Form POST + `_csrf`; pesan error generik | — | — | — | `auth.py`, `registry`, `__init__` | Login | `test_login_and_access`, `test_forgot_password`, `test_errors_and_security` | — | Tinggi (keamanan) |
| `admin/*.html` (8) | Verified, Tested | Halaman admin | users, user_new, user_detail, temp_password (`no-store`), dashboards, audit, `_ui.html`, `_audit_table.html` | context `admin.py` | HTML | `portal/base.html` | `admin.py` | Admin | `test_login_and_access` | Fitur admin | Tinggi |
| `dashboard/base.html` | Verified, Tested | Kerangka report | Header biru (logo, judul, menu `pages`, Last Update), panel chat + `window.CHAT` (jika `chat_enabled`), `dashboard.css`, `dash-common.js`, `chat.js` | `dashboard`, `header` | HTML | `base.html`, `_icons.html` | semua template dashboard | Semua report | `test_errors_and_security` | Layout report | **Sangat tinggi** |
| `dashboard/_icons.html`, `empty.html`, `error.html` | Verified, Tested | Ikon & status | `empty`: "No data available yet"; `error`: pesan umum + kode ref | `ref`, `header` | HTML | — | errors.py, PANI routes | Status data | `test_errors_and_security` | — | — |

## F. `mantra/static/` (shared)

| Path | Status | Fungsi utama | Isi & tanggung jawab | Input | Output | Dependency | Dipanggil oleh | Berkaitan dengan | Test terkait | Kapan diubah | Risiko perubahan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `css/shell.css` | Verified, Tested (200 di localhost) | Design token & kerangka | `:root` (warna, `--sidebar-w`, `--topbar-h`), sidebar, top bar, loader | — | — | — | `base.html`, `_auth_layout`, `bare` | Semua | smoke test | Warna/ukuran global | Semua halaman |
| `css/portal.css` | Verified | Gaya portal, login, admin | Kartu `tone-*`, pill `act-*`, form | — | — | shell.css | `portal/base`, `bare`, `_auth_layout` | Portal | — | UI portal | Sedang |
| `css/dashboard.css` | Verified | Gaya report & chat | `.dash`, header `.hd`, panel, tabel, chat panel; breakpoint `@container dash` | — | — | shell.css | `dashboard/base.html` | Semua report | — | UI report | Semua dashboard |
| `js/shell.js` | Verified | Perilaku kerangka | Sidebar mini/drawer (`localStorage mantra.sidebar`), loader pindah halaman, tombol favorit (`fetch` POST + `X-CSRF-Token`) | DOM, meta | — | — | `base.html` | Semua | — | — | Navigasi rusak |
| `js/portal.js` | Verified | Filter Reports | Search + kategori di sisi browser | DOM | — | — | `portal/base.html` | Reports | — | — | Rendah |
| `js/dash-common.js` | Verified | Util report | `window.Dash` = `{esc, fmt, statusRank, badgeColor, setHeaderCompany, moName}` | — | — | — | `dashboard/base.html` | Semua report | — | — | Semua dashboard |
| `js/chat.js` | Verified | Panel AI | Kirim `{message, history(20), context, filters}` ke `window.CHAT.url` dengan `X-CSRF-Token`; markdown sederhana; daftar tool yang dipakai | `window.CHAT`, `DashContext`, `DashFilters` | DOM | `Dash.esc` | `dashboard/base.html` | AI | — | UI chat | Semua agent |
| `img/mantra-mark.svg` | Verified | Logo/favicon | — | — | — | — | `base.html`, `_auth_layout` | — | — | — | — |

## G. `scripts/` dan `tests/`

Penjelasan per file: [scripts/README.md](../../scripts/README.md), [tests/README.md](../../tests/README.md).

| Path | Status | Fungsi | Butuh layanan luar | Test/uji di sesi ini |
|---|---|---|---|---|
| `scripts/manage_users.py` | Verified, Tested (seed di `test_passwords_and_database`) | CLI akun & backup | Tidak | `seed` diuji pytest |
| `scripts/check_setup.py` | Verified | Cek `.env`, Entra, Power BI, AI; `--dashboard --dax` | Ya | NOT RUN (layanan asli) |
| `scripts/check_ai_agent.py` | Verified, Tested | `--static` gratis; `--dashboard` pakai Gemini | `--dashboard`: ya | `--static`: SEMUA LULUS |
| `scripts/create_dashboard.py` | Verified, Tested | Generator dashboard | Tidak | Diuji di salinan sandbox (dok 17) |
| `scripts/compare_pani_with_powerbi.py` | Verified | Rekonsiliasi angka PANI vs report | Ya | NOT RUN |
| `tests/conftest.py` + 4 file test | Verified, Tested | 58 test | Tidak (diblokir) | 58 passed |

## H. Runtime & generated

| Path | Status | Keterangan |
|---|---|---|
| `instance/mantra.db` | Existing | Data akun & portal. **Jangan dihapus.** Dibuat & dimigrasi otomatis saat start |
| `instance/backups/` | Not Found (saat ini) | Dibuat otomatis oleh migrasi (`before-v<N>`) atau `manage_users.py backup` (`manual`) |
| `.venv/` | Existing | Python 3.13.3 + paket (dok 05) |
| `__pycache__/`, `.pytest_cache/` | Generated | Boleh dihapus, dibuat ulang otomatis |
