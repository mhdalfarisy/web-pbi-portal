# 27 — Rebuild from Zero

### A. Objective
Membangun ulang MANTRA dari direktori kosong dengan urutan yang benar, dan tahu kapan setiap tahap selesai.

### B. When to use
Belajar arsitektur secara mendalam, membuat ulang di environment bersih, atau memigrasi ke struktur baru.
**Untuk pemakaian biasa cukup `git clone`** (dok 04). Panduan ini memakai kode existing sebagai referensi
(sumber kebenaran); potongan kode di bawah adalah **kerangka minimal (Target)**, implementasi lengkap ada di file
yang dirujuk. Versi dengan link ke setiap file: [PANDUAN_DEVELOPMENT_BERURUTAN](../PANDUAN_DEVELOPMENT_BERURUTAN.md).

### C. Prerequisites
Dok 04-06 (macOS: Homebrew + `python@3.13`); akses Power BI & Gemini untuk tahap 9-12.

### D. Architecture context
Urutan mengikuti dependency import (dok 09 §2) dan roadmap CP (dok 03). **Revisi 28 Okt 2026:**

1. Registry (tahap 6) dibangun **sebelum** Portal (tahap 8), karena `portal.py` dan `inject_globals` memakai
   `registry` dan `providers.configured()`.
2. Dua **stub** sementara: `portal.py` (tahap 5, supaya login bisa redirect ke `portal.home`) dan
   `core/chat/providers.py` (tahap 6, `configured()` → `False`). Keduanya diganti versi penuh di tahap 8 dan 12.
3. Dashboard dibangun **tanpa AI dulu** (`chat=None`, tahap 10-11), karena `ChatSpec` membuat `registry._load`
   memanggil `prompt.load()` saat start. AI ditambahkan sebagai lapisan di tahap 12.
4. `registry._load` meng-import `core/chat/prompt.py` untuk **setiap** dashboard (juga `chat=None`), jadi file itu
   dibuat di awal tahap 10 (hanya bergantung pada `core/powerbi.py` dari tahap 9).

### E. Files involved
Lihat setiap tahap.

### F. Step-by-step instructions

