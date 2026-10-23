# MANTRA: Multi-Agent Network for Tracking & Reporting Analytics

Portal analitik grup PT Merdeka Copper Gold. Satu portal berisi banyak dashboard. Setiap dashboard punya semantic
model Power BI, tampilan, logika query, dan **AI agent** sendiri. User login dengan akun Microsoft perusahaan, dan
dashboard yang bisa dibuka diatur lewat **app roles** di Microsoft Entra.

```
Browser ── login ──> Microsoft Entra (MANTRA Portal: app roles)
   │
   ▼
Flask MANTRA ── core/ (login, registry, cache, pembatas query, mesin AI agent)
   │
   ├── /d/material-readiness/  ── service principal mantra-powerbi ──> semantic model Material Readiness
   ├── /d/pani-processing/     ── service principal mantra-powerbi ──> semantic model PANI - PRCS - Processing
   └── /d/<slug>/api/chat      ── AI agent dashboard itu (Gemini; provider bisa diganti)
```

Data dashboard **tidak** disimpan di MANTRA; semuanya dibaca langsung dari semantic model lewat `executeQueries`.
File `instance/mantra.db` hanya berisi Favorites dan History per user.

## Status dashboard

| Dashboard | Slug | App role | Status |
|---|---|---|---|
| Material Readiness | `material-readiness` | `Report.MaterialReadiness` | Siap. Angka identik dengan project lama (66 perbandingan) dan 8 pertanyaan acuan AI agent lulus |
| PANI Processing | `pani-processing` | `Report.PaniProcessing` | Coming soon: menunggu akses `mantra-powerbi` ke workspace PANI |

## Struktur folder

```
run.py
mantra/
  __init__.py              create_app(), CSRF
  config.py                baca .env
  portal.py                Home, Reports, Favorites, History, Settings
  core/
    auth.py                login Microsoft Entra + hak akses dari app roles
    registry.py            daftar dashboard (auto-discovery) + kontrak Dashboard / ChatSpec / Tool
    powerbi.py             service principal, Dataset per dashboard, pembatas query bersama
    cache.py, db.py        cache query, Favorites & History
    prompts/base.md        aturan umum SEMUA AI agent
    chat/                  mesin AI agent: engine, provider (Gemini), prompt loader, pengaman parameter
  templates/portal/        halaman portal        templates/dashboard/   kerangka halaman dashboard
  static/                  portal.css, dashboard.css, portal.js, chat.js, dash-common.js
  dashboards/
    _template/             kerangka dashboard baru (dipakai scripts/new_dashboard.py)
    material_readiness/    __init__.py (manifest), queries.py, routes.py, tools.py, prompts/, templates/, static/,
                           chat_cases.py (pertanyaan acuan AI agent)
    pani_processing/       manifest (coming soon)
scripts/
  check_setup.py           cek .env, Entra, akses tiap semantic model, AI
  test_chatbot.py          tes AI agent (statis + pertanyaan acuan)
  new_dashboard.py         buat dashboard baru dari _template
```

## Setup (laptop baru / clone ulang)

### 1. Install

| Software | Versi teruji | Cek |
|---|---|---|
| Git for Windows | 2.56 | `git --version` |
| Python (centang "Add python.exe to PATH") | 3.13.3 | `python --version` |

```powershell
cd "D:\Training SSIS + Python + Streamlit"
git clone https://github.com/mhdalfarisy/Web-App-MANTRA.git "Web App MANTRA"
cd "Web App MANTRA"
python -m venv .venv
.venv\Scripts\Activate.ps1          # kalau diblokir: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
Copy-Item .env.example .env         # lalu isi (lihat langkah 2-4)
```

`.env` **tidak ada di GitHub**: simpan salinannya di tempat aman. `instance\mantra.db` (Favorites & History) dibuat
otomatis.

### 2. Microsoft Entra: login user (app registration `MANTRA Portal`)

1. entra.microsoft.com > App registrations > New registration: name `MANTRA Portal`, Single tenant,
   Redirect URI **Web** `http://localhost:5001/auth/callback` (port = `PORT` di `.env`, default 5001).
2. Catat Application (client) ID dan Directory (tenant) ID > `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`.
3. Certificates & secrets > New client secret > salin **Value** > `ENTRA_CLIENT_SECRET`.
4. App roles > Create app role (Allowed member types: Users/Groups), Value harus persis:
   `Portal.Admin`, `Report.MaterialReadiness`, `Report.PaniProcessing`.
