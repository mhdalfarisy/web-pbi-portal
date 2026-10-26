# 16 — Workflow A: Menambah Halaman ke Dashboard yang Sudah Ada

Contoh berjalan: menambah halaman **"Mining Detail"** ke PANI Processing (`/d/pani-processing/mining-detail`).
Pola yang sama berlaku untuk Material Readiness (perbedaannya di bagian A6).

### A. Objective
Halaman baru tampil di menu header dashboard, dilindungi hak akses, memakai layout bersama, dan angkanya benar.

### B. When to use
Dashboard sudah terdaftar dan berjalan; butuh tampilan/analisis baru dari semantic model yang **sama**.
Kalau semantic model berbeda → pertimbangkan dashboard baru ([17](17_NEW_DASHBOARD_DEVELOPMENT.md)).

### C. Prerequisites
- Server & test berjalan (baseline `58 passed`).
- Akses Power BI (untuk data asli) atau rencana memakai stub di test.
- Paham [08](08_FRONTEND_ARCHITECTURE.md), [10](10_FRONTEND_BACKEND_CONTRACT.md), [15](15_POWERBI_INTEGRATION.md).

### D. Architecture context
`DASHBOARD.pages` menentukan menu header (`dashboard/base.html`), breadcrumb (`topbar.html`), dan History
(`_guard` hanya mencatat endpoint di `pages`). Route di blueprint dashboard otomatis dijaga `_guard`.

---

## A1 — Analisis kebutuhan (isi sebelum coding)

| Item | Contoh |
|---|---|
| Tujuan | Rincian movement harian per leaf |
| Pengguna | User yang sudah punya akses PANI |
| KPI / tabel / chart | Tabel harian actual vs plan |
| Filter | Rentang tanggal (`?start=&end=`) |
| Sumber data | Tabel `mpx_daily_pondok_view` (sudah dipakai `queries.mining`) |
| Akses | Sama dengan dashboard (tidak ada aturan baru) |
| Acceptance | Angka = kolom DAILY report Power BI untuk filter yang sama |

## A2 — Audit halaman yang mirip
Baca `routes.mining`, `queries.mining`, `queries.mining_bounds`, `templates/pani_processing/mining.html`,
`_ui.html` (`filters`, `scripts`), `static/pani.js`, dan `tests/conftest.py` (`PAGES`).

## A3 — File yang diubah

| File | Wajib? | Perubahan | Dampak ke halaman lain | Test |
|---|---|---|---|---|
| `pani_processing/queries.py` | Wajib jika data baru (boleh pakai ulang `mining()`) | Fungsi query + cache key unik | Tidak, jika fungsi lama tidak diubah | unit/stub |
| `pani_processing/routes.py` | Wajib | Route baru | Tidak | akses |
| `pani_processing/__init__.py` | Wajib | Tambah ke `pages` | Menu header semua halaman PANI bertambah | akses |
| `templates/pani_processing/mining_detail.html` | Wajib | Template baru | Tidak | render |
| `static/pani.css` / `pani.js` | Opsional | Gaya/chart | Semua halaman PANI | manual |
| `tests/conftest.py` (`PAGES`) | Wajib | Tambah URL | Test akses otomatis mencakup halaman baru | `test_login_and_access` |
| `tools.py` + `prompts/system.md` | Opsional | Jika AI perlu data baru | Prompt divalidasi saat start | `check_ai_agent --static` |

## A4 — Backend

Kapan butuh route baru: selalu untuk halaman baru. Query baru: hanya jika data/agregasi belum ada; **utamakan
memakai ulang** fungsi `queries.py` supaya angka halaman, halaman lain, dan AI tetap sama.

```python
# pani_processing/routes.py  (Proposed, mengikuti pola routes.mining)
@bp.get("/mining-detail")
def mining_detail():
    try:
        b = queries.mining_bounds()
        if not queries.has_data(b):
            return _no_data()
        start, end = _range(b, date(b["last"].year, b["last"].month, 1), b["last"])
        data, fetched = queries.mining(start, end)        # pakai ulang query yang sudah tervalidasi
        return _page("mining_detail.html", data, fetched, b)
    except queries.DATA_ERRORS as exc:
        return data_error_page(exc)
```
- Validasi input: `_range` → `parse_date` + `date_range` (clamp ke data; tanggal tidak valid → default).
- Authorization: otomatis oleh `_guard` (jangan tambah cek sendiri, jangan hapus).
- Error: `DATA_ERRORS` → `data_error_page` (502 + ref). Data kosong → `_no_data()`.
- Kontrak `_page`: `data` **wajib** punya key `company` (header), `start`, `end` (macro `filters`).

```python
# pani_processing/__init__.py
pages=[("Processing", "pani_processing.processing"), ("Equipment", "pani_processing.equipment"),
       ("Mining", "pani_processing.mining"), ("Mining Detail", "pani_processing.mining_detail"),
       ("Production", "pani_processing.production")],
```
Catatan: `.hd-nav` di `pani.css` memakai `grid-template-columns: repeat(2, auto)`; 5 menu akan membentuk 3 baris.
Periksa tampilan dan sesuaikan CSS bila perlu.

