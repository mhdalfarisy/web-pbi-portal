"""Konfigurasi portal dari .env. Nilai khusus dashboard (workspace & dataset) ada di folder dashboard masing-masing."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
_ENV_FILE = dotenv_values(BASE_DIR / ".env")


def _flag(name):
    return os.environ.get(name, "").strip() == "1"


def _env_file_flag(name):
    """Flag yang HANYA dibaca dari file .env, bukan dari variabel environment terminal.
    Dipakai untuk AUTH_DISABLED supaya `$env:AUTH_DISABLED=1` yang tertinggal di terminal tidak mematikan login."""
    return (_ENV_FILE.get(name) or "").strip() == "1"


def _list(value):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


class Config:
    # Port lokal. Redirect URI di Entra harus ikut: http://localhost:<PORT>/auth/callback
    PORT = int(os.environ.get("PORT") or 5001)
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = _flag("SESSION_COOKIE_SECURE")
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.environ.get("SESSION_HOURS") or 8))

    # Login user: email + password (tabel users di mantra.db, lihat core/accounts.py).
    # Opsional: Microsoft Entra ID (app registration "MANTRA Portal") untuk email yang sudah terdaftar di tabel users.
    ENTRA_TENANT_ID = os.environ.get("ENTRA_TENANT_ID")
    ENTRA_CLIENT_ID = os.environ.get("ENTRA_CLIENT_ID")
    ENTRA_CLIENT_SECRET = os.environ.get("ENTRA_CLIENT_SECRET")

    # 1 = tanpa login, otomatis masuk sebagai Super Admin development (hanya untuk development lokal)
    AUTH_DISABLED = _env_file_flag("AUTH_DISABLED")
    # Nilai AUTH_DISABLED di environment terminal (diabaikan); dipakai untuk peringatan saat start
    AUTH_DISABLED_ENV_IGNORED = os.environ.get("AUTH_DISABLED", "").strip() not in ("", (_ENV_FILE.get("AUTH_DISABLED") or "").strip())

    # Data: Power BI service principal, app registration "mantra-powerbi" (tenant sama dengan login)
    PBI_TENANT_ID = os.environ.get("PBI_TENANT_ID") or ENTRA_TENANT_ID
    PBI_CLIENT_ID = os.environ.get("PBI_CLIENT_ID")
    PBI_CLIENT_SECRET = os.environ.get("PBI_CLIENT_SECRET")
    # Kuota Power BI dihitung per service principal, jadi batas ini berlaku untuk SEMUA dashboard sekaligus
    PBI_MAX_QUERIES_PER_MINUTE = int(os.environ.get("PBI_MAX_QUERIES_PER_MINUTE") or 100)
    CACHE_SECONDS = int(os.environ.get("CACHE_MINUTES") or 10) * 60

    # AI agent. Provider lain (mis. OpenAI) cukup ditambahkan di core/chat/providers.py
    AI_PROVIDER = (os.environ.get("AI_PROVIDER") or "gemini").strip().lower()
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash"
    GEMINI_FALLBACK_MODELS = _list(os.environ.get("GEMINI_FALLBACK_MODELS") or "gemini-3.1-flash-lite,gemini-flash-latest")

    # 1 = dashboard yang gagal dimuat membuat aplikasi gagal start (development).
    # 0 = dashboard itu disembunyikan dan dicatat di log, dashboard lain tetap jalan (production).
    DASHBOARD_STRICT = os.environ.get("DASHBOARD_STRICT", "1").strip() != "0"

    INSTANCE_DIR = BASE_DIR / "instance"
    APP_DB = INSTANCE_DIR / "mantra.db"
