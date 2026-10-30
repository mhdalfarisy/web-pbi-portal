# MANTRA Development Playbook

Buku panduan development **Power BI Portal (MANTRA)** untuk developer: dari folder kosong sampai aplikasi berjalan di
`http://localhost:5001`, lalu cara mengembangkannya (halaman baru, dashboard baru, AI agent, perbaikan bug).

> Mulai dari **[00_START_HERE.md](00_START_HERE.md)**.
>
> Mau membangun dari nol secara berurutan? Ikuti **[PANDUAN_DEVELOPMENT_BERURUTAN.md](../PANDUAN_DEVELOPMENT_BERURUTAN.md)**
> (fase 0-14) beserta seri pendalamannya di **[panduan_development/](../panduan_development/01_KONSEP_TEKNOLOGI.md)**.
> Semua dokumen ini juga tersedia sebagai satu PDF: **[docs/ebook/](../ebook/README.md)**.

Dokumentasi disusun dari source code aktual (diperiksa 26 Oktober 2026). Setiap klaim diberi status:

| Status | Arti |
|---|---|
| `Verified` | Kode sudah dibaca dan perilakunya dipastikan dari kode |
| `Existing` | File/komponen ada, perilaku tertentu belum diperiksa rinci |
| `Tested` | Perilaku diuji (pytest / script / request ke localhost) dan hasilnya tercatat |
| `Pending` | Masih perlu diperiksa |
| `Not Found` | Sudah dicari di cakupan yang jelas dan tidak ada |
| `Proposed` | Rekomendasi, **belum** diimplementasikan |
| `Not Applicable` | Tidak relevan untuk implementasi ini |

## Cari dokumen berdasarkan tujuan

| Saya ingin... | Baca |
|---|---|
| Paham MANTRA itu apa | [01_PROJECT_OVERVIEW](01_PROJECT_OVERVIEW.md) |
| Tahu fungsi setiap file | [02_PROJECT_STRUCTURE](02_PROJECT_STRUCTURE.md) |
| Paham urutan membangun aplikasi | [03_DEVELOPMENT_ROADMAP](03_DEVELOPMENT_ROADMAP.md), [27_REBUILD_FROM_ZERO](27_REBUILD_FROM_ZERO.md) |
| Setup laptop baru | [04_MACOS_VSCODE_SETUP](04_MACOS_VSCODE_SETUP.md), [05_PYTHON_ENVIRONMENT_AND_DEPENDENCIES](05_PYTHON_ENVIRONMENT_AND_DEPENDENCIES.md), [06_CONFIGURATION_GUIDE](06_CONFIGURATION_GUIDE.md) |
| Menjalankan aplikasi | [22_LOCALHOST_RUNBOOK](22_LOCALHOST_RUNBOOK.md) |
| Paham alur request | [07_FLASK_STARTUP_AND_REQUEST_LIFECYCLE](07_FLASK_STARTUP_AND_REQUEST_LIFECYCLE.md) |
| Mengubah tampilan saja | [18_FRONTEND_ONLY_CHANGES](18_FRONTEND_ONLY_CHANGES.md), [08_FRONTEND_ARCHITECTURE](08_FRONTEND_ARCHITECTURE.md) |
| Mengubah route / query / database | [19_BACKEND_AND_DATA_CONTRACT_CHANGES](19_BACKEND_AND_DATA_CONTRACT_CHANGES.md), [09_BACKEND_ARCHITECTURE](09_BACKEND_ARCHITECTURE.md), [10_FRONTEND_BACKEND_CONTRACT](10_FRONTEND_BACKEND_CONTRACT.md) |
| Menambah halaman di dashboard yang sudah ada | [16_DASHBOARD_PAGE_DEVELOPMENT](16_DASHBOARD_PAGE_DEVELOPMENT.md) |
| Menambah dashboard baru | [17_NEW_DASHBOARD_DEVELOPMENT](17_NEW_DASHBOARD_DEVELOPMENT.md), [14_DASHBOARD_REGISTRY](14_DASHBOARD_REGISTRY.md) |
| Bekerja dengan Power BI | [15_POWERBI_INTEGRATION](15_POWERBI_INTEGRATION.md) |
| Login, role, hak akses | [12_AUTHENTICATION_AUTHORIZATION](12_AUTHENTICATION_AUTHORIZATION.md), [../AUTH.md](../AUTH.md) |
| Database & migrasi | [11_DATABASE_AND_MIGRATIONS](11_DATABASE_AND_MIGRATIONS.md) |
| AI agent | [20](20_AI_AGENT_DEVELOPMENT.md), [29](29_AI_CHAT_FLOW_AND_TOOL_CALLING.md), [30](30_AI_ROLES_AND_ACCESS_CONTROL.md), [31](31_PROMPT_ENGINEERING_AND_DATA_DICTIONARY.md), [32](32_AI_AGENT_TESTING_AND_GROUNDING.md), [33](33_ADD_AI_AGENT_TO_DASHBOARD.md) |
| Menjalankan test | [21_TESTING_AND_REGRESSION](21_TESTING_AND_REGRESSION.md) |
| Ada error / bug | [23_DEBUGGING_PLAYBOOK](23_DEBUGGING_PLAYBOOK.md), [26_DEVELOPMENT_DECISION_GUIDE](26_DEVELOPMENT_DECISION_GUIDE.md) |
| Keamanan & secret | [24_SECURITY_AND_SECRETS](24_SECURITY_AND_SECRETS.md) |
| Release, backup, rollback | [25_RELEASE_AND_ROLLBACK](25_RELEASE_AND_ROLLBACK.md) |
| Status, gap, known issues, handover | [28_PARITY_AND_HANDOVER](28_PARITY_AND_HANDOVER.md) |

