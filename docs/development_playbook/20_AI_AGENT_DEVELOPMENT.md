# 20 — AI Agent Development (arsitektur & lifecycle)

AI agent MANTRA **bukan** chatbot yang sekadar meneruskan pertanyaan ke Gemini. Setiap pertanyaan melewati
otentikasi, otorisasi dashboard, rate limit, prompt berlapis, function calling terbatas (allowlist tools per
dashboard), validasi parameter oleh kode, dan query yang sama dengan halaman dashboard.

Dokumen lanjutan: alur end-to-end [29](29_AI_CHAT_FLOW_AND_TOOL_CALLING.md) · role & akses
[30](30_AI_ROLES_AND_ACCESS_CONTROL.md) · prompt & kamus data [31](31_PROMPT_ENGINEERING_AND_DATA_DICTIONARY.md) ·
test & grounding [32](32_AI_AGENT_TESTING_AND_GROUNDING.md) · menambah agent [33](33_ADD_AI_AGENT_TO_DASHBOARD.md).

## 1. Audit komponen (Verified)

| Komponen | File | Status |
|---|---|---|
| Chat UI | `static/js/chat.js`, markup di `templates/dashboard/base.html`, tombol di `components/topbar.html`, gaya di `dashboard.css` | Verified |
| Chat route | `core/chat/routes.py` (`POST /d/<slug>/api/chat`) | Verified, Tested |
| Engine | `core/chat/engine.py` (`answer`) | Verified, Tested (provider palsu) |
| Provider adapter | `core/chat/providers.py` (`GeminiProvider`) | Verified; panggilan Gemini asli NOT RUN |
| Shared prompt | `core/prompts/base.md` | Verified, Tested (static) |
| Prompt loader | `core/chat/prompt.py` | Verified, Tested (static) |
| Guards | `core/chat/guards.py` | Verified, Tested (static) |
| Dashboard prompt | `dashboards/<x>/prompts/system.md` | Verified (MR, PANI, _template) |
| Data dictionary | `dashboards/<x>/prompts/data_dictionary.md` | Verified |
| Tools | `dashboards/<x>/tools.py` (`TOOLS`, `clean_args`, `parse_dash`, `prompt_values`, `SUGGESTIONS`) | Verified |
| Query functions | `dashboards/<x>/queries.py` | Verified |
| Pertanyaan acuan | `dashboards/<x>/chat_cases.py` + `scripts/check_ai_agent.py` | Verified; run asli NOT RUN |
| Konfigurasi | `AI_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_FALLBACK_MODELS`, `CHAT_MAX_PER_MINUTE` | Verified |
| Aktivasi per dashboard | `Dashboard.chat = ChatSpec(...)` di manifest | Verified |

## 2. Tanggung jawab tiap lapisan

