# 05 — Python Environment & Dependencies

### A. Objective
Membuat `.venv`, memasang dependency, dan mendiagnosis masalah paket.

### B. When to use
Setup awal, menambah library, error `ModuleNotFoundError` / `ImportError`.

### C. Prerequisites
Python 3.13.x di PATH ([04](04_WINDOWS_VSCODE_SETUP.md)).

### D. Architecture context
Semua perintah (`run.py`, `pytest`, `scripts/*`) harus memakai interpreter `.venv`. `run_mantra.bat` memanggil
`.venv\Scripts\python.exe` langsung dan berhenti dengan pesan jika `.venv` belum ada.

### E. Files involved
`requirements.txt`, `requirements-dev.txt`, `.venv/`.

### F. Step-by-step instructions
1. `py -m venv .venv` (atau `python -m venv .venv`) — membuat folder `.venv`.
2. `.\.venv\Scripts\Activate.ps1` — prompt berubah menjadi `(.venv) PS ...`.
3. `python -m pip --version` — harus menunjuk `...\.venv\Lib\site-packages\pip`.
4. `pip install -r requirements.txt` — dependency runtime.
5. `pip install -r requirements-dev.txt` — tambahan untuk test (pytest).
6. Verifikasi import (bagian I).

### G. Code or patch
`requirements.txt` (aktual):
```
Flask>=3.0,<4
msal>=1.28,<2
requests>=2.31,<3
python-dotenv>=1.0,<2
google-genai>=2.0,<3
httpx>=0.27,<1  # di-import langsung oleh core/chat/providers.py (juga dependency google-genai)
```
`requirements-dev.txt`: `-r requirements.txt` + `pytest>=8.0,<10`.

### H. Code explanation

| Paket | Dipakai di | Runtime/Dev | Fitur |
|---|---|---|---|
| Flask (+ Werkzeug, Jinja2) | seluruh `mantra/` | Runtime | Web, template, hash password (`werkzeug.security`) |
| msal | `core/auth.py` (Entra), `core/powerbi.py` (token Power BI) | Runtime | Login Microsoft (opsional), data Power BI |
| requests | `core/powerbi.py` | Runtime | HTTP ke Power BI |
| python-dotenv | `config.py` | Runtime | Baca `.env` |
| google-genai | `core/chat/providers.py` | Runtime (fitur AI) | Gemini. Di-import saat start walaupun API key kosong |
| httpx | `core/chat/providers.py` | Runtime (fitur AI) | Menangkap `httpx.TransportError` |
| pytest | `tests/` | Dev | Test |

Batas atas versi = versi mayor yang sudah diuji (komentar di `requirements.txt`). Jangan naikkan tanpa menjalankan test.

### I. Commands
```powershell
python --version
python -m pip --version
python -c "import sys; print(sys.executable)"
python -c "import flask, msal, requests, dotenv, httpx; from google import genai; print('OK')"
pip list
```

### J. Expected result — environment version matrix (Tested 26 Okt 2026)

| Komponen | Versi |
|---|---|
| Windows | 11 Pro 10.0.22631 |
| Python | 3.13.3 |
| pip | 26.2.2 |
| Flask / Werkzeug / Jinja2 | 3.1.3 / 3.1.9 / 3.1.6 |
| msal | 1.39.0 |
| requests | 2.34.2 |
| python-dotenv | 1.2.4 |
| google-genai | 2.33.0 |
| httpx | 0.28.1 |
| pytest | 9.1.1 |
| Git | 2.56.0.windows.2 |

### K. Validation
`python -m pytest` lulus; `python scripts\check_ai_agent.py --static` → `SEMUA LULUS`.

### L. Troubleshooting
| Gejala | Penyebab | Solusi |
|---|---|---|
| `ModuleNotFoundError: No module named 'flask'` | Interpreter bukan `.venv` / belum install | Cek `sys.executable`; `pip install -r requirements.txt` |
| `cannot import name 'genai' from 'google'` | Python global | Aktifkan `.venv` |
| `ModuleNotFoundError: pytest` | Belum install dev | `pip install -r requirements-dev.txt` |
| Konflik versi setelah upgrade | Versi mayor baru | Kembali ke rentang di `requirements.txt`, jalankan test |
| `.venv` rusak | — | Hapus `.venv`, buat ulang (data tidak hilang; `.env` & `instance/` di luar `.venv`) |

### M. Regression impact
Upgrade Flask/Werkzeug memengaruhi hash password, session, routing; upgrade google-genai memengaruhi
`providers.py` (API `types.*`). Jalankan seluruh test + `check_ai_agent.py --static`.

### N. Acceptance criteria
Import berhasil; versi dalam rentang `requirements.txt`; test lulus.

### O. Documentation updates
Tabel versi di atas; `requirements.txt` bila menambah paket.

### P. Actual status
| Item | Status |
|---|---|
| Versi terpasang (tabel J) | PASS |
| Install bersih dari nol | NOT RUN (`.venv` sudah ada) |
