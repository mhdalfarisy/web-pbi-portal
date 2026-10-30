# 04 — macOS & VS Code Setup

### A. Objective
MacBook siap untuk clone, menjalankan, dan mengedit MANTRA di VS Code. Padanan Windows ada di bagian Q.

### B. When to use
Laptop baru, clone ulang, atau interpreter VS Code salah.

### C. Prerequisites
Hak install software (password admin Mac); akses ke repository GitHub dan ke salinan `.env` yang aman (tidak ada di
GitHub).

### D. Architecture context
MANTRA berjalan sebagai proses Python lokal (`run.py`) di `http://localhost:5001`. VS Code hanya editor + terminal;
server bisa juga dijalankan di jendela Terminal sendiri lewat `run_mantra.command` (double-click di Finder).

### E. Files involved
`.venv/` (dibuat), `.env` (disalin), `run.py`, `run_mantra.command`, `requirements*.txt`.

### F. Step-by-step instructions

1. Install **Git**: `xcode-select --install` (Apple Git, teruji 2.50.1).
2. Install **Homebrew** (https://brew.sh), lalu **Python 3.13**: `brew install python@3.13`.
   Cek: `python3.13 --version` → `Python 3.13.x`.
3. Install **VS Code** + extension **Python** (Microsoft). Aktifkan perintah `code`:
   `Cmd+Shift+P` → *Shell Command: Install 'code' command in PATH*.
4. Clone:
   ```bash
   cd ~/Documents/Portfolio
   git clone https://github.com/mhdalfarisy/web-pbi-portal.git
   cd web-pbi-portal
   ```
5. Buat & aktifkan `.venv`, install dependency (detail [05](05_PYTHON_ENVIRONMENT_AND_DEPENDENCIES.md)):
   ```bash
   python3.13 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
   Pakai `python3.13` **eksplisit**. `python3` di Mac bisa menunjuk versi lain (mis. 3.14 dari Homebrew) atau bahkan
   venv project lain yang masih aktif di terminal.
6. Salin `.env`: `cp .env.example .env`, lalu isi ([06](06_CONFIGURATION_GUIDE.md)).
7. Buka folder di VS Code: `code .`
8. Pilih interpreter: `Cmd+Shift+P` → *Python: Select Interpreter* → `./.venv/bin/python`.
9. Buka terminal baru di VS Code (`` Ctrl+` ``) — prompt harus diawali `(.venv)`.
10. (Opsional) Launcher double-click: `run_mantra.command` sudah executable di repo. Kalau macOS menolak
    ("cannot be opened because it is from an unidentified developer"), klik kanan > **Open** sekali.

### G. Code or patch
Tidak ada. Folder `.vscode/` **tidak ada** di repo; pengaturan VS Code bersifat per laptop.

### H. Code explanation
`config.py` memuat `.env` dengan `override=True`. Alasannya (komentar di `config.py`): terminal VS Code bisa membawa
`.env` project lain (setting `python.terminal.useEnvFile`). MANTRA mencatat nama variabel yang tertimpa di log saat
start ("Variabel environment terminal ditimpa oleh .env MANTRA: ...").

### I. Commands
```bash
git --version
python3.13 --version
source .venv/bin/activate
python -c "import sys; print(sys.executable)"
```

### J. Expected result
`git version 2.50.1 (Apple Git-155)`, `Python 3.13.x`, executable
`.../web-pbi-portal/.venv/bin/python` (Tested 28 Okt 2026, macOS 26.6, Apple Silicon, Python 3.13.17).

### K. Validation
`python -m pytest` → `58 passed`; `python run.py` → halaman login di `http://localhost:5001`.

