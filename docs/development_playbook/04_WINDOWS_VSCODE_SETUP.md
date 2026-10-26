# 04 — Windows & VS Code Setup

### A. Objective
Laptop Windows siap untuk clone, menjalankan, dan mengedit MANTRA di VS Code.

### B. When to use
Laptop baru, clone ulang, atau interpreter VS Code salah.

### C. Prerequisites
Hak install software; akses ke repository GitHub dan ke salinan `.env` yang aman (tidak ada di GitHub).

### D. Architecture context
MANTRA berjalan sebagai proses Python lokal (`run.py`) di `http://localhost:5001`. VS Code hanya editor + terminal;
server bisa juga dijalankan di jendela sendiri lewat `run_mantra.bat`.

### E. Files involved
`.venv/` (dibuat), `.env` (disalin), `run.py`, `run_mantra.bat`, `requirements*.txt`.

### F. Step-by-step instructions

1. Install **Git for Windows** (teruji 2.56) dan **Python 3.13.x** (teruji 3.13.3, centang *Add python.exe to PATH*).
2. Install **VS Code** + extension **Python** (Microsoft).
3. Clone:
   ```powershell
   cd "D:\Training SSIS + Python + Streamlit"
   git clone https://github.com/mhdalfarisy/web-pbi-portal.git "Web App MANTRA"
   cd "Web App MANTRA"
   ```
4. Buat & aktifkan `.venv`, install dependency (detail [05](05_PYTHON_ENVIRONMENT_AND_DEPENDENCIES.md)).
5. Salin `.env`: `Copy-Item .env.example .env`, lalu isi ([06](06_CONFIGURATION_GUIDE.md)).
6. Buka folder di VS Code: `code .`
7. Pilih interpreter: `Ctrl+Shift+P` → *Python: Select Interpreter* → `.\.venv\Scripts\python.exe`.
8. Buka terminal baru di VS Code (`Ctrl+Shift+``) — prompt harus diawali `(.venv)`.

### G. Code or patch
Tidak ada. Folder `.vscode/` **tidak ada** di repo (`Not Found`); pengaturan VS Code bersifat per laptop.

### H. Code explanation
`config.py` memuat `.env` dengan `override=True`. Alasannya (komentar di `config.py`): terminal VS Code bisa membawa
`.env` project lain (setting `python.terminal.useEnvFile`). MANTRA mencatat nama variabel yang tertimpa di log saat
start ("Variabel environment terminal ditimpa oleh .env MANTRA: ...").

### I. Commands
```powershell
git --version
python --version
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
```

### J. Expected result
`git version 2.56...`, `Python 3.13.3`, executable di `...\Web App MANTRA\.venv\Scripts\python.exe` (Tested 26 Okt 2026).

### K. Validation
`python -m pytest` → `58 passed`; `python run.py` → halaman login di `http://localhost:5001`.

### L. Troubleshooting
| Gejala | Solusi |
|---|---|
| `Activate.ps1 cannot be loaded because running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `ImportError: cannot import name 'genai' from 'google'` | Python global dipakai; aktifkan `.venv` |
| Peringatan "Variabel environment terminal ditimpa oleh .env MANTRA" | Matikan `python.terminal.useEnvFile` untuk project lain, atau abaikan (MANTRA tetap memakai `.env`-nya sendiri) |
| `py` tidak dikenal | Pakai `python` langsung |

### M. Regression impact
Tidak ada (setup lokal).

### N. Acceptance criteria
Interpreter VS Code = `.venv`; test lulus; login tampil.

### O. Documentation updates
Perbarui tabel versi di dok 05 bila versi Python/Git teruji berubah.

### P. Actual status
| Item | Status |
|---|---|
| Python 3.13.3 di `.venv`, Git 2.56 | PASS (26 Okt 2026) |
| Clone dari GitHub di laptop bersih | NOT RUN |
| Konfigurasi `.vscode/` | Not Found / Not Applicable |
