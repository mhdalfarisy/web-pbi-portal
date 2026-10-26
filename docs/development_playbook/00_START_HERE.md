# 00 — Start Here

## Kamu siapa, baca apa

| Peran / kebutuhan | Urutan baca | Waktu |
|---|---|---|
| **Developer baru** (belum pernah buka project) | 01 → 02 → 04 → 05 → 06 → 22 → 07 → 08 → 09 → 21 | ± 1 hari |
| Mau langsung menjalankan di laptop | 04 → 05 → 06 → 22 | ± 1 jam |
| Mau mengubah tampilan | 08 → 18 → 21 | |
| Mau menambah halaman di dashboard | 14 → 15 → 10 → 16 → 21 | |
| Mau menambah dashboard baru | 14 → 15 → 17 → 33 → 21 | |
| Mau mengembangkan AI agent | 20 → 29 → 30 → 31 → 32 → 33 | |
| Ada error | 26 → 23 | |
| Mau membangun ulang dari nol | 03 → 27 | |
| Serah terima / status project | 28 | |

## Gambaran 60 detik

MANTRA adalah website **Flask** (Python). User login, lalu membuka report. Data report **tidak disimpan** di
MANTRA: setiap halaman menjalankan query DAX langsung ke **semantic model Power BI** lewat REST API
`executeQueries`. Setiap dashboard punya **AI agent** (Gemini) yang menjawab pertanyaan dengan memanggil
"tools" Python, dan tools itu memakai query yang sama dengan halaman. Database lokal SQLite
(`instance/mantra.db`) hanya menyimpan akun, hak akses, audit log, Favorites, dan History.

```
Browser ──> Flask (mantra/) ──> Power BI REST API (data report)
                  │       └───> Gemini API (AI agent)
                  └──> instance/mantra.db (akun, hak akses, audit, favorit, riwayat)
```

## 5 konsep yang harus dipahami lebih dulu

1. **Application factory**: `mantra/__init__.py:create_app()` merakit seluruh aplikasi. Dok 07.
2. **Dashboard = plug-in**: setiap folder di `mantra/dashboards/` (tanpa awalan `_`) yang punya variabel
   `DASHBOARD` otomatis terdaftar. Dok 14.
3. **Akses dicek di server**: `core/registry.py:_guard` memeriksa login + hak akses di **setiap** route dashboard
   (halaman, API, file static). Menyembunyikan menu tidak cukup. Dok 12.
4. **Query lewat satu pintu**: `queries.py` dashboard → `core/powerbi.query()` → Power BI. Dok 15.
5. **AI tidak menulis DAX**: AI hanya boleh memanggil tool yang terdaftar, parameternya divalidasi kode. Dok 29.

## Aturan kerja harian

- Selalu pakai Python dari `.venv` (`.venv\Scripts\Activate.ps1`).
- Setelah mengubah kode: `python -m pytest` (harus **58 passed**, angka per 26 Oktober 2026).
- Setelah mengubah prompt/tools AI: `python scripts\check_ai_agent.py --static`, lalu **restart Flask**.
- Jangan commit `.env`, jangan hapus `instance/mantra.db`, jangan ubah migrasi database yang sudah ada.
- Ubah file fondasi (lihat daftar di dok 02, bagian "Tingkat risiko file") hanya setelah analisis dampak.

## Status dokumentasi

Disusun dari pembacaan source code + pengujian lokal pada 26 Oktober 2026. Hasil uji aktual & yang **tidak**
diuji (Power BI asli, Gemini asli, login Microsoft) dicatat di [28_PARITY_AND_HANDOVER](28_PARITY_AND_HANDOVER.md).
