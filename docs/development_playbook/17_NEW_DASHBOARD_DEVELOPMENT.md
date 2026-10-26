# 17 — Workflow B: Menambah Dashboard Baru ke Portal

Contoh berjalan: dashboard **Work Order** (`work-order`).

### A. Objective
Dashboard baru muncul di katalog, hanya bisa dibuka user berwenang, menampilkan data benar dari semantic model,
dan (jika dibutuhkan) punya AI agent.

### B. When to use
Ada semantic model / report Power BI baru yang ingin dibawa ke portal.

### C. Prerequisites
- Workspace ID & dataset ID (dari URL `app.powerbi.com/groups/<WORKSPACE_ID>/datasets/<DATASET_ID>/...`).
- Service principal `mantra-powerbi` sudah Contributor di workspace itu.
- Baseline test lulus.

### D. Architecture context
Dashboard = sub-package di `mantra/dashboards/` dengan variabel `DASHBOARD` ([14](14_DASHBOARD_REGISTRY.md)).
Tidak ada file core yang perlu diubah.

### E. Files involved
Semua dibuat oleh generator di `mantra/dashboards/<nama>/`:
`__init__.py`, `queries.py`, `routes.py`, `tools.py`, `chat_cases.py`, `prompts/system.md`,
`prompts/data_dictionary.md`, `templates/<nama>/overview.html`, `static/.gitkeep`.
Tambahan: `tests/conftest.py` (`PAGES`), dokumentasi.

---

## B1 — Analisis kebutuhan

| Item | Isi |
|---|---|
| Nama / slug | Work Order / `work-order` (huruf kecil, dipisah `-`) |
| Halaman | mis. Overview, Detail |
| KPI, filter | ... |
| Semantic model | workspace & dataset ID |
| Siapa yang boleh membuka | daftar user (diberi lewat Admin > Users) |
| Butuh AI? | Ya/Tidak (jika tidak, hapus `chat=ChatSpec(...)` dari manifest) |

## B2 — Pelajari dashboard referensi
- Data tabel besar + filter dinamis → pelajari **Material Readiness** (Summary SSR + Detail AJAX).
- Halaman KPI per periode tanggal → pelajari **PANI** (SSR + form GET).

## B3 — Generate struktur

Generator: `scripts/create_dashboard.py` (Verified). Argumen: `<slug> "<Judul>"`. Tanpa argumen → mencetak
cara pakai. Menolak slug tidak valid dan **menolak jika folder sudah ada** (tidak menimpa).

```powershell
python scripts\create_dashboard.py work-order "Work Order"
```
Expected output (Tested di salinan sandbox, 26 Okt 2026):
```
Dashboard dibuat: mantra\dashboards\work_order
Langkah berikutnya:
  1. Isi workspace_id & dataset_id di mantra\dashboards\work_order\queries.py
  2. Start Flask: dashboard otomatis masuk katalog. Beri akses user di Admin > Users (Super Admin otomatis bisa)
  3. Beri mantra-powerbi akses ke workspace-nya, lalu: python scripts\check_setup.py
  4. Restart Flask dan buka http://localhost:<PORT dari .env, default 5001>/d/work-order/
```
Placeholder yang diganti: `__SLUG__` → `work-order`, `__NAME__` → `work_order` (nama folder, blueprint, folder
template), `__TITLE__` → `Work Order`, `__ENV__` → `WORK_ORDER` (prefix `.env`). Cek: tidak ada sisa placeholder:
```powershell
Get-ChildItem mantra\dashboards\work_order -Recurse -File | Select-String -Pattern "__SLUG__|__NAME__|__TITLE__|__ENV__"
```
(perintah ini tidak boleh menghasilkan baris; versi `bash`: `grep -rn "__SLUG__\|__NAME__" mantra/dashboards/work_order`).

## B4 — Registrasi
Tidak ada langkah manual: restart server → registry memuat folder baru → `sync_dashboards` menambah baris di tabel
`dashboards` (aktif). Hasil uji sandbox: dashboard terdaftar, `ready=False`, `url=None` (kartu "Coming soon"),
route `/d/work-order/` dan `/d/work-order/static/...` terpasang, katalog DB berisi `('work-order', 'Work Order', 1)`.

Beri akses: Admin > Users > pilih user > centang dashboard, atau
`python scripts\manage_users.py set-access --email x@merdeka.com --dashboard work-order` (daftar **baru**, menggantikan
yang lama: sertakan juga dashboard lain milik user itu).

