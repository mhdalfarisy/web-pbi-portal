"""Setting gunicorn untuk staging & production. Dibaca otomatis lewat: gunicorn -c gunicorn.conf.py wsgi:app"""
import os

from mantra.config import Config

# Hanya bisa dibuka dari mesin ini; HTTPS & domain ditangani reverse proxy (Caddy/nginx) di depannya
bind = os.environ.get("GUNICORN_BIND") or f"127.0.0.1:{Config.PORT}"
# HARUS 1 worker (proses). Batas query Power BI per menit, cache hasil query, throttle login, dan batas chat AI
# disimpan di memori proses: dengan 2 worker setiap worker punya hitungan sendiri dan kuota Power BI bisa terlewati.
# Banyak user dilayani lewat thread.
workers = 1
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS") or 16)
# Lebih lama dari batas satu request Power BI, supaya query yang lambat tidak diputus gunicorn lebih dulu
timeout = Config.PBI_TIMEOUT_SECONDS + 30
graceful_timeout = 30
# Log request gunicorn & error ke stderr (diteruskan systemd ke journal). Log aplikasi juga ke stderr.
accesslog = "-"
errorlog = "-"
