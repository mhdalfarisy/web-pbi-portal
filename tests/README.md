# tests/

Test otomatis (pytest) yang memastikan website tidak rusak setelah kode diubah. **Bukan bagian dari website**, dan
**tidak menyentuh data asli**: test memakai database sementara (bukan `instance/mantra.db`), akun dummy, dan tidak
memanggil Power BI / Gemini sungguhan.

```bash
pip install -r requirements-dev.txt   # sekali saja (pytest)
python -m pytest                      # semua test
python -m pytest tests/test_login_and_access.py      # satu file
python -m pytest -k forgot                            # test yang namanya mengandung "forgot"
```

| File | Yang diuji |
|---|---|
| `conftest.py` | Bukan test: persiapan bersama (app dengan database sementara, akun Super Admin / User A / User B, login, blokir panggilan ke layanan luar). Nama file ini wajib, dicari otomatis oleh pytest |
| `test_login_and_access.py` | Login benar/salah, user hanya melihat dashboard yang diizinkan, URL dashboard lain ditolak 403, halaman Admin hanya Super Admin, akun nonaktif / akses dicabut langsung berlaku, akun terkunci, throttle IP, CSRF, cookie palsu |
| `test_passwords_and_database.py` | Password disimpan sebagai hash, seed akun aman diulang, migrasi database tidak menghapus data & membuat backup, constraint tabel akses, log tanpa secret, `AUTH_DISABLED` hanya dari `.env` |
| `test_forgot_password.py` | Permintaan "Forgot password" sampai ke Super Admin, respons sama untuk email terdaftar / tidak, throttle, CSRF |
| `test_errors_and_security.py` | Tanggal ekstrem tidak membuat error 500, halaman "no data", detail error Power BI tidak tampil, error tool AI, batas pertanyaan AI, header keamanan, halaman 404, cache saat request bersamaan |
| `test_server_config.py` | Staging/production menolak start dengan setting development, label STAGING, `run.py` menolak non-dev, `.env` & database di luar folder kode, header proxy (IP asli & https) hanya dipakai kalau `TRUST_PROXY`, database mode WAL, `/healthz`, log request & query Power BI, `gunicorn.conf.py` 1 worker |

Nama file test harus diawali `test_` supaya ditemukan pytest (lihat `pytest.ini`).
