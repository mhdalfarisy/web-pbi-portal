# 27 — Rebuild from Zero

### A. Objective
Membangun ulang MANTRA dari direktori kosong dengan urutan yang benar, dan tahu kapan setiap tahap selesai.

### B. When to use
Belajar arsitektur secara mendalam, membuat ulang di environment bersih, atau memigrasi ke struktur baru.
**Untuk pemakaian biasa cukup `git clone`** (dok 04). Panduan ini memakai kode existing sebagai referensi
(sumber kebenaran); potongan kode di bawah adalah **kerangka minimal (Target)**, implementasi lengkap ada di file
yang dirujuk.

### C. Prerequisites
Dok 04-06; akses Power BI & Gemini untuk tahap 11-13.

### D. Architecture context
Urutan mengikuti dependency import (dok 09 §2) dan roadmap CP (dok 03).

### E. Files involved
Lihat setiap tahap.

### F. Step-by-step instructions

#### Tahap 1 — Folder & environment (CP-02/03)
```powershell
mkdir "Web App MANTRA"; cd "Web App MANTRA"; git init
py -m venv .venv; .\.venv\Scripts\Activate.ps1
```
Buat `requirements.txt` & `requirements-dev.txt` (isi di dok 05 §G), `.gitignore`:
```
.env
.venv/
__pycache__/
*.pyc
instance/
.claude/
.pytest_cache/
```
`pip install -r requirements-dev.txt`. **Selesai jika** import dok 05 §I berhasil.

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
Buat `.env.example` dan `.env`. **Selesai jika** `python -c "from mantra.config import Config; print(Config.PORT)"`.

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
Tambahkan hook CSRF, security headers, dan error handler persis seperti `mantra/__init__.py` (dok 07 §2).
**Selesai jika** server start (halaman 404 untuk `/` masih wajar di tahap ini).

#### Tahap 4 — Database (CP-06) — `mantra/core/db.py`
Salin pola: `MIGRATIONS` (list SQL), `connect`, `backup`, `migrate(path, backup_dir)` (`PRAGMA user_version`),
`init_app`, `get_db`, `_close_db`, lalu Favorites/History. Panggil `db.init_app(app)` di `create_app`.
**Selesai jika** `instance/mantra.db` dibuat dengan `user_version = 3`.

#### Tahap 5 — Akun & login (CP-07) — `core/accounts.py`, `core/auth.py`, template login
Urutan: `accounts` (user, password, authenticate, audit, katalog, hak akses) → `auth` (blueprint, `current_user`,
`login_required`, `role_required`, `require_password_change`, route login/lupa/ganti/logout/Entra) → template
`portal/_auth_layout.html`, `login.html`, `forgot_password.html`, `change_password.html`, `bare.html`, `error.html`.
Lalu `scripts/manage_users.py` (`seed`). **Selesai jika** login + wajib ganti password berfungsi; test
`test_login_and_access.py` bagian login lulus.

#### Tahap 6 — Kerangka frontend (CP-08)
`templates/base.html`, `components/sidebar.html`, `components/topbar.html`, `portal/_ui.html`, `portal/base.html`,
`static/css/shell.css`, `static/js/shell.js`, `static/img/mantra-mark.svg`. Context processor (`csrf_token`,
`current_user`, ...) wajib ada sebelum template ini bisa dirender. **Selesai jika** Home kosong tampil dengan sidebar.

#### Tahap 7 — Portal & admin (CP-09)
`mantra/portal.py`, `mantra/admin.py`, `templates/portal/*`, `templates/admin/*`, `static/css/portal.css`,
`static/js/portal.js`. **Selesai jika** semua halaman di dok 13 terbuka sesuai role.

#### Tahap 8 — Registry (CP-10) — `core/registry.py`, `mantra/dashboards/__init__.py`
Dataclass `Tool`, `ChatSpec`, `Dashboard` (dok 14 §2), `_guard`, `_load`, `module_names`, `manifests`, `init_app`.
Di `create_app`: `registry.init_app(app)` lalu `accounts.sync_dashboards(...)`.
**Selesai jika** dashboard dummy dengan `ready=False` tampil "Coming soon".

#### Tahap 9 — Power BI (CP-11) — `core/powerbi.py`, `core/cache.py`, `core/errors.py`, `core/common.py`
Kontrak: `Dataset(env_prefix, workspace_id, dataset_id)`, `query(dataset, dax) -> list[dict]`,
`DATA_ERRORS`, `Cache(ttl).get(key, load) -> (data, ts)`, `data_error_page/json/text`.
Lalu `scripts/check_setup.py`. **Selesai jika** `check_setup.py` → `SEMUA CEK LULUS`.

#### Tahap 10 — Template report bersama
`templates/dashboard/base.html`, `_icons.html`, `empty.html`, `error.html`, `static/css/dashboard.css`,
`static/js/dash-common.js`.

#### Tahap 11 — Dashboard pertama (CP-12)
Buat `dashboards/_template/` (9 file, dok 02 §D) dan `scripts/create_dashboard.py`, lalu generate dashboard nyata.
Kerangka minimal satu dashboard:
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
                      color="blue", dataset=queries.DATASET, blueprint=bp, pages=[("Overview", "<x>.overview")])
```
**Selesai jika** angka sama dengan report Power BI.

#### Tahap 12 — AI agent (CP-13)
`core/prompts/base.md` → `core/chat/prompt.py` → `guards.py` → `providers.py` → `engine.py` → `routes.py` (daftarkan
blueprint `chat` di `create_app`) → `static/js/chat.js` + panel di `dashboard/base.html` → `tools.py`, `prompts/`,
`chat_cases.py` per dashboard → `scripts/check_ai_agent.py`. Kontrak provider: dok 20 §4.
**Selesai jika** `check_ai_agent.py --static` lulus dan pertanyaan acuan lulus.

#### Tahap 13 — Test (CP-14)
`pytest.ini`, `tests/conftest.py` (Config ditimpa, DB temp, blokir Power BI, `fresh_data`, `Client` CSRF), lalu 4 file
test. **Selesai jika** 58 test (atau padanannya) lulus.

#### Tahap 14 — Localhost & handover (CP-15/16)
`run_mantra.bat`, README, smoke test dok 22, matriks parity dok 28.

### G. Code or patch
Kerangka di setiap tahap (Target). Implementasi lengkap = file existing yang dirujuk.

### H. Code explanation
Setiap kerangka menunjukkan kontrak minimal yang dibutuhkan tahap berikutnya; detail perilaku (lockout, throttle,
fallback model, dst.) wajib mengikuti file existing supaya test lulus.

### I. Commands
`python run.py` · `python -m pytest` · `python scripts\check_setup.py` · `python scripts\check_ai_agent.py --static`

### J. Expected result
Setiap tahap memenuhi "Selesai jika".

### K. Validation
Jalankan test suite existing terhadap hasil rebuild (test adalah spesifikasi perilaku yang paling lengkap).

### L. Troubleshooting
Dok 23.

### M. Regression impact
Not Applicable (membangun baru).

### N. Acceptance criteria
58 test lulus, smoke test dok 22 sama, angka dashboard sama dengan report, AI lulus pertanyaan acuan.

### O. Documentation updates
Dok 28 (parity).

### P. Actual status
Rebuild dari direktori bersih: **NOT RUN**. Kerangka kode di atas: Target, tidak dijalankan terpisah.
