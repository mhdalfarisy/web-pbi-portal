# Menjalankan MANTRA di server (staging & production)

Untuk tim infra. Laptop developer tetap memakai `python run.py` (APP_ENV=dev). Di server, aplikasi dijalankan
**gunicorn** di belakang reverse proxy (Caddy/nginx) yang menangani HTTPS. Staging dan production memakai kode yang
sama; bedanya hanya isi `.env` dan database masing-masing.

```
User (browser) ──HTTPS──► Caddy / nginx ──HTTP 127.0.0.1:5001──► gunicorn (1 proses, 16 thread) ──► wsgi:app
                          (sertifikat, domain)                       │
                                                                     ├── /var/lib/mantra/mantra.db  (akun, akses, audit)
                                                                     └── Power BI REST API, Microsoft Entra, Gemini
```

Paket yang di-deploy dibuat developer dengan `scripts/build_production.sh <folder>`: isinya `mantra/`, `wsgi.py`,
`gunicorn.conf.py`, `requirements.txt`, `scripts/manage_users.py`, `scripts/check_setup.py`, `.env.example` (server), dan
`VERSION`. Versi yang berakhiran `-belum-commit` belum boleh dirilis.

## 1. Kebutuhan

- Linux (gunicorn tidak jalan di Windows), Python 3.13, akses keluar HTTPS ke `login.microsoftonline.com`,
  `api.powerbi.com`, dan `generativelanguage.googleapis.com` (kalau AI agent aktif).
- Domain + sertifikat TLS per environment, mis. `mantra-staging.<domain>` dan `mantra.<domain>`.
- **Timezone server = zona waktu operasional** (mis. `Asia/Makassar`). Timestamp audit log & History memakai jam lokal
  server: `timedatectl set-timezone Asia/Makassar`.

## 2. Lokasi file

| Path | Isi | Diganti saat deploy? |
|---|---|---|
| `/opt/mantra/` | kode aplikasi + `.venv` | Ya |
| `/etc/mantra/mantra.env` | konfigurasi & secret (izin `600`, milik user service) | Tidak |
| `/var/lib/mantra/` | `mantra.db` (+ `mantra.db-wal`, `mantra.db-shm`) dan `backups/` | **Tidak pernah** |

Database dan `.env` sengaja di luar folder kode: folder kode boleh dihapus/diganti setiap rilis tanpa kehilangan akun.

## 3. Install

```bash
sudo useradd --system --home /var/lib/mantra --shell /usr/sbin/nologin mantra
sudo mkdir -p /opt/mantra /etc/mantra /var/lib/mantra
sudo chown mantra: /var/lib/mantra
# salin kode rilis ke /opt/mantra, lalu:
cd /opt/mantra
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 4. Konfigurasi `/etc/mantra/mantra.env`

Mulai dari `.env.example`. Nilai yang **wajib** berbeda dari laptop:

```ini
APP_ENV=staging                 # atau production
FLASK_SECRET_KEY=<python3 -c "import secrets; print(secrets.token_hex(32))">   # beda per environment
SESSION_COOKIE_SECURE=1
TRUST_PROXY=1                   # 1 reverse proxy di depan aplikasi
DASHBOARD_STRICT=0
MANTRA_INSTANCE_DIR=/var/lib/mantra
# PORT=5001                     # port lokal gunicorn (bind 127.0.0.1)
# GUNICORN_THREADS=16
ENTRA_TENANT_ID=... ENTRA_CLIENT_ID=... ENTRA_CLIENT_SECRET=...
PBI_CLIENT_ID=... PBI_CLIENT_SECRET=...
```

**Jangan** isi `AUTH_DISABLED` atau `FLASK_DEBUG=1`. Dengan `APP_ENV` staging/production aplikasi **menolak start**
kalau `AUTH_DISABLED=1`, `FLASK_DEBUG=1`, `SESSION_COOKIE_SECURE` bukan 1, atau `FLASK_SECRET_KEY` kurang dari 32
karakter. Setting yang kurang tepat lainnya (mis. `TRUST_PROXY=0`, database di dalam folder kode) muncul sebagai
`WARNING` di log saat start.

Di Microsoft Entra, app registration **MANTRA Portal** > Authentication > platform **Web**: tambahkan redirect URI
`https://<domain>/auth/callback` dan `https://<domain>/login` (tujuan setelah logout) untuk setiap environment, lalu
assign user/akun testing di Enterprise applications > MANTRA Portal > Users and groups.

