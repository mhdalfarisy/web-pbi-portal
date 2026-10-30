"""Kesiapan server staging & production: APP_ENV, proxy, lokasi data, WAL, health check, log, gunicorn."""
import logging
import os
import runpy
import sqlite3
import subprocess
import sys

import pytest

from conftest import EMAILS, ROOT

from mantra import _check_server_config, create_app
from mantra.config import Config
from mantra.core import db, powerbi
from mantra.dashboards.material_readiness import queries as material

# Setting staging yang aman; setiap test mengubah satu nilai saja
SAFE_STAGING = {"TESTING": True, "APP_ENV": "staging", "SESSION_COOKIE_SECURE": True, "SECRET_KEY": "s" * 64,
                "TRUST_PROXY": 1, "DASHBOARD_STRICT": False, "ENTRA_TENANT_ID": "t", "ENTRA_CLIENT_ID": "c",
                "ENTRA_CLIENT_SECRET": "x"}


def _app(tmp_path, **overrides):
    return create_app({**SAFE_STAGING, "INSTANCE_DIR": tmp_path, "APP_DB": tmp_path / "mantra.db", **overrides})


# ---------------------------------------------------------------- APP_ENV & pengaman start

@pytest.mark.parametrize("setting, value, message", [
    ("AUTH_DISABLED", True, "AUTH_DISABLED"),
    ("DEBUG", True, "FLASK_DEBUG"),
    ("SESSION_COOKIE_SECURE", False, "SESSION_COOKIE_SECURE"),
    ("SECRET_KEY", "pendek", "FLASK_SECRET_KEY"),
])
def test_staging_refuses_to_start_with_dev_settings(tmp_path, setting, value, message):
    with pytest.raises(RuntimeError, match=message):
        _app(tmp_path, **{setting: value})
    assert not (tmp_path / "mantra.db").exists()  # ditolak sebelum database disentuh


def test_unknown_app_env_is_rejected(tmp_path):
    with pytest.raises(RuntimeError, match="APP_ENV='prod'"):
        _app(tmp_path, APP_ENV="prod")


def test_staging_warns_about_weak_settings(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="mantra"):
        _app(tmp_path, TRUST_PROXY=0, DASHBOARD_STRICT=True, ENTRA_CLIENT_SECRET="")
    text = caplog.text
    assert "TRUST_PROXY=0" in text and "DASHBOARD_STRICT=1" in text and "ENTRA_*" in text


def test_staging_label_only_on_staging(tmp_path, client):
    staging = _app(tmp_path).test_client().get("/login").get_data(as_text=True)
    assert "[STAGING]" in staging and "env-badge" in staging
    dev = client.get("/login").get_data(as_text=True)
    assert "STAGING" not in dev and "env-badge" not in dev


def test_run_py_refuses_non_dev(tmp_path):
    """run.py (server development) tidak boleh dipakai di server; staging/production lewat gunicorn."""
    env_file = tmp_path / ".env"
    env_file.write_text(f"APP_ENV=staging\nFLASK_SECRET_KEY={'k' * 64}\nSESSION_COOKIE_SECURE=1\nDASHBOARD_STRICT=0\n"
                        f"MANTRA_INSTANCE_DIR={tmp_path / 'data'}\n")
    result = subprocess.run([sys.executable, "run.py"], cwd=ROOT, capture_output=True, text=True, timeout=60,
                            env={**os.environ, "MANTRA_ENV_FILE": str(env_file)})
    assert result.returncode != 0 and "gunicorn -c gunicorn.conf.py wsgi:app" in result.stderr, result.stderr


# ---------------------------------------------------------------- lokasi .env & database

def test_env_file_and_instance_dir_can_live_outside_code(tmp_path):
    env_file = tmp_path / "mantra.env"
    env_file.write_text(f"APP_ENV=staging\nFLASK_SECRET_KEY=x\nMANTRA_INSTANCE_DIR={tmp_path / 'data'}\n")
    code = ("from mantra.config import Config, ENV_PATH; "
            "print(ENV_PATH, Config.APP_ENV, Config.APP_DB, Config.LOG_LEVEL, sep='|')")
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60,
                            env={**os.environ, "MANTRA_ENV_FILE": str(env_file)})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().split("|") == [str(env_file), "staging", str(tmp_path / "data" / "mantra.db"), "INFO"]