## Daftar lengkap

| No | Dokumen | Isi |
|---|---|---|
| 00 | [START_HERE](00_START_HERE.md) | Peta belajar & urutan membaca |
| 01 | [PROJECT_OVERVIEW](01_PROJECT_OVERVIEW.md) | Identitas, ruang lingkup, arsitektur ringkas |
| 02 | [PROJECT_STRUCTURE](02_PROJECT_STRUCTURE.md) | Inventaris file + status verifikasi |
| 03 | [DEVELOPMENT_ROADMAP](03_DEVELOPMENT_ROADMAP.md) | CP-01 s.d. CP-16 |
| 04 | [MACOS_VSCODE_SETUP](04_MACOS_VSCODE_SETUP.md) | Git, Homebrew, Python, VS Code di macOS (+ padanan Windows) |
| 05 | [PYTHON_ENVIRONMENT_AND_DEPENDENCIES](05_PYTHON_ENVIRONMENT_AND_DEPENDENCIES.md) | `.venv`, requirements, versi |
| 06 | [CONFIGURATION_GUIDE](06_CONFIGURATION_GUIDE.md) | `.env`, `config.py`, matriks konfigurasi |
| 07 | [FLASK_STARTUP_AND_REQUEST_LIFECYCLE](07_FLASK_STARTUP_AND_REQUEST_LIFECYCLE.md) | Startup & siklus request |
| 08 | [FRONTEND_ARCHITECTURE](08_FRONTEND_ARCHITECTURE.md) | Template, CSS, JS |
| 09 | [BACKEND_ARCHITECTURE](09_BACKEND_ARCHITECTURE.md) | Modul Python & dependency |
| 10 | [FRONTEND_BACKEND_CONTRACT](10_FRONTEND_BACKEND_CONTRACT.md) | Route, payload, API, CSRF |
| 11 | [DATABASE_AND_MIGRATIONS](11_DATABASE_AND_MIGRATIONS.md) | SQLite, skema, migrasi, backup |
| 12 | [AUTHENTICATION_AUTHORIZATION](12_AUTHENTICATION_AUTHORIZATION.md) | Login & hak akses |
| 13 | [PORTAL_DEVELOPMENT](13_PORTAL_DEVELOPMENT.md) | Halaman portal & admin |
| 14 | [DASHBOARD_REGISTRY](14_DASHBOARD_REGISTRY.md) | Manifest & auto-discovery |
| 15 | [POWERBI_INTEGRATION](15_POWERBI_INTEGRATION.md) | Service principal, DAX, cache |
| 16 | [DASHBOARD_PAGE_DEVELOPMENT](16_DASHBOARD_PAGE_DEVELOPMENT.md) | Workflow A |
| 17 | [NEW_DASHBOARD_DEVELOPMENT](17_NEW_DASHBOARD_DEVELOPMENT.md) | Workflow B |
| 18 | [FRONTEND_ONLY_CHANGES](18_FRONTEND_ONLY_CHANGES.md) | Workflow C |
| 19 | [BACKEND_AND_DATA_CONTRACT_CHANGES](19_BACKEND_AND_DATA_CONTRACT_CHANGES.md) | Workflow D |
| 20 | [AI_AGENT_DEVELOPMENT](20_AI_AGENT_DEVELOPMENT.md) | Arsitektur & lifecycle AI agent |
| 21 | [TESTING_AND_REGRESSION](21_TESTING_AND_REGRESSION.md) | pytest & regression |
| 22 | [LOCALHOST_RUNBOOK](22_LOCALHOST_RUNBOOK.md) | Menjalankan & smoke test |
| 23 | [DEBUGGING_PLAYBOOK](23_DEBUGGING_PLAYBOOK.md) | Troubleshooting |
| 24 | [SECURITY_AND_SECRETS](24_SECURITY_AND_SECRETS.md) | Kontrol keamanan |
| 25 | [RELEASE_AND_ROLLBACK](25_RELEASE_AND_ROLLBACK.md) | Commit, backup, rollback |
| 26 | [DEVELOPMENT_DECISION_GUIDE](26_DEVELOPMENT_DECISION_GUIDE.md) | Memilih workflow |
| 27 | [REBUILD_FROM_ZERO](27_REBUILD_FROM_ZERO.md) | Membangun ulang dari folder kosong |
| 28 | [PARITY_AND_HANDOVER](28_PARITY_AND_HANDOVER.md) | Parity, known issues, handover |
| 29 | [AI_CHAT_FLOW_AND_TOOL_CALLING](29_AI_CHAT_FLOW_AND_TOOL_CALLING.md) | Alur tanya-jawab end-to-end |
| 30 | [AI_ROLES_AND_ACCESS_CONTROL](30_AI_ROLES_AND_ACCESS_CONTROL.md) | Role user vs role agent |
| 31 | [PROMPT_ENGINEERING_AND_DATA_DICTIONARY](31_PROMPT_ENGINEERING_AND_DATA_DICTIONARY.md) | Prompt & kamus data |
| 32 | [AI_AGENT_TESTING_AND_GROUNDING](32_AI_AGENT_TESTING_AND_GROUNDING.md) | Test & grounding AI |
| 33 | [ADD_AI_AGENT_TO_DASHBOARD](33_ADD_AI_AGENT_TO_DASHBOARD.md) | Menambah AI agent ke dashboard |

**Penomoran:** dokumen AI tambahan dari permintaan awal (`21_AI_CHAT_FLOW...` s.d. `25_ADD_AI_AGENT...`) bentrok dengan
nomor 21-25 yang sudah dipakai, jadi diberi nomor 29-33. `20_AI_AGENT_DEVELOPMENT.md` dipakai bersama.

**Dokumen terkait di luar folder ini:** [README.md](../../README.md) (setup ringkas), [docs/AUTH.md](../AUTH.md)
(login, RBAC, skema, rollback), [scripts/README.md](../../scripts/README.md), [tests/README.md](../../tests/README.md),
[docs/PANDUAN_DEVELOPMENT_BERURUTAN.md](../PANDUAN_DEVELOPMENT_BERURUTAN.md) (jalur build berurutan),
[docs/panduan_development/](../panduan_development/01_KONSEP_TEKNOLOGI.md) (konsep, kode inti, logika bisnis),
[docs/ebook/](../ebook/README.md) (PDF gabungan + script build).
Folder `audit_reports/` sengaja tidak dibuat ulang (sudah dihapus pemilik project); matriks dependency, versi,
konfigurasi, known issues, dan parity ada di dokumen 02, 05, 06, 09, dan 28.