## 5. Service systemd `/etc/systemd/system/mantra.service`

```ini
[Unit]
Description=MANTRA Power BI Portal
After=network-online.target

[Service]
User=mantra
WorkingDirectory=/opt/mantra
Environment=MANTRA_ENV_FILE=/etc/mantra/mantra.env
ExecStart=/opt/mantra/.venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now mantra
journalctl -u mantra -f          # log aplikasi + log request gunicorn
```

**Jangan menaikkan jumlah worker gunicorn.** `gunicorn.conf.py` sengaja `workers = 1`: batas query Power BI per menit,
cache, throttle login, dan batas chat AI ada di memori proses. Kapasitas ditambah lewat `GUNICORN_THREADS`, bukan worker,
dan hanya **satu** server/instance per environment (database SQLite lokal).

## 6. Reverse proxy

Caddy (`/etc/caddy/Caddyfile`), sertifikat otomatis:

```
mantra-staging.<domain> {
    reverse_proxy 127.0.0.1:5001 {
        transport http {
            read_timeout 180s
        }
    }
}
```

nginx: `proxy_pass http://127.0.0.1:5001;` dengan `proxy_set_header Host $host;`,
`X-Forwarded-For $proxy_add_x_forwarded_for;`, `X-Forwarded-Proto $scheme;`, dan **`proxy_read_timeout 180s;`**
(default nginx 60 detik lebih pendek dari query Power BI terlama, `PBI_TIMEOUT_SECONDS=120`).

## 7. Cek setelah deploy

```bash
curl -fsS https://<domain>/healthz            # {"status":"ok"}; 503 = database tidak bisa dibaca
cd /opt/mantra && sudo -u mantra MANTRA_ENV_FILE=/etc/mantra/mantra.env .venv/bin/python scripts/check_setup.py
```

Buka `https://<domain>/login`: di staging ada label **STAGING** di halaman login dan top bar.

## 8. Akun & backup

Semua perintah akun dijalankan di server dengan env file yang sama:

```bash
cd /opt/mantra
export MANTRA_ENV_FILE=/etc/mantra/mantra.env
sudo -E -u mantra .venv/bin/python scripts/manage_users.py list
sudo -E -u mantra .venv/bin/python scripts/manage_users.py backup     # -> /var/lib/mantra/backups/
```

Jadwalkan `manage_users.py backup` (cron/systemd timer, mis. harian) dan salin `/var/lib/mantra/backups/` ke luar server.
Jangan menyalin `mantra.db` langsung saat aplikasi jalan: pakai perintah backup (hasilnya satu file utuh).

**Restore:** hentikan service, simpan dulu kondisi sekarang, salin backup, **hapus `mantra.db-wal` dan `mantra.db-shm`**,
lalu start:

```bash
sudo systemctl stop mantra
sudo -E -u mantra .venv/bin/python scripts/manage_users.py backup
sudo -u mantra cp /var/lib/mantra/backups/mantra-<waktu>-<label>.db /var/lib/mantra/mantra.db
sudo rm -f /var/lib/mantra/mantra.db-wal /var/lib/mantra/mantra.db-shm
sudo systemctl start mantra
```

## 9. Update ke versi baru

1. `manage_users.py backup`.
2. Ganti isi `/opt/mantra` dengan rilis baru, `pip install -r requirements.txt`.
3. `sudo systemctl restart mantra`; migrasi database berjalan otomatis saat start (dengan backup `before-vN`).
4. Cek `/healthz` dan login. Rollback = pasang lagi rilis sebelumnya + restore backup `before-vN` (kode lama menolak
   database yang versinya lebih baru).

## 10. Log yang perlu dipantau

| Pola di log | Arti |
|---|---|
| `INFO mantra: GET /d/... 200 850ms user=...` | Satu request (durasi & user) |
| `INFO mantra.core.powerbi: Power BI MATERIAL_READINESS: 120 baris, 900 ms (antre 0 ms)` | Satu query Power BI |
| `WARNING mantra.core.powerbi: ... (antre 2300 ms)` | Batas `PBI_MAX_QUERIES_PER_MINUTE` tercapai: user mulai menunggu |
| `ERROR` / `Traceback` | Error server (user melihat halaman error dengan kode ref) |
| `WARNING mantra: APP_ENV=...` | Setting server kurang tepat (lihat langkah 4) |

`LOG_LEVEL=WARNING` mematikan log per request & per query; default di server `INFO`.