5. Enterprise applications > MANTRA Portal > Properties > **Assignment required = Yes**.
6. Users and groups > Add user/group > pilih user + role.
7. Di `.env`: `AUTH_DISABLED=0`.

### 3. Microsoft Entra + Power BI: akses data (app registration `mantra-powerbi`)

1. New registration `mantra-powerbi` (Single tenant, tanpa redirect URI) > secret > `PBI_CLIENT_ID`,
   `PBI_CLIENT_SECRET`. Tenant sama, jadi `PBI_TENANT_ID` boleh kosong. Tidak perlu API permission.
2. Groups > `sg-powerbi-api` > Members > tambahkan `mantra-powerbi` (berlaku ~15 menit).
3. Power BI > setiap workspace dashboard > Manage access > tambahkan `mantra-powerbi` sebagai **Contributor**.

### 4. AI agent

`GEMINI_API_KEY` dari https://aistudio.google.com/apikey (key khusus MANTRA). Kosong = tombol "Tanya AI" disembunyikan.

### 5. Cek dan jalankan

```powershell
python scripts\check_setup.py                 # semua harus OK (PANI menunggu akses workspace)
python scripts\test_chatbot.py --static       # cek prompt semua AI agent (gratis)
python run.py                                 # buka http://localhost:5001 (bukan 127.0.0.1)
```

**Mode development tanpa login**: `AUTH_DISABLED=1` di `.env`. Role user development diatur lewat `DEV_ROLES`
(mis. `Report.MaterialReadiness` untuk mencoba tampilan user biasa). Jangan dipakai di production.

Foto latar halaman login (opsional): simpan sebagai `mantra\static\img\login-bg.jpg`.

## Menambah dashboard

```powershell
python scripts\new_dashboard.py work-order "Work Order"
```

Lalu ikuti petunjuk yang dicetak:

1. Isi `workspace_id` & `dataset_id` di `mantra\dashboards\work_order\queries.py`.
2. Buat app role `Report.WorkOrder` di Entra, lalu assign user.
3. Beri `mantra-powerbi` akses ke workspace-nya, lalu jalankan `check_setup.py`.
4. Bangun query (`queries.py`), halaman (`templates/`, `static/`), tool agent (`tools.py`), prompt (`prompts/`),
   dan pertanyaan acuan (`chat_cases.py`).
5. Ubah `ready=True` di `__init__.py`, lalu restart Flask.

Struktur model bisa dibaca langsung:
`python scripts\check_setup.py --dashboard work-order --dax "EVALUATE INFO.VIEW.COLUMNS()"`

## AI agent

Prompt setiap agent = `mantra\core\prompts\base.md` (aturan umum) + `mantra\dashboards\<nama>\prompts\*.md`
(`system.md` lebih dulu, lalu kamus data). Petunjuk placeholder ada di komentar bagian atas tiap file. Prompt dibaca
saat start, jadi **restart Flask** setelah mengubahnya. Salah ketik placeholder atau nama tool membuat aplikasi
gagal start dengan pesan yang jelas.

```powershell
python scripts\test_chatbot.py --static                          # semua agent, tanpa kuota AI
python scripts\test_chatbot.py --dashboard material-readiness    # + pertanyaan acuan (pakai kuota)
```

Mengganti provider (mis. OpenAI): tambahkan class di `mantra\core\chat\providers.py` dengan method
`chat(system, history, message, tools, call_tool, max_rounds)`, daftarkan di `PROVIDERS`, lalu ubah `AI_PROVIDER`
di `.env`. Dashboard dan tools tidak perlu diubah.

## Kalau ada masalah

| Gejala | Solusi |
|---|---|
| "Akun Anda belum diberi akses ke MANTRA" | User belum di-assign di Enterprise applications > MANTRA Portal > Users and groups |
| Login berhasil tapi tidak ada dashboard | User belum punya app role `Report.*`. Assign role, lalu logout & login ulang |
| `AADSTS50011` redirect URI mismatch | Buka lewat `http://localhost:5001`, dan pastikan redirect URI di app registration persis `http://localhost:5001/auth/callback` (port sama dengan `PORT` di `.env`) |
| Port 5001 sudah dipakai | Ganti `PORT` di `.env` (mis. 5002), lalu ubah juga redirect URI di Entra ke port yang sama |
| Dashboard "Gagal mengambil data dari Power BI" | `python scripts\check_setup.py`. Pesan error disertai petunjuk |
| "Layanan AI sedang sibuk" | Kuota Gemini habis atau model penuh. Coba lagi, atau pakai API key khusus MANTRA |
| Perubahan prompt tidak terbaca | Restart `python run.py` |
