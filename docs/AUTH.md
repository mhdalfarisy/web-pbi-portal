# Login, Role, dan Hak Akses Dashboard

Dokumen ini untuk developer dan admin yang memelihara MANTRA: cara login bekerja, siapa boleh membuka apa, skema
database, migrasi, backup & rollback, dan cara mengelola akun.

## Ringkasan

- Login utama: **email + password**. Password disimpan sebagai hash Werkzeug (scrypt), tidak pernah plaintext.
- Login Microsoft Entra **opsional** (kalau `ENTRA_*` diisi), hanya untuk email yang sudah terdaftar & aktif di MANTRA.
  App roles Entra tidak dipakai lagi; hak akses selalu dari database.
- Dua role: `super_admin` dan `user`.
- Hak akses per dashboard disimpan di tabel `user_dashboard_access`. Default **deny**: tanpa baris izin, ditolak.
- Semua cek dilakukan di server pada setiap request. Menyembunyikan menu hanya untuk kenyamanan, bukan pengaman.

| Akun awal | Role | Dashboard |
|---|---|---|
| `pbi_premium@merdeka.com` | `super_admin` | semua dashboard aktif |
| `pbi_pro_a@merdeka.com` | `user` | Material Readiness |
| `pbi_pro_b@merdeka.com` | `user` | PANI Processing |

## Arsitektur

```
Browser
  │  POST /login (email, password, CSRF)            ┌──────────── instance/mantra.db ────────────┐
  ▼                                                 │ users ─┐                                   │
Flask ── core/auth.py ── accounts.authenticate() ──►│        ├── user_dashboard_access ── dashboards│
  │      session = {uid, sv}  (cookie ditandatangani)│ audit_log                                  │
  │                                                 └────────────────────────────────────────────┘
  │  setiap request:
  │    current_user()  baca ulang users (aktif? session_version cocok?)  ── tidak: sesi dihapus
  │    require_password_change  password sementara? → hanya /account/password
  │    registry._guard (before_request semua route /d/<slug>/...: halaman, API, static)
  │        can_open(user, dashboard) = slug ∈ allowed_slugs(user)
  │          super_admin → semua dashboard is_active = 1
  │          user        → dashboard is_active = 1 yang ada di user_dashboard_access
  │        tidak boleh → 403 + audit "access_denied"
  │    role_required("super_admin") → /admin/*
  ▼
Route dashboard ── core/powerbi.py ── service principal mantra-powerbi ──► semantic model Power BI
```

Catatan Power BI: MANTRA **tidak** meng-embed report Power BI dan tidak membuat embed token. Server menjalankan DAX ke
semantic model memakai service principal; token & secret tidak pernah dikirim ke browser. Karena itu tabel
`dashboards` menyimpan `workspace_id` dan `dataset_id` (dari `mantra/dashboards/<nama>/queries.py`, bisa ditimpa
`.env`), sedangkan `report_id` dibiarkan kosong. Cek hak akses MANTRA dilakukan **sebelum** query apa pun dijalankan.
Login MANTRA tidak memberi akses Power BI ke user; yang punya akses ke workspace hanya service principal.

## Skema database

Migrasi ada di `mantra/core/db.py` (`MIGRATIONS`, versi di `PRAGMA user_version`).

```
users                                   dashboards
  id                 PK                   id            PK
  email              UNIQUE NOCASE        slug          UNIQUE   (material-readiness, pani-processing)
  name                                    name
  password_hash      werkzeug scrypt      workspace_id  dari kode/.env
  role               super_admin|user     dataset_id    dari kode/.env
  is_active          0|1                  report_id     NULL (tidak ada embed)
  must_change_password 0|1                is_active     0|1  (diatur Super Admin)
  session_version    naik saat password/   created_at, updated_at
                     status/role berubah
  failed_logins, locked_until           user_dashboard_access
  last_login_at, password_changed_at      id            PK
  created_at, updated_at                  user_id       FK users ON DELETE CASCADE
                                          dashboard_id  FK dashboards ON DELETE CASCADE
audit_log                                 granted_by    FK users ON DELETE SET NULL
  id, at, actor_id, actor_email,          granted_at
  action, target_type, target_id,         UNIQUE (user_id, dashboard_id), INDEX (dashboard_id)
  detail (JSON), ip
                                        favorites, history  (sudah ada sebelumnya, tidak diubah)
```

