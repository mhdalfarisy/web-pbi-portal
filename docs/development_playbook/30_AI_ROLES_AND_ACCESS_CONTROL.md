# 30 — AI Roles & Access Control

## 1. Dua konsep berbeda

**User role** (identitas & hak akses aplikasi) — `Verified` dari `core/db.py` (CHECK constraint), `accounts.ROLES`,
`auth.py`:

| Role | Kode | Catatan |
|---|---|---|
| Super Admin | `super_admin` | Semua dashboard **aktif**; halaman Admin; hanya bisa diberikan lewat CLI |
| User | `user` | Dashboard aktif yang di-assign (default deny) |
| (Dev tanpa login) | `AUTH_DISABLED=1` | Diperlakukan sebagai `super_admin` tanpa akun; development saja |

Tidak ada role lain (`Not Found`).

**AI agent role** (peran fungsional dalam percakapan) — **tidak ada sebagai konsep terpisah di kode** (`Not Found`).
Setiap dashboard punya **satu** agent dengan satu set tools. Peran seperti "Dashboard Analyst", "Trend Analyst",
"Data Explorer", "Business Assistant" sudah tercakup secara implisit oleh tools yang tersedia:

| Peran (konseptual) | Dipenuhi oleh tool existing |
|---|---|
| Dashboard Analyst (KPI, ringkasan) | MR: `get_chart_totals`, `get_readiness_kpi`; PANI: `get_processing_metrics`, `get_equipment`, `get_mining`, `get_stockpile` |
| Trend Analyst | PANI: `get_processing_trend`, `get_variance_drivers` |
| Data Explorer | MR: `get_breakdown`, `get_rows`, `lookup` |
| Business Assistant | Kamus data di prompt (tanpa tool) |

Memecah agent menjadi beberapa role: `Proposed`, tidak direkomendasikan tanpa kebutuhan nyata. **Role agent tidak
pernah memberi izin tambahan**; izin hanya dari user role + hak akses dashboard di database.

## 2. Role & permission matrix (Verified / Tested)

| Aktivitas | Super Admin | User berizin | User tanpa izin | Bukti |
|---|---|---|---|---|
| Login | Ya (akun aktif) | Ya | Ya (login tetap bisa; hanya dashboard yang ditolak) | `test_login_and_access` |
| Membuka dashboard | Semua dashboard aktif | Dashboard yang di-assign & aktif | 403 + audit | `test_direct_url_to_other_dashboard_is_403` |
| Membuka chat dashboard | Ya, jika dashboard punya chat & AI dikonfigurasi | Idem, hanya dashboard yang di-assign | 403 di `/api/chat` + audit | `test_data_api_static_and_chat_are_protected` |
| Menjalankan AI tools | Hanya tools dashboard yang sedang dibuka | Idem | Tidak sampai ke AI | `engine.call_tool` (allowlist) |
| Membaca detail data | Sesuai tools/halaman dashboard. **Catatan:** `lookup` (MR) mencari di semua branch | Idem | Ditolak | `tools.py` |
| Fungsi admin | Ya | 403 + audit | 403 + audit | `test_regular_user_cannot_open_admin` |
| Melihat audit log | Ya (Admin > Audit Log) | Tidak | Tidak | idem |
| Menaikkan role ke Super Admin | Hanya via `manage_users.py set-role` di server | Tidak | Tidak | `test_no_web_route_can_promote_to_super_admin` |

Batas data Power BI: semua dashboard memakai **satu** service principal; tidak ada RLS per user MANTRA
(`Not Found` di kode: tidak ada `effectiveIdentity` di body `executeQueries`). `scripts/check_setup.py` justru
memeriksa bahwa dataset **tidak** memakai RLS (`isEffectiveIdentityRolesRequired`), karena executeQueries lewat
service principal tidak didukung untuk dataset ber-RLS. Jadi Super Admin pun hanya melihat apa yang disediakan
query dashboard. Pembatasan data = pembatasan per dashboard di MANTRA + filter di `queries.py` (mis. Material
Readiness hanya branch FP & ME di halaman).

