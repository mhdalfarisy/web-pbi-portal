"""Konfigurasi portal dari .env. Nilai khusus dashboard (workspace & dataset) ada di folder dashboard masing-masing."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# .env MANTRA SELALU menang atas variabel yang sudah ada di environment. Terminal VS Code bisa membawa .env project
# lain (setting python.terminal.useEnvFile), mis. kredensial service principal lain atau AUTH_DISABLED=1, dan tanpa
# override nilai itu diam-diam dipakai MANTRA. Nama variabel yang tertimpa dicatat untuk peringatan saat start.
# Di server, .env boleh disimpan di luar folder kode (folder kode diganti setiap deploy): MANTRA_ENV_FILE=/etc/mantra/.env
# MANTRA_ENV_FILE harus diset di environment proses (mis. systemd), bukan di dalam .env itu sendiri.
ENV_PATH = Path(os.environ.get("MANTRA_ENV_FILE") or BASE_DIR / ".env")
_ENV_FILE = dotenv_values(ENV_PATH)
ENV_OVERRIDDEN = sorted(k for k, v in _ENV_FILE.items() if k in os.environ and os.environ[k] != (v or ""))
load_dotenv(ENV_PATH, override=True)

APP_ENVS = ("dev", "staging", "production")


def _flag(name):
    return os.environ.get(name, "").strip() == "1"


def _env_file_flag(name):
    """Flag yang HANYA dibaca dari file .env (tidak ada di .env = mati). Dipakai untuk AUTH_DISABLED, supaya login
    tidak bisa dimatikan lewat variabel environment, bahkan kalau AUTH_DISABLED tidak ditulis di .env."""
    return (_ENV_FILE.get(name) or "").strip() == "1"


def _list(value):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


class Config:
    # dev = laptop developer, staging = server uji, production = server live. Selain dev, create_app menolak start
    # kalau setting berbahaya masih aktif (lihat mantra/__init__.py: _check_server_config).
    APP_ENV = (os.environ.get("APP_ENV") or "dev").strip().lower()
    # Jumlah reverse proxy (Caddy/nginx) di depan aplikasi. 1 = IP user, https, dan domain dibaca dari header
    # X-Forwarded-* yang dikirim proxy. 0 = tidak ada proxy (laptop). Jangan isi >0 kalau tidak ada proxy: header itu
    # bisa dipalsukan user.
    TRUST_PROXY = int(os.environ.get("TRUST_PROXY") or 0)
    # Level log: DEBUG, INFO, WARNING. Kosong = INFO di server (ada log tiap request & query Power BI), WARNING di dev.
    LOG_LEVEL = (os.environ.get("LOG_LEVEL") or ("WARNING" if APP_ENV == "dev" else "INFO")).strip().upper()
    # Port lokal. Redirect URI di Entra harus ikut: http://localhost:<PORT>/auth/callback
    PORT = int(os.environ.get("PORT") or 5001)
    # 1 = Werkzeug debugger + auto reload. Debugger bisa menjalankan kode di server, jadi default mati.
    DEBUG = _flag("FLASK_DEBUG")
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_HTTPONLY = True
    # Wajib 1 kalau portal dibuka lewat HTTPS; 0 hanya untuk http://localhost
    SESSION_COOKIE_SECURE = _flag("SESSION_COOKIE_SECURE")
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.environ.get("SESSION_HOURS") or 8))

    # Login user: email + password (tabel users di mantra.db, lihat core/accounts.py).
    # Opsional: Microsoft Entra ID (app registration "MANTRA Portal") untuk email yang sudah terdaftar di tabel users.
    ENTRA_TENANT_ID = os.environ.get("ENTRA_TENANT_ID")
    ENTRA_CLIENT_ID = os.environ.get("ENTRA_CLIENT_ID")
    ENTRA_CLIENT_SECRET = os.environ.get("ENTRA_CLIENT_SECRET")

    # 1 = tanpa login, otomatis masuk sebagai Super Admin development (hanya untuk development lokal)
    AUTH_DISABLED = _env_file_flag("AUTH_DISABLED")

    # Data: Power BI service principal, app registration "mantra-powerbi" (tenant sama dengan login)
    PBI_TENANT_ID = os.environ.get("PBI_TENANT_ID") or ENTRA_TENANT_ID
    PBI_CLIENT_ID = os.environ.get("PBI_CLIENT_ID")
    PBI_CLIENT_SECRET = os.environ.get("PBI_CLIENT_SECRET")
    # Kuota Power BI dihitung per service principal, jadi batas ini berlaku untuk SEMUA dashboard sekaligus
    PBI_MAX_QUERIES_PER_MINUTE = int(os.environ.get("PBI_MAX_QUERIES_PER_MINUTE") or 100)
    # Batas waktu satu request ke Power BI. Lebih lama dari ini, request user dihentikan dengan pesan gagal.
    PBI_TIMEOUT_SECONDS = int(os.environ.get("PBI_TIMEOUT_SECONDS") or 120)
    CACHE_SECONDS = int(os.environ.get("CACHE_MINUTES") or 10) * 60

    # AI agent. Provider lain (mis. OpenAI) cukup ditambahkan di core/chat/providers.py
    AI_PROVIDER = (os.environ.get("AI_PROVIDER") or "gemini").strip().lower()
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash"
    GEMINI_FALLBACK_MODELS = _list(os.environ.get("GEMINI_FALLBACK_MODELS") or "gemini-3.1-flash-lite,gemini-flash-latest")
    # Batas pertanyaan AI agent per user per menit (kuota & biaya AI dipakai bersama)
    CHAT_MAX_PER_MINUTE = int(os.environ.get("CHAT_MAX_PER_MINUTE") or 10)

    # 1 = dashboard yang gagal dimuat membuat aplikasi gagal start (development).
    # 0 = dashboard itu disembunyikan dan dicatat di log, dashboard lain tetap jalan (production).
    DASHBOARD_STRICT = os.environ.get("DASHBOARD_STRICT", "1").strip() != "0"

    # Database & backup. Di server isi di luar folder kode (mis. /var/lib/mantra) supaya tidak terhapus saat deploy.
    INSTANCE_DIR = Path(os.environ.get("MANTRA_INSTANCE_DIR") or BASE_DIR / "instance")
    APP_DB = INSTANCE_DIR / "mantra.db"
