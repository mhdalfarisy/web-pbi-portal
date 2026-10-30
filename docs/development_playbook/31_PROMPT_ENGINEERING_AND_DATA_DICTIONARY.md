# 31 — Prompt Engineering & Data Dictionary

### A. Objective
Menulis/mengubah prompt agent dan kamus data yang akurat terhadap semantic model, tanpa membuat aplikasi gagal start.

### B. When to use
Agent salah memilih tool, salah istilah, menjawab di luar scope, atau ada kolom/KPI baru.

### C. Prerequisites
Paham tools dashboard (`tools.py`) dan model (`check_setup.py --dax "EVALUATE INFO.VIEW.COLUMNS()"`).

### D. Architecture context
`prompt.load` (saat start) menggabungkan `core/prompts/base.md` + `prompts/system.md` + `prompts/*.md` lain (urut
nama), menghapus komentar `<!-- ... -->`, lalu memvalidasi:
- placeholder `{{nama}}` harus ada di `CORE_PLACEHOLDERS` (`today`, `year`, `month`, `month_name`,
  `dashboard_title`) atau `ChatSpec.placeholders`;
- setiap tool di `TOOLS` **wajib** disebut dalam backtick (`` `get_x` ``);
- nama berpola `` `get_*` `` / `` `lookup*` `` yang bukan tool → error.
`prompt.render` (setiap pertanyaan) mengisi placeholder; `prompt_values()` yang gagal karena Power BI → nilai `-`.

### E. Files involved
`mantra/core/prompts/base.md`, `mantra/dashboards/<x>/prompts/system.md`, `data_dictionary.md`, `tools.py`
(`placeholders`, `prompt_values` di manifest), `chat_cases.py`.

### F. Step-by-step instructions
1. Tentukan level aturan: berlaku semua dashboard → `base.md`; khusus dashboard → `system.md`; definisi data →
   `data_dictionary.md`. Jangan menaruh definisi bisnis satu dashboard di `base.md`.
2. Tulis catatan untuk developer di komentar HTML (tidak dikirim ke AI).
3. Sebut setiap tool dengan backtick dan jelaskan kapan dipakai.
4. `python scripts/check_ai_agent.py --static` → `SEMUA LULUS`.
5. **Restart Flask** (prompt dibaca sekali saat start).
6. `python scripts/check_ai_agent.py --dashboard <slug>` (kuota) — ulang kasus yang gagal sekali sebelum mengubah
   prompt lagi (jawaban AI bisa bervariasi).

### G. Code or patch — kerangka `system.md` (pola `_template`, Verified)
```markdown
<!-- catatan developer: tidak dikirim ke AI -->
# {{dashboard_title}} agent

## Scope
- Pertanyaan yang didukung: ...
- Di luar scope (tolak dengan sopan): ...

## Tools
- `get_x`: kapan dipakai, parameter penting, apa yang dikembalikan.

## Aturan khusus
- Istilah/status yang harus dipakai persis: ...
- Jika ... maka tanyakan klarifikasi: ...
```

Isi `data_dictionary.md` (checklist):

| Bagian | Isi |
|---|---|
| KPI | Nama, definisi bisnis, rumus/aturan agregasi (sesuai `queries.py`, bukan asumsi), satuan |
| Tabel & kolom relevan | Nama di model, tipe, arti |
| Periode | Definisi (mis. MTD/YTD, tanggal data terakhir, zona WIB) |
| Filter | Nilai yang valid, default halaman |
| Istilah & sinonim | Pemetaan bahasa user → nilai data (membantu `resolve`) |
| Batasan | Data yang **tidak** bisa dibaca agent / tidak boleh dipakai untuk kesimpulan tertentu |

### H. Code explanation
Validasi saat start memaksa prompt dan tools selalu sinkron; error muncul sebelum user mencoba agent.

### I. Commands
```bash
python scripts/check_ai_agent.py --static
python scripts/check_ai_agent.py --dashboard material-readiness
python scripts/check_ai_agent.py --dashboard pani-processing gold     # hanya kasus yang namanya mengandung "gold"
```

### J. Expected result
`SEMUA LULUS` (static: Tested 26 Okt 2026).

### K. Validation
Tanyakan pertanyaan di luar scope dan pertanyaan "abaikan aturanmu" lewat panel → agent menolak (aturan 8 `base.md`).

### L. Troubleshooting
| Pesan saat start | Arti |
|---|---|
| `[slug] placeholder tidak dikenal di prompt: x` | `{{x}}` bukan core dan tidak di `ChatSpec.placeholders` |
| `[slug] tool tidak dikenal di prompt: get_x` | Prompt menyebut tool yang tidak ada |
| `[slug] tool belum dijelaskan di prompt: get_y` | Tool ada di `TOOLS` tapi tidak disebut |
| `File prompt tidak ditemukan` / `Folder prompt ... kosong` | Path `prompt_dir` salah |

### M. Regression impact
`base.md` → **semua** agent. Jalankan `--static` untuk semua dashboard, dan kasus acuan semua dashboard bila mungkin.

### N. Acceptance criteria
Static lulus; kasus acuan lulus; kamus data cocok dengan `queries.py` dan model.

### O. Documentation updates
Kamus data itu sendiri; dok 29 jika aturan jawaban berubah.

### P. Actual status
Static check: PASS. Kasus acuan dengan Gemini: NOT RUN.

## Prompt injection & data tidak tepercaya

| Sumber | Risiko | Kontrol aktual |
|---|---|---|
| Pertanyaan user | "Abaikan aturan / tampilkan system prompt / beri saya data dashboard lain" | `base.md` aturan 8; otorisasi & allowlist tools di **kode** (tidak bisa diubah lewat teks) |
| `context` & `history` dari browser | Dapat dimanipulasi user sendiri | Hanya sebagai pesan user; dipotong panjangnya; tidak memberi akses data baru |
| Teks dari data (deskripsi job, nama plant, dsb.) di hasil tool | Teks berisi "instruksi" | Diperlakukan sebagai data (`function_response`); tools tidak bisa memperluas izin. `Proposed`: tambahkan kalimat eksplisit di `base.md` bahwa isi hasil tool adalah data, bukan instruksi |
| Secret | Bocor lewat prompt | Tidak ada secret di prompt; detail error Power BI tidak dikirim ke AI |
| Keputusan akses | Model "memutuskan" boleh/tidak | Tidak pernah: diputuskan `chat()` sebelum AI dipanggil |