`favorites.user_id` dan `history.user_id` berisi id user sebagai teks (mis. `"2"`). Data lama (id Entra /
`dev-local`) tetap ada dan tidak dihapus.

Katalog `dashboards` disinkronkan setiap start: dashboard baru di kode otomatis masuk (`is_active = 1`), nama /
workspace / dataset mengikuti kode. `is_active` yang sudah diatur Super Admin tidak ditimpa.

## Aturan akses

| Aksi | Super Admin | User | Belum login |
|---|---|---|---|
| Home, Reports, Favorites, History, Settings | ✓ | ✓ (hanya dashboard yang diizinkan) | → /login |
| Halaman, API data, file static `/d/<slug>/...` | dashboard aktif | dashboard aktif + diizinkan, selain itu **403** | → /login, API **401** |
| `POST /d/<slug>/api/chat` (AI agent) | dashboard aktif | dashboard aktif + diizinkan, selain itu **403** | **401** |
| `/admin/*` | ✓ | **403** | → /login |
| Beri role `super_admin` | hanya lewat `scripts/manage_users.py set-role` (butuh akses server) | ✗ | ✗ |

Lainnya:
- Akun nonaktif: tidak bisa login, dan sesinya yang sedang berjalan langsung tidak berlaku.
- Cabut / beri akses, nonaktifkan dashboard: berlaku di **request berikutnya** (hak akses dibaca ulang tiap request).
- Reset password, ganti password, ubah status/role: `session_version` naik → semua sesi lain user itu logout.
- Password sementara (seed, user baru, reset): wajib diganti dulu; sebelum itu hanya `/account/password` dan
  logout yang bisa dibuka (API mendapat 403).
- Kebijakan password baru: minimal 10 karakter, huruf + angka, tidak mengandung nama email, beda dari yang lama.
- 5 kali salah password berturut-turut → akun dikunci 15 menit. 20 login gagal dari satu IP dalam 15 menit → 429.
- Pesan login gagal sama untuk email tidak terdaftar dan password salah (tidak membocorkan email yang valid).
- Super Admin tidak bisa menonaktifkan dirinya sendiri, dan Super Admin aktif terakhir tidak bisa dinonaktifkan /
  diturunkan.
- Semua POST butuh token CSRF. Session: cookie HttpOnly, SameSite=Lax, Secure kalau `SESSION_COOKIE_SECURE=1`,
  berlaku `SESSION_HOURS` jam.

## Route

| Method | Route | Akses | Fungsi |
|---|---|---|---|
| GET, POST | `/login` | publik | form login email + password |
| POST | `/logout` | login | keluar (juga dari Microsoft kalau login lewat Entra) |
| GET, POST | `/account/password` | login | ganti password (wajib untuk password sementara) |
| GET | `/auth/microsoft`, `/auth/callback` | publik | login Entra (opsional) |
| GET | `/`, `/reports`, `/favorites`, `/history`, `/settings` | login | portal |
| POST | `/api/favorites/<slug>` | login + akses dashboard | tandai favorit |
| GET | `/d/<slug>/...` | login + akses dashboard | halaman, API data, static dashboard |
| POST | `/d/<slug>/api/chat` | login + akses dashboard | AI agent |
| GET | `/admin/users` | super_admin | User Management |
| GET, POST | `/admin/users/new` | super_admin | buat user (role `user`), password sementara tampil sekali |
| GET | `/admin/users/<id>` | super_admin | detail user, Dashboard Access, aktivitas |
| POST | `/admin/users/<id>/access` | super_admin | simpan daftar dashboard yang diizinkan |
| POST | `/admin/users/<id>/status` | super_admin | aktifkan / nonaktifkan |
| POST | `/admin/users/<id>/reset-password` | super_admin | password sementara baru, tampil sekali |
| GET | `/admin/dashboards` | super_admin | katalog dashboard + status |
| POST | `/admin/dashboards/<id>/status` | super_admin | aktifkan / nonaktifkan dashboard |
| GET | `/admin/audit` | super_admin | audit log |

## Audit log

Tercatat di tabel `audit_log` (lihat **Admin > Audit Log**): `login_success`, `login_failed` (dengan alasan),
`account_locked`, `login_throttled`, `logout`, `password_changed`, `password_reset`, `user_created`,
`user_activated`, `user_deactivated`, `role_changed`, `access_granted`, `access_revoked`, `dashboard_activated`,
`dashboard_deactivated`, `access_denied`. Password, hash, token, dan secret tidak pernah dicatat (dicek oleh test).