### L. Troubleshooting
| Gejala | Solusi |
|---|---|
| `python3.13: command not found` | `brew install python@3.13`; pastikan `/opt/homebrew/bin` ada di PATH (`eval "$(/opt/homebrew/bin/brew shellenv)"` di `~/.zprofile`) |
| `sys.executable` bukan `.../web-pbi-portal/.venv/bin/python` | Venv project lain masih aktif: `deactivate`, lalu `source .venv/bin/activate` |
| `ImportError: cannot import name 'genai' from 'google'` | Python global dipakai; aktifkan `.venv` |
| `Address already in use` di port 5001 | `lsof -nP -iTCP:5001 -sTCP:LISTEN` → `kill <PID>`, atau ganti `PORT` di `.env` (dan redirect URI Entra). Jangan pakai 5000 (AirPlay Receiver macOS) |
| `run_mantra.command` tidak mau dibuka | Klik kanan > Open; atau `chmod +x run_mantra.command` |
| Peringatan "Variabel environment terminal ditimpa oleh .env MANTRA" | Matikan `python.terminal.useEnvFile` untuk project lain, atau abaikan (MANTRA tetap memakai `.env`-nya sendiri) |

### M. Regression impact
Tidak ada (setup lokal).

### N. Acceptance criteria
Interpreter VS Code = `.venv`; test lulus; login tampil.

### O. Documentation updates
Perbarui tabel versi di dok 05 bila versi Python/Git teruji berubah.

### P. Actual status
| Item | Status |
|---|---|
| Python 3.13.17 di `.venv` (Homebrew), Git 2.50.1, macOS 26.6 arm64 | PASS (28 Okt 2026) |
| `python -m pytest` | PASS, 58 passed (28 Okt 2026). Kalau `PBI_CLIENT_ID=` kosong di `.env`, `test_env_file_wins_over_inherited_terminal_variables` gagal (lihat [PANDUAN_DEVELOPMENT_BERURUTAN §7](../PANDUAN_DEVELOPMENT_BERURUTAN.md#7-temuan-analis--catatan-penting)) |
| Clone dari GitHub di Mac bersih | NOT RUN |
| Konfigurasi `.vscode/` | Not Found / Not Applicable |

### Q. Padanan Windows (PowerShell)

Seluruh dokumentasi memakai perintah macOS, platform development project ini. Tabel ini hanya referensi kalau
terpaksa menjalankan project di Windows (tidak ada launcher Windows; jalankan `python run.py`):

| Kebutuhan | macOS (zsh) | Windows (PowerShell) |
|---|---|---|
| Install Python | `brew install python@3.13` | installer python.org, centang *Add python.exe to PATH* |
| Buat venv | `python3.13 -m venv .venv` | `py -m venv .venv` |
| Aktifkan venv | `source .venv/bin/activate` | `.\.venv\Scripts\Activate.ps1` (kalau diblokir: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`) |
| Python venv langsung | `.venv/bin/python` | `.venv\Scripts\python.exe` |
| Salin file | `cp a b` | `Copy-Item a b` |
| Set / hapus env sementara | `export X='...'` / `unset X` | `$env:X = "..."` / `Remove-Item Env:X` |
| Env untuk satu perintah | `PORT=5002 python run.py` | (tidak berlaku: `.env` selalu menang, lihat dok 06) |
| Cari teks | `grep -rnE "pola" folder` | `Get-ChildItem folder -Recurse \| Select-String "pola"` |
| Proses di port | `lsof -nP -iTCP:5001 -sTCP:LISTEN` | `netstat -ano \| findstr :5001` |
| Info / hentikan proses | `ps -p <PID> -o pid,command` / `kill <PID>` | `tasklist /FI "PID eq <PID>"` / `taskkill /PID <PID>` |
| Buang output curl | `-o /dev/null` | `curl.exe ... -o NUL` |
| Pilih interpreter VS Code | `./.venv/bin/python` | `.\.venv\Scripts\python.exe` |
| Refresh keras / lihat sumber | `Cmd+Shift+R` / `Cmd+Option+U` | `Ctrl+F5` / `Ctrl+U` |

Path di argumen Python (`python scripts/check_setup.py`, `python -m pytest tests/test_login_and_access.py`) memakai
`/` dan berjalan di kedua OS.
