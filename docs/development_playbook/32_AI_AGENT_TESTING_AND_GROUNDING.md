# 32 — AI Agent Testing & Grounding

## 1. Cakupan test saat ini (Verified)

| Kategori | Kasus | Ada di | Status |
|---|---|---|---|
| Authentication | Belum login → 401 | `test_data_api_static_and_chat_are_protected` (sebagian), `test_anonymous_is_redirected_or_401` | PASS |
| Authorization | User tanpa akses dashboard → 403 | `test_data_api_static_and_chat_are_protected` | PASS |
| Authorization | Tool terlarang / dashboard lain | Allowlist per dashboard (kode); tidak ada test khusus | Verified, test `Proposed` |
| Prompt | Placeholder & nama tool valid, komentar tidak terkirim | `check_ai_agent.py --static` | PASS |
| Prompt | Di luar scope | `case_out_of_scope` (MR & PANI) | NOT RUN (Gemini) |
| Tool | Parameter tidak valid → `valid_options` | `test_invalid_tool_argument_returns_valid_options` | PASS |
| Tool | Exception tak terduga tidak memutus chat | `test_unexpected_tool_error_does_not_break_chat` | PASS |
| Tool | Pencocokan status/company/week | `check_ai_agent.py --static` (guards) | PASS |
| Tool | Kolom tidak tersedia | `case_unavailable_column` (MR) | NOT RUN |
| Grounding | Angka sesuai query (dihitung dari queries saat tes) | `chat_cases.py` (MR 8, PANI 5) | NOT RUN (README: MR 8 lulus sebelumnya) |
| Provider | Rate limit per user (429) | `test_chat_is_rate_limited_per_user` | PASS |
| Provider | Timeout / 503 / model cadangan / API key salah | Tidak ada test (`Proposed`: mock `genai` client) | — |
| Frontend chat | Kirim, loading, tampil, error | Tidak ada test JS | — |

## 2. Cara kerja `chat_cases.py`

Setiap `case_<nama>()` mengembalikan `{question, filters, context, checks}` atau `{"skip": alasan}`. `checks(answer,
used)` → list `(label, lulus?)`. **Jawaban acuan dihitung dari `queries`/`tools` saat tes**, jadi tetap valid
walau data berubah. Contoh helper: `numbers(text)` mengekstrak bilangan dari jawaban (format ribuan EN/ID).

## 3. Evaluation dataset

Status per 26 Okt 2026: semua baris di bawah **NOT RUN** di sesi ini (butuh kuota Gemini + Power BI). Kolom
"Actual" diisi saat dijalankan.

