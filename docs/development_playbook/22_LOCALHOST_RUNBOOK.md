# 22 — Localhost Runbook

### A. Objective
Menjalankan MANTRA di `http://localhost:5001` dan memastikan semuanya berfungsi.

### B. When to use
Setiap hari development; setelah setup; setelah perubahan besar.

### C. Prerequisites
Dok 04-06 selesai; ada akun (`python scripts\manage_users.py seed`).

### D. Architecture context
`run.py` menjalankan dev server Werkzeug di **`localhost`** (bukan `0.0.0.0`) pada `PORT` dari `.env`. Buka lewat
`http://localhost:<PORT>` (bukan `127.0.0.1`) supaya cookie & redirect URI Entra cocok (komentar `run.py`).

### E. Files involved
`run.py`, `run_mantra.bat`, `.env` (`PORT`, `FLASK_DEBUG`).

### F. Step-by-step instructions

**Cara 1 — terminal VS Code**
```powershell
.\.venv\Scripts\Activate.ps1
python run.py
```
**Cara 2 — jendela sendiri:** double-click `run_mantra.bat` (server tetap jalan walau VS Code ditutup; jendela tetap
terbuka saat server berhenti supaya pesan terbaca).

**Berhenti:** `Ctrl+C` / tutup jendela. **Restart wajib** setelah mengubah `.env`, prompt AI, manifest/registry,
atau kode Python (kecuali `FLASK_DEBUG=1` yang auto-reload kode).

### G. Code or patch
Tidak ada.

### H. Code explanation
`run.py` mencetak status (`Login: ON (email + password)` / `SKIPPED (AUTH_DISABLED=1 ...)`, `Debug: ON/OFF`) dan
saat berhenti mencetak `stopped (Ctrl+C or terminal closed)` atau `crashed (exit code N)`.

### I. Commands — smoke test (tanpa login, read-only)
```powershell
curl.exe -s -o NUL -w "%{http_code}`n" http://localhost:5001/login                     # 200
curl.exe -s -o NUL -w "%{http_code} %{redirect_url}`n" http://localhost:5001/          # 302 .../login
curl.exe -s -o NUL -w "%{http_code}`n" http://localhost:5001/d/material-readiness/api/detail   # 401
curl.exe -s -o NUL -w "%{http_code}`n" http://localhost:5001/static/css/shell.css      # 200
curl.exe -s -o NUL -w "%{http_code}`n" -X POST -d "email=x&password=x" http://localhost:5001/login  # 400 (CSRF)
curl.exe -s -D - -o NUL http://localhost:5001/login | Select-String "X-Frame|X-Content|Referrer"
netstat -ano | findstr :5001                                                          # PID yang mendengar
```

### J. Expected result (Tested 26 Okt 2026 pada server yang sedang berjalan, PID `.venv\Scripts\python.exe run.py`)

| Request | Hasil |
|---|---|
| `GET /` | 302 → `/login` |
| `GET /login`, `/forgot-password` | 200 |
| `GET /reports`, `/admin/users`, `/d/material-readiness/`, `/d/pani-processing/mining` | 302 → `/login?next=...` |
| `GET /d/material-readiness/api/detail` | 401 `application/json` |
| `GET /d/pani-processing/static/pani.js` | 302 → login (static dashboard ikut dijaga) |
| `GET /static/css/shell.css`, `/static/js/chat.js` | 200 |
| `GET /tidak-ada` | 404 |
| `POST /login` tanpa CSRF | 400 |
| Header | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, cookie `HttpOnly; SameSite=Lax` |

### K. Validation — checklist manual (setelah login)

| # | Cek | Lulus jika |
|---|---|---|
| 1 | Login sebagai Super Admin | Home tampil, menu Admin ada |
| 2 | Reports | Kartu sesuai hak akses |
| 3 | Buka Material Readiness Summary & Detail | Data tampil; "Last Update" terisi |
| 4 | Buka 4 halaman PANI, ganti tanggal | Data berubah sesuai filter |
| 5 | Klik bintang favorit | Masuk Favorites |
| 6 | History | Halaman yang dibuka tercatat |
| 7 | Ask AI (jika `GEMINI_API_KEY`) | Jawaban + daftar tool |
| 8 | Login sebagai user biasa, buka URL dashboard tanpa akses | 403 "Access denied" |
| 9 | Browser console (F12) | Tanpa error merah |
| 10 | Log server | Tanpa traceback; error Power BI tercatat dengan `[ref ...]` |

### L. Troubleshooting
| Gejala | Solusi |
|---|---|
| `OSError: [WinError 10048]` / port dipakai | `netstat -ano \| findstr :5001` → jika itu server MANTRA lama, tutup jendelanya; atau ganti `PORT` di `.env` (dan redirect URI Entra) |
| `RuntimeError: FLASK_SECRET_KEY belum diisi` | Isi `.env` |
| App gagal start dengan pesan prompt/tool | Perbaiki file prompt yang disebut (dok 31) |
| Login Microsoft `AADSTS50011` | Buka lewat `http://localhost:5001`; redirect URI harus `http://localhost:<PORT>/auth/callback` |
| Perubahan tidak terlihat | Restart; `Ctrl+F5` untuk CSS/JS |
| Selengkapnya | Dok 23 |

### M. Regression impact
Tidak ada (operasional).

### N. Acceptance criteria
Smoke test J sesuai; checklist K lulus untuk fitur yang dikonfigurasi.

### O. Documentation updates
Tabel J bila perilaku berubah.

### P. Actual status
| Item | Status |
|---|---|
| Smoke test tanpa login (tabel J) | PASS (26 Okt 2026). Catatan: server yang berjalan sudah start sebelum perubahan cleanup/rename hari itu; restart untuk memuat kode terbaru |
| Checklist K (login, data Power BI, AI) | NOT RUN (tidak memakai kredensial user / layanan berbayar) |