Semua perintah untuk macOS (zsh); padanan Windows di [04 §Q](04_MACOS_VSCODE_SETUP.md#q-padanan-windows-powershell).

#### Tahap 1 — Folder & environment (CP-02/03)
```bash
mkdir web-pbi-portal && cd web-pbi-portal && git init
mkdir -p mantra/core/chat mantra/core/prompts mantra/dashboards mantra/templates mantra/static/{css,js,img} scripts tests docs
python3.13 -m venv .venv && source .venv/bin/activate
```
Buat `requirements.txt` & `requirements-dev.txt` (isi di dok 05 §G), `pytest.ini`, `.gitignore`:
```
.env
.venv/
__pycache__/
*.pyc
instance/
.claude/
.pytest_cache/
.DS_Store
```
`pip install -r requirements-dev.txt`. **Selesai jika** import dok 05 §I berhasil dan
`python -c "import sys; print(sys.executable)"` menunjuk `.venv/bin/python`.

#### Tahap 2 — Konfigurasi (CP-04) — `mantra/config.py`
```python
import os
from pathlib import Path
from dotenv import dotenv_values, load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = dotenv_values(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env", override=True)          # .env menang atas env terminal

class Config:
    PORT = int(os.environ.get("PORT") or 5001)
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
    AUTH_DISABLED = (_ENV_FILE.get("AUTH_DISABLED") or "").strip() == "1"   # hanya dari file
    INSTANCE_DIR = BASE_DIR / "instance"
    APP_DB = INSTANCE_DIR / "mantra.db"
    # ... variabel lain: lihat mantra/config.py & dok 06
```
Buat `.env.example`, lalu `cp .env.example .env` dan isi `FLASK_SECRET_KEY`. Buat juga `mantra/__init__.py` kosong.
**Selesai jika** `python -c "from mantra.config import Config; print(Config.PORT)"` → `5001`.

#### Tahap 3 — Factory & entry point (CP-05) — `mantra/__init__.py`, `run.py`
```python
# mantra/__init__.py (kerangka)
from flask import Flask
from .config import Config

def create_app(test_config=None):
    app = Flask(__name__, instance_path=str(Config.INSTANCE_DIR))
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("FLASK_SECRET_KEY belum diisi di .env")
    # tahap berikut: db.init_app, blueprint, registry, CSRF, security headers, context processor, error handler
    return app
```
```python
# run.py (kerangka; versi lengkap mencetak status & penyebab berhenti)
from mantra import create_app
from mantra.config import Config
app = create_app()
if __name__ == "__main__":
    app.run(host="localhost", port=Config.PORT, debug=Config.DEBUG)
```
Opsional: launcher `run_mantra.command` (`chmod +x`).
**Selesai jika** server start dan `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5001/` → `404`.

#### Tahap 4 — Database (CP-06) — `mantra/core/db.py`
Buat `mantra/core/__init__.py`. Salin pola: `MIGRATIONS` (list SQL), `connect`, `backup`,
`migrate(path, backup_dir)` (`PRAGMA user_version`), `init_app`, `get_db`, `_close_db`, lalu Favorites/History.
Panggil `db.init_app(app)` di `create_app`.
**Selesai jika** `sqlite3 instance/mantra.db "PRAGMA user_version"` → `3`.

#### Tahap 5 — Akun & login (CP-07) — `core/accounts.py`, `core/auth.py`, **stub** `portal.py`, template akun
Urutan:
1. `core/accounts.py` (user, password, authenticate, audit, katalog, hak akses).
2. `core/auth.py` (blueprint, `current_user`, `login_required`, `role_required`, `require_password_change`, route
   login/lupa/ganti/logout/Entra).
3. **Stub** `mantra/portal.py` — dibutuhkan karena login sukses memanggil `url_for("portal.home")`:
   ```python
   # STUB sementara: diganti versi penuh di tahap 8
   from flask import Blueprint
   from .core.auth import current_user, login_required

   bp = Blueprint("portal", __name__)

   @bp.get("/")
   @login_required
   def home():
       return f"Login OK sebagai {current_user()['email']}"
   ```
4. Aset & template akun (tidak butuh sidebar): `static/img/mantra-mark.svg`, `static/css/shell.css`,
   `static/css/portal.css`, `portal/_ui.html`, `portal/_auth_layout.html`, `login.html`, `forgot_password.html`,
   `bare.html`, `change_password.html`, `error.html`.
5. Di `create_app`: register `auth.bp` dan `portal.bp`; hook CSRF, security headers, `inject_globals` versi awal
   (`csrf_token`, `current_user`) dan error handler persis seperti `mantra/__init__.py` (dok 07 §2).
6. `scripts/manage_users.py` (`seed` dulu).

**Selesai jika**:
```bash
export MANTRA_SEED_PASSWORD='Sementara-2026'; python scripts/manage_users.py seed; unset MANTRA_SEED_PASSWORD
python run.py   # login pbi_pro_a@merdeka.com → wajib ganti password → "Login OK sebagai ..."
```
Test otomatis (`test_login_and_access.py`) baru bisa dijalankan di tahap 13: `conftest.py` meng-import
`mantra.core.chat.routes` (tahap 12) dan butuh kedua dashboard sudah ada.

#### Tahap 6 — Registry (CP-08) — **stub** `core/chat/providers.py`, `core/registry.py`, `mantra/dashboards/__init__.py`
1. `core/chat/__init__.py` (docstring) dan **stub** provider:
   ```python
   # mantra/core/chat/providers.py — STUB sementara: diganti GeminiProvider penuh di tahap 12
   def configured():
       return False   # belum ada AI: chat_enabled False, tombol Ask AI tersembunyi
   ```
2. `core/registry.py`: dataclass `Tool`, `ChatSpec`, `Dashboard` (dok 14 §2), `_guard`, `_load`, `module_names`,
   `manifests`, `init_app`.
3. `mantra/dashboards/__init__.py` (docstring).
4. Di `create_app`: `registry.init_app(app)` lalu `accounts.sync_dashboards(...)`.

**Selesai jika** app start dan `sqlite3 instance/mantra.db "select count(*) from dashboards"` → `0`.

#### Tahap 7 — Kerangka frontend (CP-09)
`components/sidebar.html`, `components/topbar.html`, `templates/base.html`, `portal/base.html`, `static/js/shell.js`.
Lengkapi `inject_globals` (`user_is_admin`, `pending_resets`, `dashboard`, `chat_enabled`, `report_favorite`) dan
`now_str`. Template ini memanggil `url_for` ke endpoint portal & admin, jadi **dicek di akhir tahap 8**.

#### Tahap 8 — Portal & admin (CP-10) — ganti stub `portal.py`
`mantra/portal.py` versi penuh (**timpa stub tahap 5**), `templates/portal/{home,reports,favorites,history,settings,denied}.html`,
`static/js/portal.js`, `mantra/admin.py` (+ register `admin.bp`), `templates/admin/*`.
**Selesai jika** semua halaman di dok 13 terbuka sesuai role, Reports masih kosong, dan `grep -n "Login OK" mantra/portal.py`
tidak menghasilkan apa pun.

#### Tahap 9 — Power BI (CP-11) — `core/common.py`, `core/powerbi.py`, `core/cache.py`, `core/errors.py`
Kontrak: `Dataset(env_prefix, workspace_id, dataset_id)`, `query(dataset, dax) -> list[dict]`,
`DATA_ERRORS`, `Cache(ttl).get(key, load) -> (data, ts)`, `data_error_page/json/text`.
Lalu `scripts/check_setup.py`. **Selesai jika** `python scripts/check_setup.py` → cek `.env` & token Power BI `OK`.

#### Tahap 10 — Template report bersama + `_template` tanpa AI (CP-12, bagian 1)
0. `core/chat/prompt.py` versi penuh (`load`, `values`, `render`). Wajib ada sebelum dashboard pertama karena
   `registry._load` meng-import-nya; `load()` sendiri baru dipanggil untuk dashboard yang punya `ChatSpec`.
1. `templates/dashboard/base.html`, `_icons.html`, `empty.html`, `error.html`, `static/css/dashboard.css`,
   `static/js/dash-common.js`.
2. `dashboards/_template/`: `queries.py`, `routes.py`, `templates/__NAME__/overview.html`, `static/.gitkeep`,
   `__init__.py` dengan **`chat=None`** (`tools.py`, `chat_cases.py`, `prompts/` menyusul di tahap 12). Buang juga
   `ChatSpec` dari import `core.registry`, `tools` dari `from . import queries, tools`, dan `from pathlib import Path`;
   kalau tidak, start gagal dengan `ImportError` (`tools.py` belum ada).
3. `scripts/create_dashboard.py`.

**Selesai jika** `python scripts/create_dashboard.py coba-data "Coba Data"` + ID dataset asli → kartu "Coming soon";
`ready=True` → halaman Overview menampilkan tabel model. Hapus folder `coba_data/` setelahnya dan nonaktifkan barisnya
di Admin > Dashboards.

#### Tahap 11 — Dashboard pertama tanpa AI (CP-12, bagian 2)
Kerangka minimal satu dashboard (urutan tulis: `queries.py` → `routes.py` → `templates/` → `static/` → `__init__.py`):
```python
# dashboards/<x>/queries.py
from ...config import Config
from ...core.cache import Cache
from ...core.common import dax_str, stamp_info  # noqa: F401
from ...core.powerbi import DATA_ERRORS, Dataset, query  # noqa: F401
DATASET = Dataset("PREFIX", workspace_id="...", dataset_id="...")
_cache = Cache(Config.CACHE_SECONDS)

# dashboards/<x>/routes.py
from flask import Blueprint, render_template
from ...core.errors import data_error_page
from . import queries
bp = Blueprint("<x>", __name__, url_prefix="/d/<slug>", template_folder="templates", static_folder="static")

# dashboards/<x>/__init__.py
from ...core.registry import Dashboard
from . import queries
from .routes import bp
DASHBOARD = Dashboard(slug="<slug>", title="...", description="...", category="...", icon="chart",
                      color="blue", dataset=queries.DATASET, blueprint=bp, pages=[("Overview", "<x>.overview")],
                      chat=None)   # AI ditambahkan di tahap 12
```
**Selesai jika** angka sama dengan report Power BI dan user tanpa akses mendapat 403.

#### Tahap 12 — AI agent (CP-13) — ganti stub `providers.py`, tambah `ChatSpec`
1. Mesin: `core/prompts/base.md` → `core/chat/guards.py` → (`core/chat/prompt.py` sudah dari tahap 10) → `core/chat/providers.py`
   (**timpa stub tahap 6**, kontrak provider: dok 20 §4) → `core/chat/engine.py` → `core/chat/routes.py`
   (daftarkan blueprint `chat` di `create_app`) → `static/js/chat.js` (panel & tombol sudah ada di
   `dashboard/base.html` dan `topbar.html`).
2. Per dashboard: `tools.py`, `prompts/system.md`, `prompts/data_dictionary.md`, `chat_cases.py`,
   `window.DashContext` / `window.DashFilters` di JS halaman, lalu ganti manifest:
   ```python
   from pathlib import Path
   from ...core.registry import ChatSpec, Dashboard
   from . import queries, tools
   ...
   chat=ChatSpec(tools=tools.TOOLS, prompt_dir=Path(__file__).resolve().parent / "prompts",
                 suggestions=tools.SUGGESTIONS),
   ```
3. Lengkapi `_template` dengan `tools.py`, `chat_cases.py`, `prompts/` dan `ChatSpec` (dashboard baru dari generator
   langsung punya agent contoh).
4. `scripts/check_ai_agent.py`.

**Selesai jika** `python scripts/check_ai_agent.py --static` → `SEMUA LULUS`, pertanyaan acuan lulus, dan
`grep -n "^class GeminiProvider" mantra/core/chat/providers.py` menemukan class-nya (stub sudah diganti).

#### Tahap 13 — Test (CP-14)
`tests/conftest.py` (Config ditimpa, DB temp, blokir Power BI, `fresh_data`, `Client` CSRF), lalu 4 file test.
Prasyarat: tahap 12 selesai **dan** dashboard `material-readiness` + `pani-processing` ada, karena `conftest.py`
meng-import `mantra.core.chat.routes` dan `fresh_data` memberi akses ke kedua dashboard (`PAGES`/`APIS` juga menguji
URL keduanya). Kalau rebuild baru punya satu dashboard, sesuaikan `PAGES`, `APIS`, dan daftar slug di `fresh_data`.
**Selesai jika** 58 test (atau padanannya) lulus.

#### Tahap 14 — Localhost & handover (CP-15/16)
`run_mantra.command`, README, smoke test dok 22, matriks parity dok 28.

### G. Code or patch
Kerangka di setiap tahap (Target). Implementasi lengkap = file existing yang dirujuk. Stub di tahap 5 & 6 bukan bagian
dari kode final.

### H. Code explanation
Setiap kerangka menunjukkan kontrak minimal yang dibutuhkan tahap berikutnya; detail perilaku (lockout, throttle,
fallback model, dst.) wajib mengikuti file existing supaya test lulus. Stub hanya ada supaya setiap tahap bisa
dijalankan dan dites sebelum lapisan di atasnya selesai.

### I. Commands
`python run.py` · `python -m pytest` · `python scripts/check_setup.py` · `python scripts/check_ai_agent.py --static`

### J. Expected result
Setiap tahap memenuhi "Selesai jika".

### K. Validation
Jalankan test suite existing terhadap hasil rebuild (test adalah spesifikasi perilaku yang paling lengkap).

### L. Troubleshooting
Dok 23. Khusus urutan ini:

| Gejala | Penyebab | Solusi |
|---|---|---|
| Login sukses lalu 500 `BuildError: Could not build url for endpoint 'portal.home'` | Stub `portal.py` belum dibuat / belum di-register | Tahap 5 langkah 3 & 5 |
| `ImportError: cannot import name 'registry'` saat membuat `portal.py` | Portal dibangun sebelum registry | Selesaikan tahap 6 dulu |
| `ImportError: cannot import name 'prompt' from 'mantra.core.chat'` saat start (manifest sudah `chat=None`) | `core/chat/prompt.py` belum dibuat | Tahap 10 langkah 0 |
| `RuntimeError: File prompt tidak ditemukan` / `Folder prompt ... kosong` saat start | Manifest memakai `ChatSpec` sebelum tahap 12 | Pakai `chat=None` sampai tahap 12 |
| Tombol Ask AI tidak pernah muncul setelah tahap 12 | Stub `providers.py` belum diganti | Tahap 12 langkah 1 |

### M. Regression impact
Not Applicable (membangun baru).

### N. Acceptance criteria
58 test lulus, smoke test dok 22 sama, angka dashboard sama dengan report, AI lulus pertanyaan acuan, tidak ada stub tersisa.

### O. Documentation updates
Dok 28 (parity).

### P. Actual status
Rebuild dari direktori bersih: **NOT RUN**. Kerangka kode di atas: Target, tidak dijalankan terpisah. Urutan direvisi
28 Okt 2026 berdasarkan analisis import (`portal.py` → `registry`, `providers`) dan `registry._load` → `prompt.load`.