| Test ID | User role | Dashboard | Question (ringkas) | Expected authorization | Expected tool | Expected parameters | Expected data basis | Expected behavior | Actual | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| MR-01 `case_lookup_site_job` | user berizin MR | material-readiness | "apa type dari work order W0417321 dan apa PO_Status Description nya ?" | izin | `lookup` | `field=job_code`, `value=W0417321` | `tool_lookup` (semua branch) | Sebut semua type, setiap status + jumlahnya, dan jelaskan branch SITE (tidak tampil di dashboard) | | NOT RUN |
| MR-02 `case_lookup_not_found` | idem | idem | "apa status work order ZZ99999999?" | izin | `lookup` | kode tsb | tidak ditemukan | Menyatakan tidak ditemukan | | NOT RUN |
| MR-03 `case_chart_total_this_month` | idem | idem | "Berapa total material PO bulan ini per status?" (filter dashboard = bulan ini) | izin | `get_chart_totals` | `type=PO` + filter bulan ini | `tool_chart` | Total & angka per status = tool | | NOT RUN |
| MR-04 `case_status_alias_so` | idem | idem | "Berapa item SO yang not ready bulan ini?" | izin | `get_chart_totals` | `type=SO`, status "not ready" → `All Not Ready` | `tool_chart` | Angka = tool | | NOT RUN |
| MR-05 `case_company_code` | idem | idem | "Berapa total material PO bulan ini untuk MMI?" | izin | `get_chart_totals` | `company` dinormalkan ke nama lengkap MMI | `tool_chart` | Total = tool | | NOT RUN |
| MR-06 `case_breakdown_plant` | idem | idem | "Plant mana yang paling banyak FP Not Ready di tahun <tahun ini>?" | izin | `get_breakdown` | `group_by=plant`, `status=FP Not Ready` | `tool_breakdown` | Plant teratas + jumlah baris | | NOT RUN |
| MR-07 `case_out_of_scope` | idem | idem | "Siapa presiden pertama Indonesia?" | izin | tidak ada | — | — | Tanpa tool, menolak sopan (menyebut Material Readiness) | | NOT RUN |
| MR-08 `case_unavailable_column` | idem | idem | "Work order W0417321 dikerjakan oleh section apa?" | izin | — | — | kamus data | Menyatakan data belum/tidak tersedia | | NOT RUN |
| PANI-01 `case_gold_ytd` | user berizin PANI | pani-processing | "Berapa gold produced YTD dan targetnya?" (rentang 1 Jan s/d data terakhir) | izin | `get_processing_metrics` atau `get_variance_drivers` | rentang YTD | `queries.processing` | Actual & target YTD = data | | NOT RUN |
| PANI-02 `case_drivers` | idem | idem | "Apa 5 penyebab variance negatif terbesar tahun ini?" | izin | `get_variance_drivers` | — | `processing()["drivers"]` | Menyebut driver teratas | | NOT RUN |
| PANI-03 `case_equipment_day` | idem | idem | "Berapa unit equipment yang aktif dan tidak aktif pada 1 Agustus 2026?" | izin | `get_equipment` | 2026-08-01 | `queries.equipment` | Jumlah aktif & nonaktif = data | | NOT RUN |
| PANI-04 `case_mining_mtd` | idem | idem | "Bagaimana total mined MTD dibanding plan?" (filter 1-3 Agu 2026) | izin | `get_mining` | rentang filter | `mining()["periods"]["mtd"]` | Actual & plan MTD = data | | NOT RUN |
| PANI-05 `case_out_of_scope` | idem | idem | "Berapa harga emas dunia hari ini?" | izin | tidak ada | — | — | Tanpa tool, menolak (menyebut PANI) | | NOT RUN |
| AUTH-01 | user tanpa izin | pani-processing | apa saja | **403** sebelum AI | — | — | — | Pesan "no access" | 403 | PASS (pytest) |
| AUTH-02 | anonim | apa saja | apa saja | **401** | — | — | — | Pesan sesi kedaluwarsa | 401 | PASS (pytest) |
| LIM-01 | user berizin | material-readiness | > `CHAT_MAX_PER_MINUTE` per menit | izin | — | — | — | 429 | 429 | PASS (pytest) |

Detail parameter yang tepat ada di masing-masing fungsi `case_*` (sumber kebenaran).

## 4. Prosedur menjalankan

```powershell
python scripts\check_ai_agent.py --static                              # gratis, semua agent
python scripts\check_ai_agent.py --dashboard material-readiness        # static + semua kasus (kuota)
python scripts\check_ai_agent.py --dashboard material-readiness lookup # hanya kasus yang namanya mengandung "lookup"
python -m pytest -k "chat or tool"                                     # test pytest terkait AI (provider palsu)
```
Jawaban AI bisa sedikit berbeda setiap kali; jika satu kasus gagal, jalankan ulang kasus itu sebelum mengubah prompt.
Gunakan provider asli hanya bila kredensial, akses, dan kuota tersedia serta diizinkan.

## 5. Acceptance criteria agent

| Kriteria | Status saat ini |
|---|---|
| Chat route: autentikasi & otorisasi | PASS (pytest) |
| Tools tervalidasi & dibatasi | PASS (static + pytest) |
| Data contract jelas | Verified (`tools.py` JSON schema + deskripsi) |
| Jawaban tidak mengarang angka | NOT RUN di sesi ini (kasus acuan) |
| Data kosong & error ditangani | Verified (`add_hint`, error tool) / PASS (pytest error tool) |
| Role & izin diuji | PASS |
| Prompt & kamus data terdokumentasi | Verified |
| Test cases tersedia & hasil dicatat | Tersedia; hasil aktual NOT RUN |
| Tidak ada secret bocor | PASS (`test_audit_log_and_app_log_contain_no_secrets`; error Power BI tidak ke AI) |
| Batasan AI diketahui | Panel menampilkan "answers can be wrong, check the dashboard"; dok 28 |
