# 23 — Debugging & Troubleshooting Playbook

Aturan umum: **jangan** mulai dengan langkah destruktif (hapus `instance/mantra.db`, `git reset --hard`, hapus
`.venv`). Mulai dari membaca pesan error pertama di terminal server. Pesan error Power BI ke user selalu membawa
**kode ref**; cari `[ref XXXXXXXX]` di log server untuk detailnya.

Format setiap entri: Gejala · Penyebab · File · Reproduksi · Diagnostik · Membaca hasil · Solusi aman · Uji perbaikan · Risiko regresi · Selesai jika.

---

### 1. Flask startup failure
| | |
|---|---|
| Gejala | `python run.py` berhenti dengan traceback / `crashed (exit code 1)` |
| Penyebab | `FLASK_SECRET_KEY` kosong; prompt rusak; manifest dashboard salah; DB versi lebih baru; import error |
| File | `mantra/__init__.py`, `config.py`, `core/registry.py`, `core/chat/prompt.py`, `core/db.py` |
| Reproduksi | `python run.py` |
| Diagnostik | Baca baris **terakhir** traceback; `python -c "import sys; sys.path.insert(0,'.'); from mantra import create_app; create_app()"` |
| Membaca hasil | `FLASK_SECRET_KEY belum diisi` → `.env`; `[slug] tool belum dijelaskan di prompt` / `placeholder tidak dikenal` → prompt; `tidak punya variabel DASHBOARD` / `Slug dashboard dobel` → manifest; `Database versi N lebih baru dari kode` → kode lama |
| Solusi aman | Perbaiki file yang disebut. Sementara bisa `DASHBOARD_STRICT=0` untuk menyembunyikan dashboard rusak (jangan permanen) |
| Uji | `python -m pytest` |
| Risiko regresi | Rendah jika hanya memperbaiki file yang disebut |
| Selesai jika | Server start, `/login` 200 |

### 2. Import error
| | |
|---|---|
| Gejala | `ModuleNotFoundError`, `ImportError: cannot import name 'genai' from 'google'` |
| Penyebab | Bukan Python `.venv`; paket belum terpasang; dijalankan dari folder lain |
| File | `requirements.txt` |
| Diagnostik | `python -c "import sys; print(sys.executable)"`; `pip list` |
| Solusi | Aktifkan `.venv`; `pip install -r requirements.txt`; jalankan dari root project |
| Selesai jika | Import di dok 05 §I berhasil |

### 3. Dependency mismatch
| | |
|---|---|
| Gejala | `AttributeError` di library, perilaku aneh setelah `pip install --upgrade` |
| Penyebab | Versi di luar rentang teruji |
| Diagnostik | `pip list` dibanding tabel dok 05 |
| Solusi | `pip install -r requirements.txt` (rentang sudah dibatasi); jangan upgrade mayor tanpa test |
| Uji | pytest + `check_ai_agent.py --static` |

### 4. Port conflict
| | |
|---|---|
| Gejala | `OSError: [Errno 48] Address already in use` (Windows: `[WinError 10048]`) |
| Penyebab | Server MANTRA lain (mis. jendela `run_mantra.command`) masih jalan, atau proses lain memakai port itu |
| Diagnostik | `lsof -nP -iTCP:5001 -sTCP:LISTEN` lalu `ps -p <pid> -o pid,command` |
| Solusi | Tutup server lama; atau ubah `PORT` di `.env` (+ redirect URI Entra) |
| Selesai jika | Hanya satu PID mendengar di port itu |

### 5. Environment variable missing
| | |
|---|---|
| Gejala | `Belum diisi di .env: PBI_CLIENT_ID...`; tombol Ask AI hilang; tombol Microsoft memberi pesan "not configured" |
| Penyebab | Nilai kosong / salah nama / server belum restart; `.env` menang atas env terminal |
| File | `.env`, `config.py` |
| Diagnostik | `python scripts/check_setup.py` (tidak mencetak secret) |
| Solusi | Isi `.env`, restart |

