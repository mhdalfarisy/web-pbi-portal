# 33 — Menambah AI Agent ke Dashboard

### A. Objective
Dashboard (baru atau existing) mendapat AI agent yang menjawab dari data dashboard itu saja, dengan tools
tervalidasi dan test acuan.

### B. When to use
Setelah halaman dashboard benar ([16](16_DASHBOARD_PAGE_DEVELOPMENT.md)/[17](17_NEW_DASHBOARD_DEVELOPMENT.md)) **dan**
ada kebutuhan tanya-jawab. Jangan membuat agent hanya karena dashboard baru dibuat; tanpa `chat=` di manifest,
tidak ada agent.

### C. Prerequisites
`queries.py` sudah tervalidasi terhadap report; `GEMINI_API_KEY` untuk uji asli.

### D. Architecture context
Mesin agent di `core/chat/` generik; dashboard hanya menyediakan `ChatSpec` (tools + prompt + hook). Lihat
[20](20_AI_AGENT_DEVELOPMENT.md), [29](29_AI_CHAT_FLOW_AND_TOOL_CALLING.md).

### E. Files involved
| File | Isi |
|---|---|
| `dashboards/<x>/tools.py` | `TOOLS`, `clean_args`, `parse_dash`, `prompt_values` (opsional), `SUGGESTIONS` |
| `dashboards/<x>/prompts/system.md` | Scope + penjelasan setiap tool |
| `dashboards/<x>/prompts/data_dictionary.md` | Kamus data |
| `dashboards/<x>/chat_cases.py` | Pertanyaan acuan (`CASES`) |
| `dashboards/<x>/__init__.py` | `chat=ChatSpec(...)` |
| `static/*.js` dashboard | `window.DashContext`, `window.DashFilters` |

### F. Step-by-step instructions
1. **Tujuan & scope**: tulis 5-10 pertanyaan bisnis yang didukung dan 2-3 yang harus ditolak.
2. **Akses**: tidak ada pekerjaan tambahan; chat otomatis mengikuti akses dashboard (dok 30). Pastikan tool tidak
   membaca data di luar yang boleh dilihat pengguna dashboard (perhatikan pola `lookup` MR).
3. **Kamus data** (`data_dictionary.md`) dari model & `queries.py`.
4. **Tools minimum**: satu tool per kebutuhan; **panggil fungsi `queries.py` yang sama dengan halaman**. Batasi
   output (jumlah baris), kembalikan `total`/`total_rows`/`groups` agar `add_hint` bekerja, dan tambahkan `note`
   jika ada keterbatasan.
5. **Parameter**: JSON schema dengan `enum` untuk nilai tetap; normalkan nilai bebas di `clean_args` memakai
   `guards.resolve` (lempar `ToolArgError` dengan pilihan valid).
6. **`parse_dash`**: ubah `filters` dari browser menjadi dict yang dipakai tool sebagai default (validasi tipe &
   panjang).
7. **Prompt** (`system.md`): sebut setiap tool dengan backtick; kapan memakai masing-masing.
8. **Manifest**: tambah `chat=ChatSpec(...)`.
9. **Frontend**: definisikan `window.DashContext()` (teks filter aktif) dan `window.DashFilters()` (dict) di JS halaman.
10. **Test**: `chat_cases.py` (jawaban acuan dihitung dari queries saat tes); `check_ai_agent.py --static`.
11. **Restart**, uji di panel, lalu `check_ai_agent.py --dashboard <slug>`.
12. **Regresi**: `--static` untuk semua dashboard; `python -m pytest`.
13. **Dokumentasi**: dok 01 (tabel tools), dok 32 (dataset uji).