def test_database_inside_code_folder_is_warned(tmp_path):
    app = _app(tmp_path)
    app.config["INSTANCE_DIR"] = ROOT / "instance"  # hanya dicek, database asli tidak dibuka
    assert any("MANTRA_INSTANCE_DIR" in w for w in _check_server_config(app))


# ---------------------------------------------------------------- reverse proxy

def test_proxy_headers_used_only_when_trusted(tmp_path):
    headers = {"X-Forwarded-For": "203.0.113.9", "X-Forwarded-Proto": "https", "X-Forwarded-Host": "portal.example.com"}
    for trust, expected in ((1, "203.0.113.9 https://portal.example.com/login"), (0, "127.0.0.1 http://localhost/login")):
        app = _app(tmp_path / str(trust), TRUST_PROXY=trust)

        @app.get("/_probe")
        def probe():
            from flask import request, url_for
            return f"{request.remote_addr} {url_for('auth.login', _external=True)}"

        assert app.test_client().get("/_probe", headers=headers).get_data(as_text=True) == expected


def test_login_throttle_counts_real_client_ip_behind_proxy(tmp_path):
    """Di belakang proxy, salah password dari satu IP tidak boleh memblokir login user lain (IP lain)."""
    from mantra.core import auth
    app = _app(tmp_path)
    c = app.test_client()
    with c.session_transaction() as s:
        s["_csrf"] = "t"
    for _ in range(auth.IP_MAX_FAILURES):
        c.post("/login", data={"email": "x@merdeka.com", "password": "salah", "_csrf": "t"},
               headers={"X-Forwarded-For": "203.0.113.9"})
    blocked = c.post("/login", data={"email": "x@merdeka.com", "password": "salah", "_csrf": "t"},
                     headers={"X-Forwarded-For": "203.0.113.9"})
    other = c.post("/login", data={"email": "x@merdeka.com", "password": "salah", "_csrf": "t"},
                   headers={"X-Forwarded-For": "198.51.100.7"})
    auth.reset_ip_throttle()
    assert blocked.status_code == 429 and other.status_code == 401


# ---------------------------------------------------------------- database

def test_database_uses_wal(app):
    conn = sqlite3.connect(app.config["APP_DB"])
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        conn.close()


def test_healthz_without_login(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.get_json() == {"status": "ok"}


def test_healthz_reports_broken_database(client, monkeypatch):
    def broken():
        raise sqlite3.OperationalError("disk I/O error")
    monkeypatch.setattr(db, "get_db", broken)
    r = client.get("/healthz")
    assert r.status_code == 503 and r.get_json() == {"status": "error"}


# ---------------------------------------------------------------- log

def test_request_log_has_user_status_and_duration(login_as, caplog):
    c = login_as("a")
    with caplog.at_level(logging.INFO, logger="mantra"):
        c.get("/")
        c.get("/static/css/shell.css")
        c.get("/healthz")
    lines = [r.getMessage() for r in caplog.records if r.name == "mantra"]
    assert any(m.startswith("GET / 200 ") and f"user={EMAILS['a']}" in m for m in lines), lines
    assert not any("/static/" in m or "/healthz" in m for m in lines), lines


def test_powerbi_query_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(powerbi.PowerBI, "request",
                        lambda self, *a, **k: {"results": [{"tables": [{"rows": [{"[x]": 1}, {"[x]": 2}]}]}]})
    with caplog.at_level(logging.INFO, logger="mantra"):
        assert powerbi.query(material.DATASET, "EVALUATE {1}") == [{"x": 1}, {"x": 2}]
    assert any(r.name == "mantra.core.powerbi" and "MATERIAL_READINESS: 2 baris" in r.getMessage()
               for r in caplog.records), caplog.text


# ---------------------------------------------------------------- gunicorn

def test_gunicorn_config_uses_one_worker():
    """Limiter Power BI, cache, dan throttle ada di memori proses: harus 1 worker, banyak thread."""
    conf = runpy.run_path(str(ROOT / "gunicorn.conf.py"))
    assert conf["workers"] == 1 and conf["worker_class"] == "gthread" and conf["threads"] >= 8
    assert conf["timeout"] > Config.PBI_TIMEOUT_SECONDS
    assert conf["bind"].startswith("127.0.0.1:")


def test_wsgi_module_exposes_app(tmp_path):
    code = "import wsgi; assert 'auth.login' in wsgi.app.view_functions; print('ok')"
    env = {**os.environ, "MANTRA_INSTANCE_DIR": str(tmp_path)}
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60, env=env)
    assert result.returncode == 0 and "ok" in result.stdout, result.stderr
