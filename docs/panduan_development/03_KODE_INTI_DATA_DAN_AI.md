# Pendalaman 3 — Kode Inti Data & AI Agent (Fase 7-12)

> Bagian dari [Panduan Development Berurutan](../PANDUAN_DEVELOPMENT_BERURUTAN.md). Potongan kode disalin dari
> repository (28 Okt 2026); baris yang tidak relevan diganti `...`. Konsep: [Pendalaman 1](01_KONSEP_TEKNOLOGI.md)
> §9-12. Logika angka per dashboard: [Pendalaman 4](04_LOGIKA_BISNIS_DASHBOARD.md).

## Daftar isi

1. [`powerbi.py` — satu pintu ke Power BI](#1-powerbipy--satu-pintu-ke-power-bi) (Fase 7)
2. [`cache.py` — cache single-flight](#2-cachepy--cache-single-flight) (Fase 7)
3. [`errors.py` — pesan umum + kode ref](#3-errorspy--pesan-umum--kode-ref) (Fase 7)
4. [Pola satu dashboard: queries → routes → template → JS](#4-pola-satu-dashboard-queries--routes--template--js) (Fase 9-10)
5. [`guards.py` — menormalkan parameter dari AI](#5-guardspy--menormalkan-parameter-dari-ai) (Fase 11)
6. [`prompt.py` — memuat & memvalidasi prompt](#6-promptpy--memuat--memvalidasi-prompt) (Fase 9/11)
7. [`providers.py` — loop function calling Gemini](#7-providerspy--loop-function-calling-gemini) (Fase 11)
8. [`engine.py` — menjalankan tool dengan aman](#8-enginepy--menjalankan-tool-dengan-aman) (Fase 11)
9. [`chat/routes.py` + `chat.js` — endpoint & UI](#9-chatroutespy--chatjs--endpoint--ui) (Fase 11)
10. [`tools.py` — contoh tool nyata](#10-toolspy--contoh-tool-nyata) (Fase 11-12)

---

## 1. `powerbi.py` — satu pintu ke Power BI

File: [mantra/core/powerbi.py](../../mantra/core/powerbi.py)

```python
@dataclass(frozen=True)
class Dataset:
    env_prefix: str
    workspace_id: str
    dataset_id: str

    @property
    def ids(self):
        return (os.environ.get(f"{self.env_prefix}_WORKSPACE_ID") or self.workspace_id,
                os.environ.get(f"{self.env_prefix}_DATASET_ID") or self.dataset_id)

    @property
    def path(self):
        workspace_id, dataset_id = self.ids
        return f"/groups/{workspace_id}/datasets/{dataset_id}"
```
- Setiap dashboard punya satu `Dataset` di `queries.py`. ID default ada di kode (bukan secret), tetapi bisa ditimpa
  `.env`, mis. `MATERIAL_READINESS_DATASET_ID=` untuk dataset dev.
- `frozen=True`: tidak bisa diubah setelah dibuat (aman dibagi antar thread).

```python
class _RateLimiter:
    def __init__(self, per_minute):
        self.per_minute = per_minute
        self.calls = deque()
        self.lock = threading.Lock()

    def wait(self):
        while True:
            with self.lock:
                now = time.monotonic()
                while self.calls and now - self.calls[0] >= 60:
                    self.calls.popleft()
                if len(self.calls) < self.per_minute:
                    self.calls.append(now)
                    return
                delay = 60 - (now - self.calls[0])
            time.sleep(min(max(delay, 0.05), 5))
```
- `time.monotonic()` (bukan `time.time()`): tidak terpengaruh jam sistem yang berubah.
- `sleep` **di luar** `with self.lock`: kalau tidur sambil memegang lock, semua thread lain ikut macet.
- `min(..., 5)`: tidur maksimal 5 detik lalu cek ulang (thread lain bisa saja sudah melepas slot).

```python
    def execute_query(self, dataset, dax):
        self._limiter.wait()
        body = {"queries": [{"query": dax}], "serializerSettings": {"includeNulls": True}}
        data = self.request("POST", f"{dataset.path}/executeQueries", json=body)
        try:
            result = data["results"][0]
        except (KeyError, IndexError, TypeError):
            raise PowerBIError("Respons executeQueries tidak dikenal (tidak ada results)") from None
        if "error" in result:
            raise PowerBIError(f"DAX error: {result['error']}")
        rows = ((result.get("tables") or [{}])[0] or {}).get("rows") or []
        if not rows:
            return []
        keys = list(rows[0])
        cleaned = [_clean_column(k) for k in keys]
        names = dict(zip(keys, cleaned if len(set(cleaned)) == len(cleaned) else keys))
        return [{names.get(k, k): v for k, v in row.items()} for row in rows]
```
- `includeNulls: True`: kolom bernilai kosong tetap muncul sebagai `None`. Tanpa ini, baris pertama bisa kekurangan
  kunci dan `rows[0]` tidak mewakili semua kolom.
- `_clean_column`: `'DWMaterialReadiness'[Plant_No]` → `Plant_No`. Kalau dua kolom dari tabel berbeda menghasilkan nama
  pendek yang sama, nama asli dipakai (`len(set(cleaned)) == len(cleaned)`).
- Error DAX (salah ketik kolom) datang sebagai HTTP 200 dengan `result["error"]`, karena itu dicek terpisah dari HTTP.

```python
def query(dataset, dax):
    return client().execute_query(dataset, dax)
```
Satu-satunya fungsi yang dipanggil dashboard. `client()` membuat objek `PowerBI` sekali (lock) dan gagal dengan
`PowerBIError("Belum diisi di .env: ...")` kalau kredensial kosong; pesan itulah yang terlihat di log output nyata Fase 10.

---

## 2. `cache.py` — cache single-flight

File: [mantra/core/cache.py](../../mantra/core/cache.py)

```python
    def get(self, key, load):
        with self.lock:
            hit = self._fresh(key)
            if hit:
                return hit
            key_lock = self.loading.setdefault(key, threading.Lock())
        with key_lock:
            with self.lock:
                hit = self._fresh(key)  # sudah dimuat thread lain selagi menunggu
                if hit:
                    return hit
            try:
                value = (load(), time.time())
            except BaseException:
                with self.lock:
                    self.loading.pop(key, None)
                raise
            with self.lock:
                self.items[key] = value
                self.loading.pop(key, None)
                if len(self.items) > self.size:
                    for old in sorted(self.items, key=lambda k: self.items[k][1])[: len(self.items) - self.size]:
                        del self.items[old]
            return value
```
Skenario 3 user membuka Summary bersamaan saat cache kosong:

| Waktu | Thread A | Thread B, C |
|---|---|---|
| t0 | cache kosong → ambil `key_lock` → jalankan `load()` (query Power BI) | cache kosong → menunggu `key_lock` |
| t1 | simpan hasil, lepas lock | dapat lock → **cek ulang** → hit → kembalikan hasil A |

Hasilnya satu query, bukan tiga. Nilai kembali selalu `(data, waktu_ambil)`; waktu itulah yang tampil di kotak
"Last Update" (`stamp_info(fetched)`). Error **tidak** disimpan, jadi request berikutnya mencoba lagi.

---

## 3. `errors.py` — pesan umum + kode ref

File: [mantra/core/errors.py](../../mantra/core/errors.py)

```python
def log_data_error(exc):
    ref = secrets.token_hex(4).upper()
    current_app.logger.error("Power BI request failed [ref %s]: %s", ref, exc, exc_info=exc)
    return ref


def data_error_json(exc):
    ref = log_data_error(exc)
    return jsonify(error=f"{PUBLIC_MESSAGE} (ref {ref})", ref=ref), 502
```
Pesan `PowerBIError` berisi path API (ID workspace/dataset) dan potongan respons Power BI. User hanya melihat pesan umum
+ ref; developer mencari ref yang sama di log. HTTP 502 = "server di belakang kita (Power BI) gagal", bukan bug portal.

---

## 4. Pola satu dashboard: queries → routes → template → JS

Contoh: halaman Summary Material Readiness.

**(a) Query** — [material_readiness/queries.py](../../mantra/dashboards/material_readiness/queries.py)
```python
DATASET = Dataset("MATERIAL_READINESS", workspace_id="076fb2d0-...", dataset_id="6dfa0b74-...")
_cache = Cache(Config.CACHE_SECONDS)

def _query(dax):
    return query(DATASET, dax)

def summary_cube():
    def load():
        po = _CUBE_PART.format(T=T, C=C, t=0, desc=STATUS_DESC["PO"], legend=LEGEND["PO"])
        so = _CUBE_PART.format(T=T, C=C, t=1, desc=STATUS_DESC["SO"], legend=LEGEND["SO"])
        rows = _query(f"DEFINE VAR _base = CALCULATETABLE({T}, {BRANCH})\nEVALUATE UNION({po}, {so})")
        return [[int(r["t"]), r["s"], r["w"], int(r["y"]), int(r["m"]), int(r["q"] or 0), int(r["j"] or 0), r["c"] or ""]
                for r in rows]
    return _cache.get("cube", load)
```
Pola tetap setiap fungsi query: fungsi dalam `load()` berisi DAX, dibungkus `_cache.get(key, load)`, mengembalikan
`(data, waktu)`. Hasil dibentuk menjadi list pendek (bukan dict) supaya payload ke browser kecil. Isi DAX-nya dijelaskan
di [Pendalaman 4 §1](04_LOGIKA_BISNIS_DASHBOARD.md#1-material-readiness).

**(b) Route** — [material_readiness/routes.py](../../mantra/dashboards/material_readiness/routes.py)
```python
@bp.get("/")
def summary():
    try:
        cube, fetched = queries.summary_cube()
        logo = queries.company_logos()
    except queries.DATA_ERRORS as exc:
        return data_error_page(exc)
    now = queries.now_wib()
    payload = {"data": cube, "logo": logo, "curY": now.year, "curM": now.month,
               "detailUrl": url_for("material_readiness.detail")}
    return render_template("material_readiness/summary.html", payload=payload, header=queries.stamp_info(fetched))
```
Tidak ada `@login_required`: login & hak akses sudah dijaga `_guard` di blueprint. Route hanya mengambil data, menangkap
`DATA_ERRORS`, dan menyerahkan `payload` + `header` (Last Update) ke template. URL dibuat dengan `url_for`, bukan ditulis.

**(c) Template** — [summary.html](../../mantra/dashboards/material_readiness/templates/material_readiness/summary.html)
```html+jinja
{% extends "dashboard/base.html" %}
{% block content %}  ... slicer + 4 kartu chart (div kosong ber-id) ...  {% endblock %}
{% block scripts %}
<script>window.SUMMARY = {{ payload|tojson }};</script>
<script src="{{ url_for('material_readiness.static', filename='summary.js') }}"></script>
{% endblock %}
```

**(d) JavaScript** — [summary.js](../../mantra/dashboards/material_readiness/static/summary.js)
```javascript
var P = window.SUMMARY;
/* DATA : [tipe 0=PO 1=SO, status, week category, tahun Start_Date, bulan Start_Date, count QTY_Order, count Job_Code, company] */
var DATA = P.data;
...
window.DashFilters = function () {
    return {
        year: THIS_MONTH ? CUR_Y : (YSEL === 'ALL' ? null : +YSEL),
        month: THIS_MONTH ? CUR_M : (MSEL === 'ALL' ? null : +MSEL),
        company: COSEL === 'ALL' ? null : COSEL,
    };
};
```
Slicer (company, tahun, bulan, This Month) memfilter `DATA` **di browser**, tanpa query baru. Halaman Detail memakai
pola kedua: `fetch(payload.api + "?type=PO&year=...")` ke `/api/detail`, karena datanya terlalu besar untuk ditanam.

**Kontrak antar lapisan** (kalau satu diubah, yang lain ikut):

| Dari → ke | Kontrak | Contoh |
|---|---|---|
| `queries.py` → `routes.py` | fungsi mengembalikan `(data, fetched)`; error = `DATA_ERRORS` | `summary_cube()` |
| `routes.py` → template | nama variabel `payload`, `header` | `render_template(..., payload=..., header=...)` |
| template → JS | `window.SUMMARY` / `window.DETAIL` | urutan index list cube `[t, s, w, y, m, q, j, c]` |
| JS → AI agent | `window.DashContext()` (teks), `window.DashFilters()` (dict) | diterima `tools.parse_dash` |

---

## 5. `guards.py` — menormalkan parameter dari AI

File: [mantra/core/chat/guards.py](../../mantra/core/chat/guards.py)

```python
def resolve(name, value, options, prefixes=("fp", "all")):
    key = norm(value)
    exact = {norm(o): o for o in options}
    if key in exact:
        return exact[key]
    if prefixes:
        pattern = re.compile(rf"^({'|'.join(prefixes)})(?=.)")
        core = {pattern.sub("", k): o for k, o in exact.items()}  # "FP Not Ready" -> "notready"
        if key in core:
            return core[key]
    hits = [o for k, o in exact.items() if key and key in k]
    if len(hits) == 1:
        return hits[0]
    raise ToolArgError(name, value, sorted(options))
```
AI sering menulis "not ready", padahal nilai di data "FP Not Ready". Tiga tahap pencocokan:
1. `norm()` membuang semua selain huruf/angka dan huruf kecil: `"In Progress"` = `"inprogress"`.
2. Abaikan awalan `fp`/`all`: `"notready"` cocok dengan `"fpnotready"`.
3. Satu-satunya opsi yang **mengandung** teks itu: `"merdeka mining"` → `"PT Merdeka Mining Indonesia"`.

Ambigu atau tidak ketemu → `ToolArgError` yang berubah menjadi `{"error": ..., "valid_options": [...]}` untuk AI.
Aturan prompt no. 4 menyuruh AI memperbaiki parameter dari daftar itu. Output nyata `check_ai_agent.py --static`
(Checkpoint Fase 11) menguji persis kasus-kasus ini.

---

## 6. `prompt.py` — memuat & memvalidasi prompt

File: [mantra/core/chat/prompt.py](../../mantra/core/chat/prompt.py)

```python
def load(dashboard):
    chat = dashboard.chat
    files = sorted(Path(chat.prompt_dir).glob("*.md"), key=lambda p: (p.name != "system.md", p.name))
    if not files:
        raise RuntimeError(f"Folder prompt {chat.prompt_dir} kosong")
    text = "\n\n".join([_read(BASE_PROMPT)] + [_read(p) for p in files])

    allowed = set(CORE_PLACEHOLDERS) | set(chat.placeholders)
    unknown = set(PLACEHOLDER_RE.findall(text)) - allowed
    if unknown:
        raise RuntimeError(...)
    tools = set(chat.tool_map)
    named = set(re.findall(r"`(get_\w+|lookup\w*)`", text))
    if named - tools:
        raise RuntimeError(f"[{dashboard.slug}] tool tidak dikenal di prompt: ...")
    missing = {t for t in tools if f"`{t}`" not in text}
    if missing:
        raise RuntimeError(f"[{dashboard.slug}] tool belum dijelaskan di prompt: ...")
    chat.template = text
```
- Urutan prompt: `base.md` → `system.md` → file lain abjad (`data_dictionary.md`). Kunci sort `(p.name != "system.md",
  p.name)` menaruh `system.md` paling depan karena `False < True`.
- `_read` membuang `<!-- komentar -->`: catatan developer tidak terkirim ke AI.
- Tiga validasi **saat start**: placeholder `{{...}}` harus dikenal; nama tool di backtick harus ada; setiap tool harus
  disebut. Salah ketik nama tool di prompt langsung menggagalkan start, bukan membuat AI memanggil tool fiktif.
- Pola regex `get_\w+|lookup\w*` berarti **nama tool baru sebaiknya diawali `get_` atau `lookup`**, supaya ikut
  divalidasi.

`render()` mengganti placeholder **per pertanyaan** (`{{today}}` selalu tanggal hari ini, `{{companies}}` dari
`prompt_values()` dashboard).

---

## 7. `providers.py` — loop function calling Gemini

File: [mantra/core/chat/providers.py](../../mantra/core/chat/providers.py)

```python
    def chat(self, system, history, message, tools, call_tool, max_rounds):
        contents = [types.Content(role="model" if h["role"] == "model" else "user", parts=[types.Part(text=h["text"])])
                    for h in history]
        contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(name=t.name, description=t.description, parameters_json_schema=t.parameters)
                for t in tools])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        models = list(self.models)
        for _ in range(max_rounds):
            response, model = self._generate(contents, config, models)
            models = [model] + [m for m in models if m != model]
            calls = response.function_calls or []
            if not calls:
                return (response.text or "Sorry, I could not get an answer.").strip(), model
            contents.append(response.candidates[0].content)
            parts = [types.Part.from_function_response(name=c.name, response={"result": call_tool(c.name, dict(c.args or {}))})
                     for c in calls]
            contents.append(types.Content(role="user", parts=parts))
        return "Sorry, this question needs too many steps. Please make it more specific.", models[0]
```
| Baris | Arti |
|---|---|
| `contents` | riwayat percakapan + pertanyaan baru, dalam format Gemini |
| `FunctionDeclaration(... parameters_json_schema=t.parameters)` | `Tool` dari registry → deklarasi tool Gemini; schema yang sama dipakai AI untuk mengisi argumen |
| `automatic_function_calling(disable=True)` | SDK **tidak** boleh menjalankan fungsi sendiri; MANTRA yang menjalankan lewat `call_tool` (supaya ada guard, log, batas) |
| `models = [model] + ...` | setelah satu model berhasil, ronde berikutnya tetap di model itu |
| `contents.append(response.candidates[0].content)` | jawaban model (berisi function_call) wajib masuk riwayat sebelum hasil tool |
| `from_function_response(...)` | hasil tool dikirim balik ke model; satu pertanyaan bisa memanggil beberapa tool sekaligus |
| `for _ in range(max_rounds)` | batas 6 ronde: mencegah loop tak berujung yang menghabiskan kuota |

`_generate` mencoba `GEMINI_MODEL` lalu `GEMINI_FALLBACK_MODELS` saat error 429/500/503/504 atau timeout, dan melempar
`AIUnavailable` kalau semua gagal. Mengganti provider = membuat class baru dengan method `chat(...)` yang sama, lalu
mendaftarkannya di `PROVIDERS`.

---

## 8. `engine.py` — menjalankan tool dengan aman

File: [mantra/core/chat/engine.py](../../mantra/core/chat/engine.py)

```python
    def call_tool(name, args):
        tool = tool_map.get(name)
        if tool is None:
            return {"error": f"Unknown tool {name}"}
        try:
            if chat.clean_args:
                args = chat.clean_args(args)
            result = add_hint(tool.fn(args, dash))
        except ToolArgError as exc:
            result = exc.result()
        except DATA_ERRORS as exc:
            result = {"error": f"Power BI data is temporarily unavailable (ref {log_data_error(exc)}). "
                               "Tell the user and do not guess any numbers."}
        except Exception:
            current_app.logger.exception("Tool %s gagal (args %s)", name, args)
            result = {"error": "This tool failed to run. Tell the user the data could not be retrieved; "
                               "do not guess any numbers."}
        used.append({"name": name, "label": tool.label, "args": args})
        return result
```
Setiap kegagalan diubah menjadi **dict untuk AI**, bukan exception yang memutus percakapan. Pesan error sengaja berisi
instruksi "do not guess any numbers". `used` dikembalikan ke browser sebagai "Data used (n queries)".

```python
    system = prompt.render(dashboard, datetime.now(WIB))
    prefix = f"[Active dashboard filters: {context}]\n" if context else ""
    text, model = provider.chat(system, _clean_history(history), prefix + message, chat.tools, call_tool,
                                MAX_TOOL_ROUNDS)
```
`context` (teks dari `DashContext()`) ditempel di depan pertanyaan, jadi AI tahu filter yang sedang dilihat user.
`dash` (dict dari `parse_dash(filters)`) diberikan ke tool, sehingga tool bisa memakai periode dashboard sebagai default.
`_clean_history` memotong riwayat ke 20 pesan × 4.000 karakter (riwayat datang dari browser, jadi tidak dipercaya).

---

## 9. `chat/routes.py` + `chat.js` — endpoint & UI

File: [mantra/core/chat/routes.py](../../mantra/core/chat/routes.py)

Urutan pemeriksaan di `POST /d/<slug>/api/chat` (setiap baris punya kode HTTP sendiri):

| No | Cek | Gagal |
|---|---|---|
| 1 | dashboard ada, punya chat, ready | 404 |
| 2 | sudah login | 401 |
| 3 | boleh membuka dashboard ini (+ audit) | 403 |
| 4 | belum melewati `CHAT_MAX_PER_MINUTE` | 429 |
| 5 | provider AI terkonfigurasi | 503 |
| 6 | body JSON valid, `message` tidak kosong (dipotong 1.000 karakter) | 400 |
| 7 | `engine.answer(...)` | 503 (`AIUnavailable`), 502 (`AIError`, Power BI) |

Route chat **tidak** berada di blueprint dashboard (satu blueprint `chat` untuk semua slug), jadi `_guard` tidak
berlaku; karena itu cek 2 & 3 ditulis ulang di sini. CSRF tetap dari `csrf_protect` global.

File: [mantra/static/js/chat.js](../../mantra/static/js/chat.js)
```javascript
        const r = await fetch(CFG.url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': CSRF },
            body: JSON.stringify({
                message: text,
                history: HISTORY.slice(-20),
                context: window.DashContext ? window.DashContext() : '',
                filters: window.DashFilters ? window.DashFilters() : null,
            }),
        });
```
`CFG.url` dan contoh pertanyaan datang dari `window.CHAT` di `dashboard/base.html` (`url_for("chat.chat", slug=...)`).
Jawaban dirender oleh `markdown()` sederhana **setelah** `esc()` (HTML dari AI tidak pernah dieksekusi).

---

## 10. `tools.py` — contoh tool nyata

File: [material_readiness/tools.py](../../mantra/dashboards/material_readiness/tools.py)

```python
    Tool("get_chart_totals", "Totals (chart logic)",
         "Total per status dengan logika yang SAMA PERSIS dengan chart di halaman Summary (hanya baris yang status dan "
         "week-nya terisi). Juga mengembalikan pembagian per bulan Start Date, berguna kalau satu week melintasi dua "
         "bulan. Pakai ini untuk semua pertanyaan total/jumlah.",
         {"type": "object", "properties": CHART_PROPS, "required": []},
         tool_chart),
```
Lima bagian `Tool`: `name` (dipanggil AI, wajib disebut di prompt), `label` (tampil di "Data used"), `description`
(dibaca AI untuk memilih tool), `parameters` (JSON schema; `enum` membatasi nilai), `fn(args, dash)`.

```python
def tool_chart(args, dash):
    t = 1 if (args.get("type") or "PO").upper() == "SO" else 0
    idx = 6 if args.get("measure") == "work_order" else 5
    ...
    applied_dashboard_period = False
    if not args.get("all_months") and month is None and dash.get("month") is not None:
        if week or year is None:
            year, month = dash.get("year"), dash["month"]
            applied_dashboard_period = True
    ...
    cube, _ = queries.summary_cube()
```
Prinsip penting: tool **memakai fungsi query yang sama dengan halaman** (`summary_cube()`), jadi angka AI = angka chart,
dan hasilnya ikut cache. Kalau user tidak menyebut bulan, periode diambil dari filter dashboard (`dash`) dan hasil
diberi `note` supaya AI menyebutkannya.

```python
def clean_args(args):
    args = dict(args)
    ...
    if args.get("status"):
        args["status"] = resolve("status", args["status"], {r[1] for r in cube if r[0] == t})
    if args.get("company"):
        company = queries.company_names().get(company.upper(), company)  # kode company, mis. MMI
        args["company"] = resolve("company", company, set(queries.company_logos()) | {queries.NO_COMPANY})
```
`clean_args` dijalankan engine **sebelum** setiap tool: opsi valid diambil dari data asli (bukan daftar tetap di kode),
lalu `guards.resolve` menormalkan nilai dari AI.

**Pertanyaan acuan** ([chat_cases.py](../../mantra/dashboards/material_readiness/chat_cases.py)) menghitung jawaban
benar dari tool yang sama saat tes, lalu memeriksa apakah jawaban AI memuat angka itu dan memakai tool yang benar.
Dijalankan dengan `python scripts/check_ai_agent.py --dashboard material-readiness`.
