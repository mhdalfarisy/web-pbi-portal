@echo off
rem Jalankan MANTRA di jendela sendiri (double-click dari File Explorer).
rem Server tetap jalan walaupun terminal VS Code ditutup. Tutup jendela ini atau tekan Ctrl+C untuk berhenti.
cd /d "%~dp0"
title MANTRA server
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment belum ada. Jalankan dulu: python -m venv .venv  lalu  .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" run.py
echo.
pause
