# 25 — Release & Rollback (lokal)

> Server staging & production: lihat `docs/DEPLOY_SERVER.md` (gunicorn, systemd, backup/restore di server).

### A. Objective
Menyimpan perubahan dengan aman (git), membuat titik pemulihan database, dan kembali ke kondisi sebelumnya bila perlu.

### B. When to use
Sebelum/sesudah fitur, sebelum migrasi database, saat perubahan menyebabkan masalah.

### C. Prerequisites
`python -m pytest` lulus; tahu file apa saja yang berubah (`git status`).

### D. Architecture context
Dua hal terpisah yang harus dikembalikan bersama: **kode** (git) dan **database** (`instance/mantra.db`, tidak di git).
Kode baru + DB lama → migrasi otomatis (dengan backup). Kode lama + DB baru → **gagal start** jika versi DB lebih tinggi
("Database versi N lebih baru dari kode").

### E. Files involved
Seluruh repo, `instance/mantra.db`, `instance/backups/`.

### F. Step-by-step instructions

**Release lokal**
1. `python -m pytest` dan `python scripts/check_ai_agent.py --static` → lulus.
2. `git status` → pastikan `.env`, `instance/` tidak muncul.
3. `git diff` → tinjau.
4. Kelompokkan commit per tujuan (mis. fitur vs dokumentasi). Rename file: `git add -A` agar terdeteksi sebagai rename.
5. Jika ada migrasi: `python scripts/manage_users.py backup` sebelum start kode baru.
6. Restart server; jalankan smoke test dok 22.

**Rollback kode**
1. Hentikan server.
2. Perubahan belum di-commit dan ingin disimpan dulu: `git stash`. Sudah di-commit: `git revert <commit>` (membuat commit
   pembalik, riwayat tetap utuh).
3. Start server, smoke test.

**Rollback database** (Verified dengan `docs/AUTH.md`)
```bash
# 1. Hentikan server (Ctrl+C / tutup jendela run_mantra.command)
# 2. Simpan DB sekarang (pakai perintah backup: database mode WAL, cp mantra.db saja bisa tidak lengkap),
#    lalu pulihkan backup dan hapus file WAL milik database lama
python scripts/manage_users.py backup
cp instance/backups/mantra-<waktu>-<label>.db instance/mantra.db
rm -f instance/mantra.db-wal instance/mantra.db-shm
# 3. Start server (kode harus versi yang sesuai dengan DB tersebut atau lebih baru)
```

### G. Code or patch
Tidak ada.

### H. Code explanation
Backup dibuat dengan SQLite backup API (`db.backup`) sehingga konsisten walau DB sedang dipakai.

### I. Commands
```bash
python scripts/manage_users.py backup     # -> instance/backups/mantra-<waktu>-manual.db
git status
git log --oneline -5
```

### J. Expected result
`Backup: .../instance/backups/mantra-YYYYmmdd-HHMMSS-manual.db`.

### K. Validation
Setelah restore: login, Admin > Users menampilkan akun yang diharapkan.

### L. Troubleshooting
| Gejala | Solusi |
|---|---|
| Kode lama gagal start: "Database versi N lebih baru dari kode" | Pulihkan backup `before-v<N>` yang dibuat sebelum migrasi, atau pakai kode terbaru |
| `git revert` konflik | Selesaikan konflik manual; jangan `reset --hard` jika ada perubahan yang belum disimpan |

### M. Regression impact
Restore DB mengembalikan akun, akses, audit, favorit, riwayat ke titik backup (perubahan setelahnya hilang; DB saat
ini tetap tersimpan di langkah 2).

### N. Acceptance criteria
Ada backup sebelum migrasi; commit tidak berisi secret; smoke test lulus setelah release/rollback.

### O. Documentation updates
README/AUTH.md bila prosedur berubah.

### P. Actual status (26 Okt 2026)
| Item | Status |
|---|---|
| `instance/backups/` | Not Found — **belum ada titik rollback**. Disarankan segera `manage_users.py backup` |
| Working tree | Banyak perubahan belum di-commit (perbaikan audit, cleanup, rename `scripts/` & `tests/`, playbook ini). Belum di-commit atas permintaan pemilik |
| `docs/powerbi_fixes/` | Dihapus dari working tree, belum di-commit; bisa `git restore docs/powerbi_fixes` |
| Prosedur rollback | NOT RUN (tidak dijalankan di sesi ini) |
