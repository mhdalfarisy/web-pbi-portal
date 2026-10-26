# 07 — Flask Startup & Request Lifecycle

Semua diagram di sini `Existing` dan `Verified` dari kode.

## 1. Project startup (terminal → server siap)

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Run as run.py
    participant Cfg as mantra/config.py
    participant F as create_app()
    participant DB as core/db.py
    participant Reg as core/registry.py
    participant W as Werkzeug dev server
    Dev->>Run: python run.py (atau run_mantra.bat)
    Run->>Cfg: import (baca .env, override=True)
    Run->>F: create_app()
    F->>F: SECRET_KEY ada? (tidak → RuntimeError)
    F->>DB: init_app: mkdir instance/, migrate() (+backup)
    F->>F: register blueprint auth, portal, chat, admin
    F->>Reg: init_app: import setiap mantra/dashboards/<x>
    Reg->>Reg: prompt.load() (validasi prompt & tool), pasang _guard, register blueprint
    F->>DB: accounts.sync_dashboards (katalog = kode)
    Run->>W: app.run(host="localhost", port=PORT, debug=FLASK_DEBUG)
    W-->>Dev: " * Power BI Portal: http://localhost:5001 | Login: ON ..."
```

| | |
|---|---|
| Titik awal | `python run.py` |
| File | `run.py`, `config.py`, `__init__.py`, `core/db.py`, `core/registry.py`, `core/chat/prompt.py`, `core/accounts.py`, `dashboards/*/__init__.py` |
| Input / output | `.env`, `instance/mantra.db` → server mendengar di `localhost:<PORT>` |
| Kondisi gagal | `FLASK_SECRET_KEY` kosong; DB versi lebih baru dari kode; prompt rusak (placeholder/tool tidak dikenal); manifest dashboard salah (`DASHBOARD_STRICT=1` → gagal start); port dipakai (`OSError`) |
| Cara uji | `python run.py` lalu buka `/login`; `test_errors_and_security.py::test_create_app_can_run_twice` |

`run.py` selalu mencetak penyebab berhenti: `stopped (Ctrl+C or terminal closed)` atau `crashed (exit code N)`.

## 2. Application factory (`create_app`) — urutan aktual

1. `Flask(__name__, instance_path=Config.INSTANCE_DIR)`; `app.config.from_object(Config)`; `test_config` menimpa (test).
2. `db.init_app(app)` — migrasi + `teardown_appcontext` untuk menutup koneksi.
3. `register_blueprint`: `auth.bp`, `portal.bp`, `chat_routes.bp`, `admin.bp`.
4. `registry.init_app(app)` — semua dashboard.
5. `accounts.sync_dashboards(conn, registry.all_dashboards())`.
6. Log peringatan: variabel env yang tertimpa `.env`; `AUTH_DISABLED=1`.
7. `jinja_env.globals["now_str"]`.
8. `before_request csrf_protect` — setiap **POST** wajib `_csrf` (form) atau header `X-CSRF-Token` (fetch) sama dengan
   `session["_csrf"]` (`hmac.compare_digest` atas bytes). Gagal → 400.
9. `after_request security_headers` — `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
   `Referrer-Policy: same-origin`.
10. `context_processor inject_globals` — `csrf_token()`, `current_user`, `user_is_admin`, `pending_resets`,
    `dashboard` (dashboard request ini), `chat_enabled`, `report_favorite`.
11. Error handler 400/404/500 — JSON bila path mengandung `/api/` atau request JSON, selain itu `portal/error.html`.

```mermaid
flowchart TD
    A["create_app(test_config)"] --> B["Config + test_config"]
    B --> C{"SECRET_KEY?"}
    C -- tidak --> X["RuntimeError"]
    C -- ya --> D["db.init_app → migrate + backup"]
    D --> E["Blueprint: auth · portal · chat · admin"]
    E --> F["registry.init_app → blueprint dashboard + _guard"]
    F --> G["accounts.sync_dashboards"]
    G --> H["Hook: CSRF (before) · security headers (after) · context processor · error handlers"]
    H --> I["app siap"]
```

## 3. Kapan aplikasi pertama kali bisa jalan

Cukup `.venv` + dependency + `FLASK_SECRET_KEY`. Tanpa akun, halaman login tampil tetapi tidak ada yang bisa masuk
(kecuali `AUTH_DISABLED=1`). Tanpa kredensial Power BI, halaman dashboard tampil "Could not load data from Power BI"
(HTTP 502). Tanpa `GEMINI_API_KEY`, tombol Ask AI tidak ada.

## 4. Portal request lifecycle (contoh `GET /reports`)

```mermaid
sequenceDiagram
    participant B as Browser
    participant F as Flask
    participant A as auth
    participant P as portal.reports
    participant R as registry
    participant D as SQLite
    B->>F: GET /reports (cookie session)
    F->>A: before_app_request require_password_change
    A->>D: current_user(): SELECT users WHERE id=session.uid
    A-->>F: user (atau None, atau wajib ganti password → redirect)
    F->>P: @login_required (None → 302 /login?next=/reports)
    P->>R: visible_for(user) → can_open → accounts.allowed_slugs (cache di g)
    R->>D: SELECT slug dashboards aktif (+ user_dashboard_access)
    P->>D: favorites(user)
    P-->>B: render portal/reports.html (extends portal/base.html → base.html) + security headers
```

| | |
|---|---|
| Kondisi gagal | Session tidak valid (akun nonaktif / `session_version` berubah) → `session.clear()` → redirect login |
| Cara uji | `test_login_and_access.py::test_anonymous_is_redirected_or_401`, `::test_user_sees_only_granted_dashboards`; smoke: `curl -I http://localhost:5001/reports` → 302 ke `/login?next=/reports` (Tested 26 Okt) |

## 5. Dashboard request lifecycle (contoh `GET /d/pani-processing/mining?start=...&end=...`)

```mermaid
sequenceDiagram
    participant B as Browser
    participant G as registry._guard (before_request blueprint)
    participant Rt as pani_processing.routes.mining
    participant Q as pani_processing.queries
    participant C as core.cache.Cache
    participant PB as core.powerbi
    participant API as Power BI API
    B->>G: GET /d/pani-processing/mining
    G->>G: current_user? (None → 302 login / 401 untuk /api/)
    G->>G: can_open? (tidak → audit access_denied + 403 denied.html / JSON)
    G->>G: GET halaman di pages → db.add_history
    G->>Rt: lanjut
    Rt->>Q: mining_bounds(), date_range() (clamp ke rentang data)
    Q->>C: get(key, load)
    C->>PB: query(DATASET, dax) (cache miss)
    PB->>API: POST /groups/{ws}/datasets/{ds}/executeQueries (Bearer token)
    API-->>PB: results[0].tables[0].rows
    PB-->>Q: list of dict
    Q-->>Rt: data, fetched
    Rt-->>B: render pani_processing/mining.html (extends dashboard/base.html)
    Note over Rt,B: DATA_ERRORS → errors.data_error_page → 502 + kode ref (detail hanya di log)
```

| | |
|---|---|
| Kondisi gagal | 403 (tanpa akses), 502 (Power BI), halaman "No data available yet" (tabel kosong) |
| Cara uji | `test_login_and_access.py::test_direct_url_to_other_dashboard_is_403`, `test_errors_and_security.py::test_empty_model_shows_no_data_page` |

## 6. Urutan hook per request

`before_request` app (CSRF, hanya POST) → `before_app_request` auth (`require_password_change`) →
`before_request` blueprint (dashboard: `_guard`) → view → `after_request` (security headers) →
`teardown_appcontext` (tutup koneksi DB).

Pengecualian: `require_password_change` mengizinkan endpoint `auth.change_password`, `auth.logout`, `auth.login`,
`static`, dan `*.static`.
