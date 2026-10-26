# 10 — Frontend / Backend Contract

Semua route `Verified` dari `app.url_map` (34 route) dan source. Kolom "Dilindungi" = pemeriksaan di **server**.

## 1. Daftar route

| Method | URL | Endpoint | Respons | Dilindungi | Dipanggil dari |
|---|---|---|---|---|---|
| GET/POST | `/login` | `auth.login` | HTML; POST sukses → 302 | CSRF (POST), throttle IP, lockout | Browser |
| GET/POST | `/forgot-password` | `auth.forgot_password` | HTML (pesan sama untuk semua email) | CSRF, throttle IP (5/15 mnt) | `login.html` |
| GET/POST | `/account/password` | `auth.change_password` | HTML | login, CSRF | top bar, redirect wajib ganti |
| GET | `/auth/microsoft` | `auth.microsoft` | 302 ke Microsoft | — | `login.html` |
| GET | `/auth/callback` | `auth.callback` | 302 | state MSAL | Microsoft |
| POST | `/logout` | `auth.logout` | 302 | CSRF | top bar (form) |
| GET | `/` | `portal.home` | HTML | login | — |
| GET | `/reports` | `portal.reports` | HTML (`?q=`, `?category=`) | login | sidebar, search top bar |
| GET | `/favorites`, `/history`, `/settings` | `portal.*` | HTML | login | sidebar |
| POST | `/api/favorites/<slug>` | `portal.toggle_favorite` | JSON `{favorite: bool}` / 404 | login, CSRF header, `can_open` | `shell.js` |
| GET | `/admin/users`, `/admin/users/new`, `/admin/users/<id>`, `/admin/dashboards`, `/admin/audit` | `admin.*` | HTML | `admin_required` | sidebar (Super Admin) |
| POST | `/admin/users/new`, `/admin/users/<id>/access`, `/status`, `/reset-password`, `/dismiss-reset`, `/admin/dashboards/<id>/status` | `admin.*` | 303 / HTML password sementara (`Cache-Control: no-store`) | `admin_required`, CSRF | form admin |
| POST | `/d/<slug>/api/chat` | `chat.chat` | JSON | login (401), `can_open` (403), rate limit (429), CSRF header | `chat.js` |
| GET | `/d/material-readiness/` | `material_readiness.summary` | HTML + `window.SUMMARY` | `_guard` | menu report |
| GET | `/d/material-readiness/detail` | `material_readiness.detail` | HTML + `window.DETAIL` | `_guard` | menu report |
| GET | `/d/material-readiness/api/detail` | `material_readiness.api_detail` | JSON | `_guard` (401/403 JSON) | `detail.js` |
| GET | `/d/material-readiness/api/detail/export` | `material_readiness.api_detail_export` | TSV `text/tab-separated-values` | `_guard` | `detail.js` (Copy) |
| GET | `/d/pani-processing/`, `/equipment`, `/mining`, `/production` | `pani_processing.*` | HTML + `window.PANI` | `_guard` | menu report, form filter |
| GET | `/static/<path>` | `static` | file | publik | template |
| GET | `/d/<slug>/static/<path>` | `<bp>.static` | file | `_guard` (login + akses) | template dashboard |

Perilaku teruji di localhost (26 Okt 2026, tanpa login): `/` → 302 `/login`; `/reports` → 302
`/login?next=/reports`; `/d/material-readiness/api/detail` → 401 JSON; `/d/pani-processing/static/pani.js` → 302
login; `/static/css/shell.css` → 200; POST `/login` tanpa CSRF → 400; `/tidak-ada` → 404.

## 2. CSRF

- Token: `session["_csrf"]` dibuat oleh `csrf_token()` (context processor), dicetak di `<meta name="csrf-token">`
  (`base.html`) dan field `<input name="_csrf">` di form.
- Form: kirim `_csrf`. `fetch`: header `X-CSRF-Token` (dipakai `shell.js` & `chat.js`).
- Semua POST tanpa token valid → 400 "Invalid security token...".

## 3. Kontrak data per halaman

### Material Readiness Summary — `window.SUMMARY`
`{data: <cube>, logo: {company: url}, curY, curM, detailUrl}` (dari `routes.summary`). Header: `header` =
`stamp_info(fetched)` → `{date, time}`.

### Material Readiness Detail
`window.DETAIL` = `{api, exportUrl, logo}`. Request `GET api?<query>`; parameter (`queries.parse_filters`):

| Param | Nilai | Default |
|---|---|---|
| `type` | `PO` / `SO` | `PO` |
| `tm` | `"0"` = pakai `year`/`month`; selain itu bulan ini (WIB) | bulan ini |
| `year`, `month` | angka | — |
| `company`, `plant`, `warehouse`, `status`, `doc`, `week`, `q` | teks | kosong |
| `sort` | kolom di `VIEWS[type]` | `start_date` |
| `dir` | `asc` / `desc` | `asc` |
| `page` | ≥ 1 | 1 |
| `size` | 25 / 50 / 100 / 200 | 50 |

Respons JSON: `{filters, columns:[{key,label,kind}], rows, total, matched, page, pages, size, kpi, tabs, options,
fetched:{date,time}}`. `total` = baris dimuat (maks `DETAIL_LIMIT` 15.000), `matched` = semua baris cocok. Error →
502 `{error: "Could not load data from Power BI... (ref XXXX)", ref}`.

### PANI — `window.PANI`
`{company, logo, data}` (dari `routes._page`). Query string: `start`, `end` (`YYYY-MM-DD`, di-clamp ke rentang data);
`/equipment` juga `status=active|inactive`. Template menerima `d` (data), `bounds`, `header`, `refresh`.

### Chat
Request `POST /d/<slug>/api/chat`, `Content-Type: application/json`, header `X-CSRF-Token`:
```json
{"message": "teks (maks 1000)", "history": [{"role": "user|model", "text": "..."}],
 "context": "teks filter aktif (maks 500)", "filters": {"...": "dari window.DashFilters()"}}
```
Respons 200: `{"answer": "markdown", "tools": [{"name", "label", "args"}], "model": "nama model"}`.
Error: `{"error": "pesan aman"}` dengan status 400 / 401 / 403 / 404 / 429 / 502 / 503.

`window.DashFilters()` per dashboard → `ChatSpec.parse_dash`:
Material Readiness `{year, month, company}`; PANI `{page, start, end}`.

### Favorit
`POST /api/favorites/<slug>` header `X-CSRF-Token` → `{"favorite": true|false}`.

## 4. Aturan mengubah kontrak

1. Cari semua pemakai: `grep` key JSON di `static/**/*.js` dan template.
2. Tambah field = aman (backward compatible). Ganti/hapus field = ubah backend + JS + test dalam satu perubahan.
3. URL tidak diganti (bisa ada di Favorites/History user dan bookmark); kalau terpaksa, sediakan redirect.
Detail: [19_BACKEND_AND_DATA_CONTRACT_CHANGES](19_BACKEND_AND_DATA_CONTRACT_CHANGES.md).