### 6. Database schema error
| | |
|---|---|
| Gejala | `sqlite3.OperationalError: no such column/table`; `Database versi N lebih baru dari kode` |
| Penyebab | Migrasi lama diubah; kode lama + DB baru; DB dari laptop lain |
| File | `core/db.py` |
| Diagnostik | `python -c "import sqlite3; c=sqlite3.connect('instance/mantra.db'); print(c.execute('PRAGMA user_version').fetchone()); print([r[0] for r in c.execute('select name from sqlite_master where type=\'table\'')])"` |
| Solusi aman | Backup dulu (`manage_users.py backup`); pakai kode terbaru; pulihkan backup yang cocok (dok 25). **Jangan** hapus DB |
| Uji | `test_passwords_and_database.py` |

### 7. Login / session failure
| | |
|---|---|
| Gejala | "Wrong email or password" terus; langsung logout; "account is locked"; "Invalid security token" |
| Penyebab | Password salah / lockout 15 menit setelah 5 gagal / throttle IP 20 gagal; akun nonaktif; `session_version` berubah (reset password, ganti password di perangkat lain); `FLASK_SECRET_KEY` diganti; cookie diblokir; dibuka via `127.0.0.1` vs `localhost` (cookie terpisah) |
| File | `core/auth.py`, `core/accounts.py` |
| Diagnostik | Admin > Audit Log (`login_failed` + reason, `account_locked`, `login_throttled`); `python scripts/manage_users.py list` |
| Catatan | Akun dikunci **pada** kegagalan ke-5, tetapi kegagalan ke-5 itu masih menampilkan "Wrong email or password."; pesan "Too many failed attempts. Your account is locked for 15 minutes." baru tampil di percobaan ke-6 (selama kunci berlaku, password benar pun ditolak). Audit log mencatat `account_locked` tepat di kegagalan ke-5. Jadi user yang melihat "Wrong email or password" 5x lalu yakin password-nya benar sebenarnya sudah terkunci: cek `account_locked` di Audit Log |
| Solusi | Tunggu lock; Super Admin reset password; `manage_users.py reset-password --email ...` (Super Admin terakhir); buka lewat `http://localhost:5001` |
| Uji | `test_login_and_access.py` |

### 8. Authorization failure
| | |
|---|---|
| Gejala | 403 "Access denied" / kartu dashboard tidak tampil |
| Penyebab | User belum di-assign; dashboard dinonaktifkan; route admin untuk non-Super Admin |
| Diagnostik | Admin > Users > user (centang dashboard); Admin > Dashboards (status); Audit `access_denied` |
| Solusi | Beri akses di Admin (langsung berlaku) |
| Jangan | Menghapus `_guard` / decorator untuk "memperbaiki" |
| Uji | `test_direct_url_to_other_dashboard_is_403` |

### 9. Template not found
| | |
|---|---|
| Gejala | `jinja2.exceptions.TemplateNotFound: xxx.html` |
| Penyebab | Path salah; template dashboard tidak di `templates/<nama_blueprint>/`; blueprint tanpa `template_folder="templates"` |
| Diagnostik | `python -c "import sys; sys.path.insert(0,'.'); from mantra import create_app; a=create_app(); print(sorted(a.jinja_env.list_templates()))"` |
| Solusi | Sesuaikan path dengan daftar di atas |

### 10. CSS / JavaScript tidak dimuat
| | |
|---|---|
| Gejala | Halaman polos; console `Dash is not defined` / `Pani is not defined`; 404 di tab Network |
| Penyebab | `url_for` salah endpoint (`static` vs `<bp>.static`); template tidak extend base yang memuat file; cache browser |
| Diagnostik | DevTools Network & Console |
| Solusi | Perbaiki `url_for`; `Cmd+Shift+R`; panggil `{{ scripts() }}` (PANI) |
| Catatan | Static dashboard butuh login + akses (302/403 bila tidak) |

### 11. Dashboard tidak muncul di portal
| | |
|---|---|
| Penyebab | Lihat dok 14 §3 (folder `_`, tanpa `DASHBOARD`, `DASHBOARD_STRICT=0` menyembunyikan error, belum restart, user tanpa akses, nonaktif) |
| Diagnostik | Log startup: `Dashboard ... gagal dimuat dan disembunyikan`; `python -c "import sys; sys.path.insert(0,'.'); from mantra.core import registry; print([d.slug for d in registry.manifests()])"` |
| Solusi | Perbaiki manifest; restart; beri akses |