## A5 — Frontend

```jinja
{# templates/pani_processing/mining_detail.html (Proposed) #}
{% extends "dashboard/base.html" %}
{% from "pani_processing/_ui.html" import filters, picon, scripts with context %}
{% block title %}Mining Detail - PANI{% endblock %}
{% block head %}<link rel="stylesheet" href="{{ url_for('pani_processing.static', filename='pani.css') }}">{% endblock %}
{% block main_title %}Mining Detail{% endblock %}
{% block pill %}Mining Detail{% endblock %}
{% block content %}
<div class="pg">
  {{ filters(d, bounds) }}
  <section class="panel">
    {# tabel / chart di sini; pakai helper fmt / sgn / tone dari context processor routes.helpers #}
  </section>
</div>
{{ scripts() }}
{% endblock %}
```
- Sidebar & top bar otomatis (jangan disalin).
- Loading antar halaman: `shell.js` (otomatis). Empty state: `dashboard/empty.html` via `_no_data()`. Error state:
  `dashboard/error.html` via `data_error_page`.
- Chart: `Pani.combo(el, cfg)` / `Pani.spark(el, values, color)` di dalam `Pani.onResize(fn)` (lihat `mining.html`).

## A6 — Integrasi data

PANI: SSR, filter lewat form GET (reload). Material Readiness: Summary memakai data cube di-embed, Detail memakai
`fetch` ke `/api/detail`. Untuk halaman Material Readiness yang butuh data dinamis, tambahkan endpoint
`/api/<nama>` di `routes.py` yang mengembalikan JSON dan memakai `data_error_json` untuk error; panggil dari JS
dengan `fetch(url, {headers: {Accept: 'application/json'}})` (pola `detail.js`). Endpoint `/api/...` di blueprint
dashboard otomatis mendapat 401/403 JSON dari `_guard`.

## A7 — Testing

1. Tambah URL ke `PAGES["pani-processing"]` di `tests/conftest.py` → test akses (anonim, user tanpa akses = 403,
   user berizin) otomatis mencakup halaman baru.
2. Jika ada query baru, tambah test dengan stub (pola `_stub_pani` di `test_errors_and_security.py`).
3. `python -m pytest`.
4. Manual: buka halaman, ganti tanggal, cek angka vs report Power BI, cek browser console (F12) bebas error,
   cek log server, cek lebar 1280 / 1000 / 800 px.
5. Regresi: buka 4 halaman PANI lain + Material Readiness.

## A8 — Dokumentasi & release lokal
Perbarui tabel halaman di dok 01/10, `prompts/data_dictionary.md` jika istilah baru, commit dengan pesan jelas
([25](25_RELEASE_AND_ROLLBACK.md)).

---

### I. Commands
```powershell
python -m pytest
python scripts\check_ai_agent.py --static
python run.py
```
### J. Expected result
Menu "Mining Detail" muncul di header PANI; breadcrumb `Reports › PANI Processing › Mining Detail`; History mencatat.
### K. Validation
`curl -I http://localhost:5001/d/pani-processing/mining-detail` tanpa login → 302 ke login.
### L. Troubleshooting
| Gejala | Penyebab |
|---|---|
| `BuildError: Could not build url for endpoint` | Endpoint di `pages` salah tulis (harus `<blueprint>.<fungsi>`) |
| `TemplateNotFound` | Template tidak di `templates/pani_processing/` |
| Halaman tidak di menu | Belum ditambah ke `pages` atau server belum restart |
| `jinja2 UndefinedError ... 'company'` | `data` tidak punya key yang dibutuhkan `_page` |
| 403 untuk user berizin | User belum diberi akses dashboard (bukan per halaman) |
### M. Regression impact
`pages` memengaruhi menu semua halaman dashboard itu; `queries.py` bersama dipakai AI.
### N. Acceptance criteria
Route terlindungi, ada di `pages`, test akses mencakup URL baru, angka cocok dengan report, tanpa error console.
### O. Documentation updates
Dok 01, 10, data dictionary.
### P. Actual status
| Item | Status |
|---|---|
| Patch contoh (route + `pages` + template) diterapkan di **salinan sandbox**, dirender dengan data PANI di-stub (`AUTH_DISABLED=True`, DB sementara) | PASS (26 Okt 2026): HTTP 200, menu header & breadcrumb "Mining Detail" muncul, filter tanggal terisi, `/mining` lama tetap 200 |
| Patch diterapkan ke project asli | NOT RUN (contoh `Proposed`; tidak diubah) |
| Angka vs report Power BI | NOT RUN (butuh Power BI) |
| Tampilan 5 menu di `.hd-nav` | PENDING (cek visual) |
