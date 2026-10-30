# Pendalaman 1 — Konsep Teknologi yang Dipakai

> Bagian dari [Panduan Development Berurutan](../PANDUAN_DEVELOPMENT_BERURUTAN.md). Baca bab ini **sebelum** fase yang
> memakai konsepnya (kolom "Dipakai di" pada setiap judul). Setiap konsep ditutup dengan bagian **Di project ini**
> (file nyata yang memakainya) dan **Latihan** kecil yang bisa dicoba di terminal.

## Daftar isi

1. [Virtual environment & pip](#1-virtual-environment--pip) — Fase 0
2. [File `.env` dan python-dotenv](#2-file-env-dan-python-dotenv) — Fase 1
3. [Flask: aplikasi, route, dan blueprint](#3-flask-aplikasi-route-dan-blueprint) — Fase 2, 4-6, 9-10
4. [Flask: siklus request, `g`, `session`, hook](#4-flask-siklus-request-g-session-hook) — Fase 2-6
5. [Jinja: template, pewarisan, macro](#5-jinja-template-pewarisan-macro) — Fase 4, 6, 8, 10
6. [SQLite dan migrasi berbasis `user_version`](#6-sqlite-dan-migrasi-berbasis-user_version) — Fase 3
7. [Keamanan web yang dipakai portal](#7-keamanan-web-yang-dipakai-portal) — Fase 4, 14
8. [Microsoft Entra ID & MSAL](#8-microsoft-entra-id--msal) — Fase 4 (SSO), Fase 7
9. [Power BI REST API & DAX](#9-power-bi-rest-api--dax) — Fase 7, 10, 12
10. [Thread, lock, rate limit, dan cache](#10-thread-lock-rate-limit-dan-cache) — Fase 4, 7, 11
11. [Frontend tanpa framework](#11-frontend-tanpa-framework) — Fase 6, 8, 10
12. [LLM function calling (AI agent)](#12-llm-function-calling-ai-agent) — Fase 11
13. [pytest: fixture dan monkeypatch](#13-pytest-fixture-dan-monkeypatch) — Fase 13

---

## 1. Virtual environment & pip

**Masalahnya.** Python global di Mac dipakai banyak project. Di Mac ini, `python3` global menunjuk Python 3.14 milik
venv project lain (`project_data_engineer/venv`). Kalau MANTRA memasang Flask ke sana, versi bisa bentrok, dan
project lain ikut rusak.

**Konsepnya.** `python3.13 -m venv .venv` membuat folder `.venv/` berisi **salinan interpreter + folder
`site-packages` sendiri**. `source .venv/bin/activate` hanya mengubah `PATH` di terminal itu supaya `python` dan
`pip` menunjuk ke `.venv/bin/`. Tidak ada yang "dipasang ke sistem".

| Perintah | Artinya |
|---|---|
| `python3.13 -m venv .venv` | buat venv dengan Python 3.13 (versi eksplisit) |
| `source .venv/bin/activate` | aktifkan di terminal ini saja; prompt diawali `(.venv)` |
| `pip install -r requirements.txt` | pasang semua library di daftar, ke `.venv` |
| `deactivate` | kembali ke Python global |
| `.venv/bin/python run.py` | pakai Python venv **tanpa** aktivasi (cara `run_mantra.command`) |

**Rentang versi** di [requirements.txt](../../requirements.txt), mis. `Flask>=3.0,<4`: boleh versi 3.x terbaru,
tidak boleh 4.0 (versi mayor baru bisa mengubah API). `requirements-dev.txt` diawali `-r requirements.txt`, jadi
memasangnya juga memasang dependency runtime.

**Di project ini:** `run_mantra.command` memanggil `.venv/bin/python` langsung; README memperingatkan error
`cannot import name 'genai' from 'google'` yang muncul kalau Python global dipakai.

**Latihan.**
```bash
which python                     # sebelum aktivasi: Python global
source .venv/bin/activate
which python                     # sesudah: .../web-pbi-portal/.venv/bin/python
python -c "import flask; print(flask.__version__, flask.__file__)"   # file-nya ada di dalam .venv
```

---

## 2. File `.env` dan python-dotenv

**Konsepnya.** Secret (client secret, API key) tidak boleh ada di kode karena kode masuk git. Nilainya ditaruh di file
`.env` (di-*ignore* git), lalu dibaca saat start menjadi **environment variable** proses.

`python-dotenv` menyediakan dua fungsi yang dipakai [mantra/config.py](../../mantra/config.py):

| Fungsi | Hasil |
|---|---|
| `dotenv_values(path)` | dict isi file `.env` **tanpa** mengubah `os.environ` |
| `load_dotenv(path, override=True)` | salin isi `.env` ke `os.environ`; `override=True` = timpa variabel yang sudah ada |

**Kenapa `override=True` penting di project ini.** Extension Python di VS Code bisa membawa `.env` project lain ke
terminal (setting `python.terminal.useEnvFile`). Tanpa override, `PBI_CLIENT_ID` milik project lain diam-diam dipakai.
`config.py` juga menghitung `ENV_OVERRIDDEN` (nama variabel yang tertimpa) untuk peringatan di log, **tanpa nilainya**.

**Kenapa `AUTH_DISABLED` dibaca beda.** `_env_file_flag("AUTH_DISABLED")` membaca dari hasil `dotenv_values`, bukan
`os.environ`. Akibatnya `AUTH_DISABLED=1` yang tertinggal di terminal **tidak** bisa mematikan login; hanya baris di
file `.env` yang dihitung.

**Jebakan nilai kosong.** Baris `PBI_CLIENT_ID=` (kosong) membuat `os.environ["PBI_CLIENT_ID"] = ""`, bukan "tidak
ada". Karena itu `config.py` menulis `os.environ.get("PORT") or 5001` (string kosong dianggap tidak diisi), dan karena
itu pula satu test gagal kalau baris itu kosong (lihat panduan §7).

**Latihan.**
```bash
python -c "from dotenv import dotenv_values; print(sorted(dotenv_values('.env')))"   # nama variabel saja
PORT=9999 python -c "from mantra.config import Config; print(Config.PORT)"           # tetap nilai .env: override=True
```

---

## 3. Flask: aplikasi, route, dan blueprint

**Aplikasi.** `Flask(__name__)` adalah objek WSGI: menerima request HTTP, memilih fungsi Python (*view*), dan
mengembalikan response. `app.run()` menjalankan **development server** Werkzeug (satu proses, multi-thread). Untuk
production dipakai server WSGI seperti gunicorn; itu sebabnya log start mencetak peringatan "development server".

**Application factory.** Daripada membuat `app` di tingkat modul, MANTRA membuat fungsi `create_app(test_config)`
([mantra/\_\_init\_\_.py](../../mantra/__init__.py)). Setiap pemanggilan menghasilkan app baru. Manfaatnya: test bisa
membuat app dengan database sementara (`tests/conftest.py`), dan script di `scripts/` bisa memakai app tanpa
menjalankan server.

**Route & endpoint.**
```python
@bp.get("/reports")          # URL + method
@login_required              # decorator dijalankan dari bawah ke atas: cek login dulu
def reports():               # nama fungsi = bagian dari nama endpoint
    ...
```
Nama endpoint = `<nama blueprint>.<nama fungsi>`, mis. `portal.reports`. Template dan kode **tidak pernah** menulis
URL mentah; mereka memanggil `url_for("portal.reports")`. Kalau endpoint belum ada, `url_for` melempar `BuildError`
(inilah alasan stub `portal.py` di Fase 4).

**Blueprint.** Kelompok route + template + file static yang bisa didaftarkan ke app.
```python
bp = Blueprint("material_readiness", __name__, url_prefix="/d/material-readiness",
               template_folder="templates", static_folder="static")
```
| Argumen | Efek |
|---|---|
| `"material_readiness"` | prefix nama endpoint (`material_readiness.summary`) |
| `url_prefix` | semua route blueprint diawali `/d/material-readiness` |
| `template_folder` | folder template tambahan (karena itu template dashboard diberi subfolder bernama dashboard, supaya tidak bentrok) |
| `static_folder` | file static milik blueprint, di-URL-kan dengan `url_for("material_readiness.static", filename=...)` |

**Di project ini:** blueprint `auth`, `portal`, `admin`, `chat`, dan satu blueprint per dashboard. Dashboard tidak
didaftarkan manual: `registry.init_app` mencari folder di `mantra/dashboards/` lalu mendaftarkan blueprint-nya.

**Latihan.**
```bash
python - <<'EOF'
from mantra import create_app
app = create_app()
for r in sorted(app.url_map.iter_rules(), key=lambda r: r.rule)[:8]:
    print(r.rule, "->", r.endpoint)
EOF
```

---

## 4. Flask: siklus request, `g`, `session`, hook

Urutan yang terjadi untuk **setiap** request di MANTRA:

```
request masuk
 ├─ app.before_request          csrf_protect                (mantra/__init__.py)   hanya POST
 ├─ before_app_request          require_password_change     (core/auth.py)         semua blueprint
 ├─ blueprint.before_request    _guard(dashboard)           (core/registry.py)     hanya blueprint dashboard
 ├─ decorator view              @login_required / @admin_required
 ├─ view function               mis. portal.reports()
 │    └─ render_template  ──>  context_processor inject_globals menambah variabel ke template
 ├─ app.after_request           security_headers
 └─ teardown_appcontext         db._close_db (tutup koneksi SQLite)
```
Kalau sebuah hook **mengembalikan nilai** (redirect, response), Flask berhenti di situ dan view tidak dijalankan. Itulah
cara `_guard` menolak akses (403) dan `require_password_change` memaksa redirect.

**`g`** = tempat menyimpan data **selama satu request** (hilang setelah response). MANTRA menyimpan koneksi DB
(`g.db`), user yang sedang login (`g.user`), dan slug yang boleh dibuka (`g.allowed_slugs`) supaya tidak dihitung
berulang dalam satu request.

**`session`** = dict yang disimpan di **cookie browser**, ditandatangani dengan `SECRET_KEY` (isi bisa dibaca, tetapi
tidak bisa diubah tanpa ketahuan). Karena itu MANTRA hanya menyimpan `uid` (id user) dan `sv` (session_version),
lalu membaca ulang user dari database di setiap request. Setting cookie di `config.py`: `HttpOnly` (tidak bisa dibaca
JavaScript), `SameSite=Lax` (tidak ikut terkirim pada POST lintas situs), `Secure` (hanya HTTPS, wajib di production).

**`context_processor`** = fungsi yang mengembalikan dict; isinya otomatis tersedia di **semua** template. Sidebar dan
top bar membutuhkan `current_user`, `user_is_admin`, `chat_enabled`, dst., jadi satu kunci yang hilang membuat semua
halaman error.

**`flash()`** = pesan sekali tampil (disimpan di session, dibaca `get_flashed_messages()` di template berikutnya).

**Latihan.** Ubah sementara `security_headers` agar mencetak `request.path`, jalankan server, buka dua halaman, lalu
lihat urutan log. Kembalikan setelahnya.

---

## 5. Jinja: template, pewarisan, macro

| Fitur | Contoh di MANTRA | Fungsi |
|---|---|---|
| `{% extends "base.html" %}` + `{% block main %}` | `portal/base.html`, `dashboard/base.html` | template anak mengisi "lubang" milik template induk |
| `{% macro icon(name) %}` | `portal/_ui.html`, `dashboard/_icons.html` | fungsi kecil yang menghasilkan HTML |
| `{% from "components/sidebar.html" import sidebar with context %}` | `base.html` | memanggil macro dari file lain; `with context` = macro boleh membaca variabel template (mis. `current_user`) |
| `{{ payload\|tojson }}` | `summary.html` | ubah dict Python jadi JSON yang aman ditanam di `<script>` |
| autoescape | semua `.html` | `{{ x }}` otomatis di-escape (`<` jadi `&lt;`), mencegah XSS |
| `{% set report = dashboard %}` | `dashboard/base.html` | variabel lokal; di sini dipakai sidebar & breadcrumb |

**Rantai pewarisan MANTRA**:
```
base.html              (sidebar + topbar + <main> + loader)
 ├─ portal/base.html   (+ portal.css, flash, portal.js)  ← home, reports, admin/*
 └─ dashboard/base.html (+ header biru, panel AI)        ← summary.html, processing.html, ...
portal/bare.html       (tanpa sidebar)                   ← ganti password wajib, error sebelum login
portal/_auth_layout.html                                 ← login, forgot password
```

**Latihan.** Di `templates/portal/settings.html`, tambahkan sementara `<pre>{{ current_user|tojson }}</pre>`, buka
`/settings`, lihat isinya, lalu hapus lagi.

---

## 6. SQLite dan migrasi berbasis `user_version`

**SQLite** = database dalam satu file (`instance/mantra.db`), tanpa server. Cocok untuk data portal yang kecil
(akun, akses, audit). Data dashboard **tidak** disimpan di sini.

| Konsep | Di [core/db.py](../../mantra/core/db.py) | Kenapa |
|---|---|---|
| `conn.row_factory = sqlite3.Row` | `connect()` | baris bisa dibaca seperti dict: `row["email"]` |
| `PRAGMA foreign_keys = ON` | `connect()` | SQLite **mematikan** foreign key secara default; tanpa ini `ON DELETE CASCADE` tidak jalan |
| `PRAGMA user_version` | `migrate()` | angka bebas di header file DB; dipakai sebagai "versi skema" |
| `executescript("BEGIN; ...; COMMIT;")` | `migrate()` | satu migrasi = satu transaksi; gagal di tengah → `ROLLBACK` |
| `conn.backup(dest)` | `backup()` | salinan konsisten walau DB sedang dipakai |
| `COLLATE NOCASE` | kolom `users.email` | `A@x.com` dan `a@x.com` dianggap sama |
| `INSERT ... ON CONFLICT (slug) DO UPDATE` | `accounts.sync_dashboards` | *upsert*: tambah kalau belum ada, perbarui kalau sudah |

**Cara kerja migrasi.** `MIGRATIONS` adalah list SQL. Kalau `user_version` = 1 dan panjang list = 3, maka migrasi
ke-2 dan ke-3 dijalankan, lalu `user_version` diset 3. Karena itu **migrasi lama tidak boleh diubah**: laptop yang sudah
di versi 3 tidak akan menjalankannya lagi, sehingga skema antar laptop berbeda.

**Latihan.**
```bash
sqlite3 instance/mantra.db "PRAGMA user_version; .schema users"
sqlite3 instance/mantra.db "select action, count(*) from audit_log group by action"
```

---

## 7. Keamanan web yang dipakai portal

| Ancaman | Penangkal di MANTRA | Lokasi |
|---|---|---|
| Password bocor dari DB | simpan **hash** (`generate_password_hash`), bukan password | `core/accounts.py` |
| Menebak email terdaftar lewat waktu respons | email tak terdaftar tetap dicek ke `_DUMMY_HASH` | `accounts.authenticate` |
| Brute force | kunci akun 15 menit setelah 5 gagal + throttle 20 gagal/15 mnt per IP | `accounts.py`, `auth._IpThrottle` |
| CSRF (situs lain mengirim form atas nama user) | token acak per session, wajib di setiap POST (`_csrf` / header `X-CSRF-Token`) | `create_app.csrf_protect` |
| Session fixation | `session.clear()` sebelum login | `auth._start_session` |
| Sesi lama tetap aktif setelah reset password / nonaktif | `session_version` di DB dinaikkan; sesi dengan `sv` lama ditolak | `auth.current_user` |
| Open redirect (`?next=https://jahat.com`) | `_safe_next` hanya menerima path yang diawali `/` dan bukan `//` | `core/auth.py` |
| Clickjacking, MIME sniffing, kebocoran URL | `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin` | `security_headers` |
| Akses dashboard lewat URL langsung | `_guard` di setiap route blueprint dashboard (default deny) | `core/registry.py` |
| DAX injection dari input user | `dax_str()` menggandakan tanda kutip | `core/common.py` |
| Detail error Power BI bocor ke user | user hanya melihat pesan umum + `ref`; detail di log | `core/errors.py` |

**CSRF dalam satu kalimat:** browser otomatis mengirim cookie ke situs kita, jadi cookie saja tidak membuktikan
bahwa form berasal dari halaman kita; token rahasia yang hanya ada di halaman kita yang membuktikannya.

---

## 8. Microsoft Entra ID & MSAL

MANTRA memakai Entra untuk **dua hal berbeda**, dengan dua app registration:

| | App `mantra-powerbi` (data) | App `MANTRA Portal` (login, opsional) |
|---|---|---|
| Siapa yang login | **aplikasi itu sendiri** (service principal) | **manusia** |
| Alur OAuth | *client credentials* | *authorization code + PKCE* |
| Fungsi MSAL | `acquire_token_for_client(scopes=[".../.default"])` | `initiate_auth_code_flow` → redirect → `acquire_token_by_auth_code_flow` |
| Hasil | access token untuk Power BI REST API | `id_token_claims` berisi email user |
| File | [core/powerbi.py](../../mantra/core/powerbi.py) | [core/auth.py](../../mantra/core/auth.py) (`microsoft`, `callback`) |

**Client credentials:** app menukar `client_id` + `client_secret` menjadi token. Scope `.../.default` artinya "semua izin
yang sudah diberikan ke app ini". Izin ke workspace diberikan lewat grup `sg-powerbi-api` dan peran Contributor di
workspace. MSAL menyimpan token di memori dan memperbarui otomatis saat kedaluwarsa.

**Authorization code + PKCE:** browser diarahkan ke halaman login Microsoft, lalu kembali ke
`/auth/callback?code=...&state=...`. MSAL memeriksa `state` (anti CSRF) dan PKCE (anti pencurian code). MANTRA lalu
mencari email itu di tabel `users`; Entra **hanya** membuktikan identitas, hak akses tetap dari database.

---

## 9. Power BI REST API & DAX

**Endpoint yang dipakai:**
```
POST https://api.powerbi.com/v1.0/myorg/groups/<workspace_id>/datasets/<dataset_id>/executeQueries
Authorization: Bearer <token>
{"queries": [{"query": "EVALUATE ..."}], "serializerSettings": {"includeNulls": true}}
```
Respons: `results[0].tables[0].rows` = list dict dengan kunci seperti `'Tabel'[Kolom]` atau `[Measure]`.
`powerbi._clean_column` meringkasnya menjadi `Kolom`. Batas: 100.000 baris / 1 juta nilai per query, dan kuota per
service principal (karena itu ada rate limiter bersama).

**DAX = bahasa query semantic model.** Query selalu diawali `EVALUATE <ekspresi tabel>`. Fungsi yang dipakai MANTRA:

| Fungsi | Arti | Contoh di MANTRA |
|---|---|---|
| `EVALUATE t` | kembalikan tabel `t` | semua query |
| `DEFINE VAR _x = ...` | variabel di awal query | `_base`, `_rows` di Material Readiness |
| `CALCULATETABLE(t, filter1, ...)` | tabel `t` dengan filter tambahan | `_table()` |
| `TREATAS({"FP","ME"}, T[branch_code])` | filter kolom ke daftar nilai | `BRANCH` |
| `FILTER(t, kondisi)` | baris yang memenuhi kondisi | aturan "status terisi" |
| `SUMMARIZECOLUMNS(col1, ..., filter, "nama", ekspresi)` | group by + agregasi | PANI, `lookup` |
| `GROUPBY(t, col, "n", COUNTX(CURRENTGROUP(), 1))` | group by atas tabel hasil variabel | `_CUBE_PART`, `breakdown` |
| `SELECTCOLUMNS(t, "nama", ekspresi)` | pilih/ganti nama kolom | hampir semua |
| `TOPN(n, t, kolom, DESC)` | n baris teratas | `breakdown`, `DETAIL_LIMIT` |
| `UNION(a, b)` | gabung baris dua tabel berkolom sama | cube PO + SO, `_meta` |
| `ROW("a", x)` | tabel satu baris | `processing_bounds` |
| `INFO.VIEW.TABLES()` / `INFO.VIEW.COLUMNS()` | metadata model | `_template`, eksplorasi `check_setup.py --dax` |

**Kenapa tidak memakai measure report?** Service principal tidak bisa membaca **rumus** measure report PANI, jadi
angkanya direkonstruksi dari tabel dan dibandingkan dengan teks measure lewat `compare_pani_with_powerbi.py`.

**Latihan** (butuh `PBI_*` terisi):
```bash
python scripts/check_setup.py --dashboard material-readiness --dax "EVALUATE TOPN(3, 'DWMaterialReadiness')"
python scripts/check_setup.py --dashboard material-readiness --dax "EVALUATE INFO.VIEW.TABLES()"
```

---

## 10. Thread, lock, rate limit, dan cache

Dev server Flask melayani beberapa request **bersamaan** di thread berbeda, dan Material Readiness memakai
`ThreadPoolExecutor` untuk menjalankan beberapa query paralel. Objek yang dipakai bersama harus aman:

| Objek | Masalah tanpa pengaman | Solusi di MANTRA |
|---|---|---|
| Klien Power BI | dibuat dua kali | singleton + `_client_lock` (`powerbi.client()`) |
| `requests.Session` | tidak dijamin thread-safe | satu Session per thread (`threading.local`) |
| Kuota query | dua thread melewati batas bersamaan | `_RateLimiter`: `deque` waktu panggilan + `Lock`, jendela 60 detik |
| Cache | 10 request bersamaan = 10 query sama | `Cache.get`: lock per key, thread lain menunggu hasil `load()` pertama (*single-flight*) |
| Throttle login & batas AI | hitungan rusak | `deque` per IP/user + `Lock` |

**Sliding window** (`_RateLimiter.wait`): buang catatan yang umurnya ≥ 60 detik; kalau sisa < batas, catat dan
lanjut; kalau tidak, tidur sampai catatan tertua kedaluwarsa.

**Batasan penting:** semua ini **di memori satu proses**. Dengan beberapa worker (gunicorn `-w 4`) setiap worker punya
cache & limiter sendiri.

---

## 11. Frontend tanpa framework

MANTRA tidak memakai React/Vue. Polanya:

1. **Server merender HTML** (Jinja) lengkap dengan sidebar, top bar, dan kerangka halaman.
2. **Data awal ditanam** di halaman: `<script>window.SUMMARY = {{ payload|tojson }};</script>`.
3. **JavaScript halaman** (mis. `summary.js`) membaca `window.SUMMARY` dan menggambar chart/slicer dengan DOM biasa.
4. **Data tambahan** diambil dengan `fetch()` ke route `/api/...` (mis. tabel Detail), memakai header `X-CSRF-Token`
   untuk POST (favorit, chat).
5. **Kontrak ke AI:** halaman menyediakan `window.DashContext()` (teks filter aktif) dan `window.DashFilters()` (dict
   filter) yang dikirim `chat.js` bersama pertanyaan.

CSS memakai **custom property** (`--sidebar-w`, `--topbar-h` di `:root` pada `shell.css`) dan **container query**
(`@container dash (...)`) di area report, supaya tata letak mengikuti lebar area konten (setelah sidebar), bukan lebar
layar.

---

## 12. LLM function calling (AI agent)

**Masalahnya.** Model bahasa pandai menulis tetapi tidak tahu data dashboard, dan bisa mengarang angka.

**Konsepnya.** Model diberi daftar **tool** (nama, deskripsi, JSON schema parameter). Model tidak menjalankan apa pun;
ia hanya menjawab "panggil `get_chart_totals` dengan `{type: "PO", month: 10}`". Kode kitalah yang menjalankan tool,
lalu mengirim hasilnya kembali. Loop ini diulang sampai model menjawab teks.

```
pesan user ──> model ──> function_call(get_chart_totals, args)
                 ▲                │
                 │        kode Python menjalankan tool (query Power BI yang sama dengan halaman)
                 └── function_response(hasil) ◄┘      ... maks 6 ronde (MAX_TOOL_ROUNDS)
model ──> teks jawaban (angka diambil dari hasil tool)
```

| Komponen | File | Peran |
|---|---|---|
| System prompt | `core/prompts/base.md` + `dashboards/<x>/prompts/*.md` | aturan menjawab, pemilihan tool, kamus data |
| Tool | `dashboards/<x>/tools.py` | fungsi Python + JSON schema |
| Guard | `core/chat/guards.py` | menormalkan parameter ("not ready" → "FP Not Ready") atau mengembalikan `valid_options` |
| Loop | `core/chat/providers.py` (`GeminiProvider.chat`) | memanggil Gemini, menjalankan `call_tool`, pindah model cadangan saat 429/503 |
| Orkestrasi | `core/chat/engine.py` | menyusun prompt, membatasi riwayat, menangkap error tool |

**Grounding** = memastikan angka di jawaban berasal dari hasil tool. Diperkuat oleh aturan prompt ("Every number must
come from a tool result"), hint saat hasil kosong, dan pertanyaan acuan (`chat_cases.py`) yang jawabannya dihitung dari
tool, bukan ditulis manual.

---

## 13. pytest: fixture dan monkeypatch

| Konsep | Di [tests/conftest.py](../../tests/conftest.py) | Fungsi |
|---|---|---|
| fixture `scope="session"` | `app` | satu app + DB sementara untuk semua test (cepat) |
| fixture `autouse=True` | `no_external_calls`, `fresh_data` | otomatis dipakai setiap test |
| `monkeypatch.setattr` | `PowerBI.request` diganti fungsi yang melempar error | test tidak pernah memanggil Power BI sungguhan |
| `app.test_client()` | class `Client` | browser palsu: GET/POST tanpa server |
| `session_transaction()` | `Client.csrf()` | menanam token CSRF ke session supaya POST lolos |
| `tempfile.mkdtemp()` | `app` fixture | `instance/mantra.db` asli tidak tersentuh |

**Kenapa `Config` diubah langsung, bukan lewat environment?** `config.py` memuat `.env` dengan `override=True`, jadi
nilai environment selalu ditimpa `.env`. Karena itu conftest menulis `setattr(Config, ...)` setelah import.

**Latihan.**
```bash
python -m pytest -k forgot -v          # hanya test yang namanya mengandung "forgot"
python -m pytest tests/test_login_and_access.py::test_ip_throttle -v
```