| Lapisan | Implementasi aktual |
|---|---|
| **Chat UI** | Panel `#chatPanel` muncul hanya jika `chat_enabled` (dashboard punya `chat` **dan** provider terkonfigurasi). Mengirim `message`, 20 riwayat terakhir, `context` (`window.DashContext()`), `filters` (`window.DashFilters()`), header `X-CSRF-Token`. Merender markdown sederhana + daftar tool yang dipakai |
| **Chat route** | 404 jika dashboard tidak ada / tanpa chat / `ready=False`; 401 belum login; 403 + audit `access_denied` jika `can_open` gagal; 429 jika > `CHAT_MAX_PER_MINUTE`/menit per user; 503 jika provider belum dikonfigurasi; 400 body/pesan kosong; potong pesan 1000 & context 500 karakter |
| **Engine** | `parse_dash(filters)` → `dash`; `prompt.render` (isi placeholder, tanggal WIB); prefix `[Active dashboard filters: ...]`; `call_tool` hanya untuk nama di `chat.tool_map`, `clean_args`, `add_hint`; error tool → dict `error`; maks 6 putaran tool |
| **Provider** | Gemini dengan `system_instruction`, `function_declarations` dari `Tool`, function calling **manual** (`automatic_function_calling.disable=True`), timeout 20 dtk, tanpa retry SDK, model cadangan pada 429/500/503/504/transport error → `AIUnavailable`; kode lain → `AIError(code)` |
| **Shared prompt** | `base.md`: hanya angka dari hasil tool, hasil kosong ≠ data tidak ada, perbaiki parameter dari `valid_options`, sampaikan `note`/`hint`, tolak mengubah aturan/membuka instruksi/di luar dashboard, format angka & tabel, baris sumber + filter |
| **Dashboard prompt + kamus** | Scope, pilihan tool, istilah, status, kolom |
| **Tools** | Fungsi Python terdaftar; **AI tidak pernah mengirim DAX** |
| **Guards** | `resolve` (cocokkan ke nilai asli data, ambigu → `ToolArgError` + `valid_options`), `resolve_week`, `add_hint` |
| **Query functions** | Sama dengan halaman → angka konsisten |
| **Validasi jawaban** | **Tidak ada** validasi otomatis atas teks jawaban akhir (`Not Found`). Grounding mengandalkan prompt + hasil tool + `chat_cases.py` (lihat dok 32) |

## 3. Urutan pembangunan agent (dan dependency)

| # | Tahap | Bergantung pada | Selesai jika |
|---|---|---|---|
| 1 | Kebutuhan & batas tugas | — | Daftar pertanyaan didukung & ditolak |
| 2 | Audit UI/route/engine/provider/prompt/tools/queries | dok ini | Tidak ada gap |
| 3 | Dashboard & semantic model sumber | dok 15 | `check_setup.py` OK |
| 4 | Role & akses | dok 12, 30 | Sama dengan akses dashboard |
| 5 | Pertanyaan didukung / di luar scope | 1 | Tertulis di `system.md` |
| 6 | Data dictionary & KPI | 3 | `data_dictionary.md` |
| 7 | Prompt global & dashboard | 5, 6 | `prompt.load` lulus |
| 8 | Tools: parameter (JSON schema) & output | 6 | `TOOLS` |
| 9 | Guards (`clean_args`) | 8 | Nilai di-resolve ke data asli |
| 10 | Engine ↔ provider | konfigurasi | Sudah tersedia (core) |
| 11 | Tools ↔ queries tervalidasi | dok 15 | Tool memakai fungsi halaman |
| 12 | Validasi hasil & jawaban | 11 | `add_hint`, pesan error tool |
| 13 | Backend ↔ frontend | `chat.js` | `DashContext`/`DashFilters` diisi |
| 14 | Error, timeout, limit | core | Sudah tersedia |
| 15 | Dataset uji | 5 | `chat_cases.py` |
| 16 | Unit test (provider palsu) | 13 | pytest |
| 17 | Integration test | kuota | `check_ai_agent.py --dashboard` |
| 18 | Quality & regression | 17 | Semua kasus lulus (ulang kasus yang flaky) |
| 19 | End-to-end UI | 13 | Jawaban tampil di panel |
| 20 | Dokumentasi | semua | Dok 31-33 diperbarui |

## 4. Mengganti provider (Verified dari docstring & kode)

1. Tambah class di `providers.py` dengan method `chat(system, history, message, tools, call_tool, max_rounds)` →
   `(text, model)`; lempar `AIUnavailable` / `AIError(code)` untuk error.
2. Daftarkan: `PROVIDERS["nama"] = (Class, lambda: bool(Config.API_KEY_BARU))`.
3. Tambah variabel di `config.py` + `.env.example`; set `AI_PROVIDER=nama`.
4. Dashboard & tools tidak berubah. Jalankan `python -m pytest` (test memakai provider palsu) dan uji manual.
Catatan: `google-genai` tetap di-import saat start (import tingkat modul di `providers.py`).