### G. Code or patch (`Proposed`, mengikuti pola `material_readiness/tools.py` & `_template/tools.py`)
```python
# dashboards/<x>/tools.py
from ...core.chat.guards import ToolArgError, resolve
from ...core.registry import Tool
from . import queries

STATUSES = ("open", "closed")

def tool_summary(args, dash):
    year = args.get("year") or dash.get("year")
    rows, _ = queries.summary(year)                        # fungsi yang sama dengan halaman
    return {"total": sum(r["count"] for r in rows), "rows": rows[:30],
            "note": "Maksimal 30 baris ditampilkan."}

TOOLS = [
    Tool("get_summary", "Summary", "Jumlah work order per status untuk satu tahun.",
         {"type": "object",
          "properties": {"year": {"type": "integer", "description": "Tahun, mis. 2026"},
                         "status": {"type": "string", "enum": list(STATUSES)}},
          "required": []},
         tool_summary),
]

def clean_args(args):
    args = dict(args)
    if args.get("status"):
        args["status"] = resolve("status", args["status"], STATUSES, prefixes=())
    return args

def parse_dash(raw):
    raw = raw if isinstance(raw, dict) else {}
    year = raw.get("year")
    return {"year": int(year) if str(year).isdigit() else None}

SUGGESTIONS = ["How many work orders are open this year?"]
```
```python
# dashboards/<x>/__init__.py
chat=ChatSpec(tools=tools.TOOLS, prompt_dir=Path(__file__).resolve().parent / "prompts",
              suggestions=tools.SUGGESTIONS, clean_args=tools.clean_args, parse_dash=tools.parse_dash),
```
```markdown
<!-- prompts/system.md -->
## Tools
- `get_summary`: jumlah work order per status; pakai untuk pertanyaan total/per status.
```
```js
// static/<x>.js
window.DashContext = function () { return 'Year ' + state.year; };
window.DashFilters = function () { return { year: state.year }; };
```

### H. Code explanation
`resolve` mengembalikan nilai asli data atau `ToolArgError` → engine mengirim `valid_options` ke model. Nama tool
diawali `get_` supaya salah ketik nama tool di prompt terdeteksi saat start (dok 28 issue 11).

### I. Commands
```powershell
python scripts\check_ai_agent.py --static
python -m pytest
python scripts\check_ai_agent.py --dashboard <slug>
```

### J. Expected result
`SEMUA LULUS`; tombol Ask AI muncul di dashboard; jawaban menyebut sumber & filter.

### K. Validation
Pertanyaan normal, di luar scope, ambigu, parameter salah, dan "abaikan aturan" (dok 32 §1).

### L. Troubleshooting
Pesan saat start: dok 31 §L. Tombol tidak muncul: `chat` belum di manifest atau `GEMINI_API_KEY` kosong.
`/api/chat` 404: dashboard `ready=False` atau tanpa `chat`.

### M. Regression impact
`base.md`/`core/chat/*` tidak diubah → dashboard lain tidak terdampak; tetap jalankan `--static` semua.

### N. Acceptance criteria (checklist)
- [ ] Tujuan & scope agent terdokumentasi (`system.md`)
- [ ] Kamus data diverifikasi terhadap model & `queries.py`
- [ ] Prompt global dan dashboard diperiksa (`--static`)
- [ ] Tools terdaftar, memakai queries halaman, output dibatasi
- [ ] Parameter divalidasi (`clean_args`/`resolve`)
- [ ] Authorization tetap di backend (tidak ada perubahan pada `chat()` / `_guard`)
- [ ] Error handling (hasil kosong, error tool) diuji
- [ ] `chat_cases.py` dibuat; hasil dicatat (dok 32)
- [ ] Grounding diperiksa (angka jawaban = hasil tool)
- [ ] Kegagalan provider dipahami (503/502)
- [ ] Regresi dashboard lain dijalankan
- [ ] Dokumentasi diperbarui

### O. Documentation updates
Dok 01, 30 (matriks peran ↔ tools), 32.

### P. Actual status
Contoh kode: `Proposed`, NOT RUN. Pola yang diikuti: Verified dari `material_readiness/tools.py`, `pani_processing/tools.py`, `_template/tools.py`.