### 12. Power BI authentication failure
| | |
|---|---|
| Gejala | Halaman "Could not load data from Power BI (ref ...)"; log `Gagal ambil token: ...` |
| Penyebab | `PBI_CLIENT_SECRET` salah/kedaluwarsa (pakai **Value**, bukan Secret ID), tenant salah |
| Diagnostik | `python scripts/check_setup.py` |
| Solusi | Buat secret baru di Entra, update `.env`, restart |

### 13. Workspace / semantic model tidak ditemukan
| | |
|---|---|
| Gejala | Log `HTTP 401/403/404` pada `/groups/...` atau `/datasets/...` |
| Penyebab | SP bukan anggota workspace; belum di grup `sg-powerbi-api` (tunggu ~15 menit); ID salah; override `<PREFIX>_WORKSPACE_ID` salah |
| Diagnostik | `check_setup.py` (cek akses per dashboard) |
| Solusi | Workspace > Manage access > `mantra-powerbi` Contributor; perbaiki ID di `queries.py` / `.env` |

### 14. DAX query failure
| | |
|---|---|
| Gejala | Log `DAX error: ...` |
| Penyebab | Nama tabel/kolom berubah di model, sintaks, nilai filter tidak di-escape |
| Diagnostik | `python scripts/check_setup.py --dashboard <slug> --dax "EVALUATE ..."`; `EVALUATE INFO.VIEW.COLUMNS()` |
| Solusi | Perbaiki DAX di `queries.py`; selalu `dax_str()` untuk teks |
| Uji | Halaman terkait + `compare_pani_with_powerbi.py` (PANI) |

### 15. Invalid data type
| | |
|---|---|
| Gejala | `TypeError` / `ValueError` di `queries.py` atau template; angka tampil `-` |
| Penyebab | Kolom BLANK (`None`), tanggal string vs `date`, model berubah tipe |
| File | `queries.py` (`_num`, `to_date`, `_int`) |
| Solusi | Tangani `None` di fungsi konversi; jangan asumsi kolom selalu terisi |
| Uji | Test dengan stub (`_stub_pani` mengembalikan `None`) |

### 16. AI provider failure
| | |
|---|---|
| Gejala | "The AI service is busy..." (503) / "The AI service rejected the request (400/401/403)" (502) |
| Penyebab | Kuota/limit atau model penuh (setelah semua model cadangan dicoba); API key salah; nama model tidak tersedia |
| Diagnostik | Log `Gemini <model> tidak tersedia (...)`, `AI provider gagal`; `check_setup.py` (cek AI) |
| Solusi | Tunggu; ganti `GEMINI_MODEL` / `GEMINI_FALLBACK_MODELS`; API key khusus MANTRA |

### 17. Tool validation failure
| | |
|---|---|
| Gejala | AI menjawab "tidak dikenali" / meminta klarifikasi; panel menampilkan tool dipanggil berulang |
| Penyebab | `ToolArgError` dari `clean_args` / `resolve` (nilai tidak cocok dengan data) |
| Diagnostik | Response JSON `tools` (args yang dikirim AI); `check_ai_agent.py --static` (guards) |
| Solusi | Perbaiki `clean_args`/sinonim di `data_dictionary.md`; jangan melonggarkan `resolve` sampai ambigu |
| Uji | `test_invalid_tool_argument_returns_valid_options` + kasus `chat_cases.py` |

### 18. Test failure
| | |
|---|---|
| Gejala | `F` / `E` di pytest |
| Diagnostik | `python -m pytest -x -vv <file>::<test>`; baca assertion |
| Membedakan regresi | `git stash` → jalankan test → `git stash pop` (atau bandingkan baseline) |
| Solusi | Perbaiki kode, bukan melemahkan test — kecuali perilaku memang berubah dengan sengaja (catat alasannya) |

---

## Diagnosis "localhost tidak bisa dibuka" (urutan)

1. Terminal server: masih jalan? pesan `crashed`? → entri 1.
2. `lsof -nP -iTCP:5001 -sTCP:LISTEN` → ada yang mendengar? PID siapa? → entri 4.
3. URL `http://localhost:<PORT>` sesuai `.env`?
4. `curl -I http://localhost:5001/login` → 200?
5. Browser: cache/cookie, mode private.