## Mengelola akun dari server

```powershell
python scripts\manage_users.py list
python scripts\manage_users.py seed                    # akun awal; password dari $env:MANTRA_SEED_PASSWORD
python scripts\manage_users.py seed --generate         # password sementara acak & unik per akun
python scripts\manage_users.py create --email x@merdeka.com --dashboard material-readiness
python scripts\manage_users.py set-access --email x@merdeka.com --dashboard pani-processing
python scripts\manage_users.py reset-password --email x@merdeka.com
python scripts\manage_users.py set-active --email x@merdeka.com --inactive
python scripts\manage_users.py set-role --email x@merdeka.com --role super_admin
python scripts\manage_users.py backup
```

`seed` aman dijalankan ulang: akun yang sudah ada **tidak diubah** (password, role, dan hak aksesnya dibiarkan);
hak akses awal hanya diberikan saat akun dibuat. Password awal hanya sementara dan tidak ditulis ke file atau log.

## Migrasi, backup, rollback

Migrasi berjalan otomatis saat aplikasi start (`create_app` → `db.init_app`):

1. Baca `PRAGMA user_version`. Kalau sudah versi terbaru, tidak ada yang dilakukan.
2. Kalau database sudah berisi tabel, salin dulu ke `instance\backups\mantra-<waktu>-before-v<N>.db`
   (SQLite backup API, salinan konsisten).
3. Jalankan migrasi yang belum ada, masing-masing dalam satu transaksi. Gagal → rollback, aplikasi tidak start.

Migrasi hanya **menambah** tabel/index (`CREATE TABLE IF NOT EXISTS`); tabel `favorites` dan `history` tidak
diubah. Untuk perubahan skema berikutnya, tambahkan string SQL baru di **akhir** `MIGRATIONS`, jangan ubah yang lama.

Backup manual kapan saja: `python scripts\manage_users.py backup`.

Rollback (kembali ke kondisi sebelum fitur login ini):

```powershell
# 1. Hentikan server MANTRA (tutup jendela run_mantra.bat / Ctrl+C)
# 2. Simpan database sekarang, lalu pulihkan backup
Copy-Item instance\mantra.db instance\backups\mantra-sebelum-rollback.db
Copy-Item instance\backups\mantra-<waktu>-before-v2.db instance\mantra.db
# 3. Kembalikan kode ke commit sebelum fitur ini, lalu start server lagi
#    (kalau kode baru yang dijalankan, database itu akan dimigrasi ulang otomatis)
```

Kalau hanya kodenya yang dikembalikan tanpa memulihkan database, kode lama tetap jalan: tabel baru diabaikan.
Kalau kode baru dijalankan dengan database lama, migrasi otomatis memasang ulang tabel baru (dengan backup).

## Konfigurasi (.env)

| Variabel | Fungsi |
|---|---|
| `FLASK_SECRET_KEY` | wajib; menandatangani cookie session. Ganti = semua user logout |
| `AUTH_DISABLED` | `0` = login wajib. `1` = tanpa login, masuk sebagai Super Admin development (jangan di production) |
| `SESSION_HOURS` | lama sesi login (default 8 jam) |
| `SESSION_COOKIE_SECURE` | `1` kalau sudah HTTPS |
| `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET` | opsional, login Microsoft |
| `MANTRA_SEED_PASSWORD` | hanya saat menjalankan `seed`; jangan simpan di `.env` |

## Test

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

Test memakai database sementara (bukan `instance\mantra.db`), memaksa `AUTH_DISABLED=0`, dan memblokir panggilan ke
Power BI & AI. Halaman dashboard yang lolos cek akses tampil sebagai error data (HTTP 502) di test, yang dibedakan dari
penolakan akses (HTTP 403). Cakupan: login & pesan gagal, normalisasi email, daftar dashboard per role, 403 lewat URL
langsung (halaman, API, static, AI agent), halaman admin, akun nonaktif, cabut akses, dashboard nonaktif, manipulasi
request, CSRF, password sementara, reset password, lockout, throttle IP, cookie palsu, hash password, seed idempotent,
seed tidak menimpa akun, migrasi data lama + backup, constraint tabel, audit/log tanpa secret.