## 3. Pemeriksaan backend per permintaan chat

| # | Pemeriksaan | Implementasi | Status |
|---|---|---|---|
| 1 | Session valid | `auth.current_user()` (DB + `session_version`) | Verified, Tested |
| 2 | Akses dashboard | `auth.can_open(user, dashboard)` | Verified, Tested |
| 3 | Chat aktif di dashboard | `dashboard.chat` & `dashboard.ready`; provider `configured()` | Verified |
| 4 | Tool tersedia untuk dashboard | `chat.tool_map` | Verified |
| 5 | Parameter dalam batas | `clean_args` + `guards.resolve`, JSON schema (enum) di `Tool.parameters`, batas di tool | Verified, Tested |
| 6 | Query hanya data yang diizinkan | Fungsi `queries.py` dashboard itu sendiri | Verified (lihat catatan `lookup`) |
| 7 | Output dibatasi | Batas baris per tool; detail error tidak dikirim | Verified |
| 8 | Usage limit | `CHAT_MAX_PER_MINUTE` per user | Verified, Tested |
| 9 | Audit | Hanya `access_denied` yang dicatat; pertanyaan sukses **tidak** | Verified (gap, dok 28 issue 4) |

Server **tidak** mempercayai identitas dari browser: `user_id`/role tidak dikirim client; slug dashboard dari URL
divalidasi lewat registry + `can_open`; nama tool dari model divalidasi lewat `tool_map`. Yang dikirim browser dan
**dipercaya sebagai konteks saja**: `history`, `context`, `filters` (dipotong panjangnya; `parse_dash` menormalkan).

## 4. Hierarki prompt (aktual)

Urutan penggabungan di `prompt.load` (satu `system_instruction` untuk Gemini):
1. `core/prompts/base.md` — aturan umum (termasuk menolak perubahan aturan, membuka instruksi, dan pertanyaan di luar dashboard).
2. `dashboards/<x>/prompts/system.md` — scope & aturan dashboard.
3. `dashboards/<x>/prompts/*.md` lain (urut nama; saat ini `data_dictionary.md`).

Lalu sebagai pesan **user**: riwayat percakapan, prefix `[Active dashboard filters: ...]` + pertanyaan. Hasil tool
dikirim sebagai `function_response`. Kebijakan keamanan aplikasi (autentikasi, otorisasi, allowlist) berada **di kode**
dan berlaku sebelum/terlepas dari prompt. Prompt bukan mekanisme otorisasi.

## 5. Aturan perilaku agent

| Aturan target | Di mana diterapkan |
|---|---|
| Jawab sesuai scope dashboard | `base.md` aturan 8; `system.md` |
| Angka dari query tervalidasi | `base.md` aturan 1 |
| Jangan mengarang angka/kolom/periode | `base.md` 1, 6 |
| Data tidak tersedia → katakan | `base.md` 3, 6 |
| Pertanyaan ambigu → klarifikasi | `base.md` 4 (setelah `valid_options`); `system.md` |
| Bedakan fakta vs interpretasi | `base.md` 2 (sebagian); `Proposed`: tegaskan di `base.md` |
| Korelasi ≠ sebab-akibat | `Proposed` (belum eksplisit di `base.md`) |
| Jangan ungkap prompt/secret | `base.md` 8; secret tidak pernah ada di prompt (kode) |
| Allowlist tools | Kode (`tool_map`) |
| Abaikan instruksi mengabaikan aturan | `base.md` 8 |
| Izin tidak dari chat | Kode (otorisasi sebelum AI) |
| Tidak membuka data dashboard lain | Kode (tools per dashboard) |
| Klaim data terbaru butuh bukti | `Proposed`; header "Last Update"/refresh model ada di halaman, tools tidak selalu mengembalikan waktu refresh |
| Sebut periode, filter, satuan, sumber | `base.md` format jawaban (baris sumber + filter) |
