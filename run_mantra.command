#!/bin/zsh
# Jalankan MANTRA di jendela Terminal sendiri (double-click dari Finder).
# Server tetap jalan walaupun VS Code ditutup. Tekan Ctrl+C atau tutup jendela ini untuk berhenti.
cd "${0:A:h}"
printf '\e]0;MANTRA server\a'
if [[ ! -x .venv/bin/python ]]; then
    echo "Virtual environment belum ada. Jalankan dulu: python3.13 -m venv .venv  lalu  .venv/bin/pip install -r requirements.txt"
    read -k 1 "?Tekan tombol apa saja untuk menutup..."
    exit 1
fi
.venv/bin/python run.py
echo
read -k 1 "?Tekan tombol apa saja untuk menutup..."