## B5 — Backend & data
1. `queries.py`: isi `workspace_id`, `dataset_id`; jalankan `python scripts\check_setup.py` (akses workspace + model).
2. Baca struktur model: `python scripts\check_setup.py --dashboard work-order --dax "EVALUATE INFO.VIEW.COLUMNS()"`.
3. Ganti `tables()` dengan query sebenarnya (pola dok 15: cache, `dax_str`, return `(data, fetched)`).
4. `routes.py`: satu fungsi per halaman, tangkap `queries.DATA_ERRORS` → `data_error_page`.
5. `__init__.py`: `pages=[("Overview", "work_order.overview"), ...]`, isi `description`, `category`, `icon`
   (nama di `portal/_ui.html`), `color`, `order`.

## B6 — Frontend
Template di `templates/work_order/` extend `dashboard/base.html` (blok di dok 08). CSS/JS khusus di
`static/` dan dimuat dengan `url_for('work_order.static', filename=...)` (file static ikut dijaga `_guard`).
Untuk chat: definisikan `window.DashContext()` (teks filter) dan `window.DashFilters()` (dict untuk `parse_dash`).

## B7 — AI agent (opsional)
Ikuti [33_ADD_AI_AGENT_TO_DASHBOARD](33_ADD_AI_AGENT_TO_DASHBOARD.md). Jika tidak butuh AI: hapus argumen `chat=`
dari manifest (tombol Ask AI tidak muncul, `/api/chat` → 404).

## B8 — Testing & validasi portal
1. Tambah URL halaman ke `PAGES` di `tests/conftest.py` → test akses mencakup dashboard baru.
2. **Perhatikan** `tests/test_login_and_access.py:ALL = {"material-readiness", "pani-processing"}`: test
   `test_super_admin_sees_all_active_dashboards` membandingkan link `href="/d/<slug>/"` di Reports dengan `ALL`.
   Selama `ready=False` kartu tidak punya link (`url=None`), jadi test masih lulus; **setelah `ready=True`** test
   gagal sampai slug baru ditambahkan ke `ALL`. Ini perilaku benar; perbarui test bersamaan dengan `ready=True`.
3. `python -m pytest`, `python scripts\check_ai_agent.py --static`.
4. Manual: Super Admin melihat kartu; user tanpa akses tidak melihat kartu dan URL langsung → 403.
5. Regresi: Material Readiness & PANI tetap terbuka.

## B9 — Acceptance & go-live
1. Ubah `ready=True` di `__init__.py` (wajib punya `blueprint` & `pages`), restart.
2. Kartu tidak lagi "Coming soon".
3. Dokumentasikan di README (tabel status dashboard) dan dok 01.

---

### I. Commands
```powershell
python scripts\create_dashboard.py work-order "Work Order"
python scripts\check_setup.py
python -m pytest
python run.py
```
### J. Expected result
Kartu "Work Order" di Reports; `/d/work-order/` menampilkan daftar tabel semantic model (halaman contoh).
### K. Validation
Login sebagai user tanpa akses → URL langsung 403; Admin > Audit Log mencatat `access_denied`.
### L. Troubleshooting
| Gejala | Penyebab / solusi |
|---|---|
| App gagal start: `tool belum dijelaskan di prompt` | Setiap tool di `tools.py` wajib disebut `` `nama_tool` `` di `prompts/*.md` |
| `placeholder tidak dikenal` | Placeholder di prompt bukan core / tidak ada di `ChatSpec.placeholders` |
| `Slug dashboard dobel` | Slug sama dengan dashboard lain |
| Kartu tidak muncul untuk user | Belum diberi akses / dashboard nonaktif |
| Halaman "Could not load data" | ID dataset salah atau SP belum punya akses (lihat log dengan kode ref) |
| `/d/work-order/` terbuka padahal `ready=False` | By design saat ini (route tetap terpasang, dijaga `_guard`); lihat known issues dok 28 |
### M. Regression impact
Test yang menghitung jumlah dashboard (`ALL`); halaman Reports/Home (kartu baru).
### N. Acceptance criteria
B9 selesai, test lulus, angka tervalidasi, dokumentasi diperbarui.
### O. Documentation updates
README (status dashboard), dok 01, data dictionary.
### P. Actual status
| Item | Status |
|---|---|
| Generator: buat folder, ganti placeholder, tolak folder sudah ada, tolak slug salah | PASS (salinan sandbox) |
| Registry memuat dashboard baru, katalog DB terisi, kartu "Coming soon" | PASS (salinan sandbox) |
| Koneksi ke semantic model baru | NOT RUN |
| `ready=True` + data asli | NOT RUN |
