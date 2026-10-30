"""Power BI Portal (nama project & package: MANTRA). Application factory: create_app()."""
import hmac
import logging
import secrets
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, g, jsonify, render_template, request, session
from flask.logging import default_handler
from werkzeug.middleware.proxy_fix import ProxyFix

from . import admin, portal
from .config import APP_ENVS, BASE_DIR, ENV_OVERRIDDEN, Config
from .core import accounts, auth, db, registry
from .core.chat import providers
from .core.chat import routes as chat_routes


def create_app(test_config=None):
    app = Flask(__name__, instance_path=str(Config.INSTANCE_DIR))
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)  # dipakai tests/ (database sementara, AUTH_DISABLED=0)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("FLASK_SECRET_KEY belum diisi di .env")

    # Satu format untuk log aplikasi, log request, dan log query Power BI (semua logger "mantra.*"). Di server,
    # gunicorn meneruskan log ini ke journal / file log.
    default_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    app.logger.setLevel(app.config["LOG_LEVEL"])
    _check_server_config(app)

    if app.config["TRUST_PROXY"]:
        # IP user, https, dan domain asli dikirim proxy lewat X-Forwarded-*. Tanpa ini semua user terlihat datang dari
        # IP proxy (throttle login mengenai semua orang) dan url_for(_external=True) menghasilkan http:// (SSO gagal).
        hops = app.config["TRUST_PROXY"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops, x_port=hops)

    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(portal.bp)
    app.register_blueprint(chat_routes.bp)
    app.register_blueprint(admin.bp)
    registry.init_app(app)  # semua folder di mantra/dashboards/

    # Katalog dashboard di database (dipakai untuk hak akses) mengikuti dashboard yang terdaftar di kode
    conn = db.connect(app.config["APP_DB"])
    try:
        accounts.sync_dashboards(conn, registry.all_dashboards())
    finally:
        conn.close()

    if ENV_OVERRIDDEN and not app.config.get("TESTING"):

        app.logger.warning("Variabel environment terminal ditimpa oleh .env MANTRA: %s. Biasanya terbawa dari .env "
                           "project lain di VS Code (setting python.terminal.useEnvFile).", ", ".join(ENV_OVERRIDDEN))
    if app.config["AUTH_DISABLED"]:
        app.logger.warning("AUTH_DISABLED=1: portal bisa dibuka tanpa login sebagai Super Admin. "
                           "Jangan dipakai di production.")

    app.jinja_env.globals["now_str"] = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Label "STAGING" di top bar & halaman login, supaya tester tidak tertukar dengan production
    app.jinja_env.globals["app_env"] = app.config["APP_ENV"]

    @app.before_request
    def start_timer():
        g.started = time.perf_counter()

    @app.before_request
    def csrf_protect():
        if request.method == "POST":
            expected = session.get("_csrf", "")
            # Form biasa kirim lewat field _csrf, request fetch/JSON lewat header X-CSRF-Token
            given = request.form.get("_csrf") or request.headers.get("X-CSRF-Token", "")
            # Dibandingkan sebagai bytes: compare_digest menolak str non-ASCII dengan TypeError (jadi HTTP 500)
            if not expected or not hmac.compare_digest(expected.encode(), given.encode("utf-8", "replace")):
                abort(400, "Invalid security token. Please reload the page and try again.")

    @app.after_request
    def security_headers(resp):
        # Halaman portal tidak boleh di-iframe situs lain (clickjacking), tipe file tidak ditebak browser,
        # dan URL halaman (bisa berisi filter) tidak dikirim ke situs luar seperti host logo.
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    @app.after_request
    def log_request(resp):
        # Satu baris per request (tanpa file static & health check): dipakai mencari halaman lambat & error di server.
        # User diambil dari cache request (g.user) saja, supaya log tidak menambah query database.
        endpoint = request.endpoint or ""
        if app.logger.isEnabledFor(logging.INFO) and endpoint != "healthz" and not endpoint.endswith("static"):
            user = g.get("user")
            ms = (time.perf_counter() - g.get("started", time.perf_counter())) * 1000
            app.logger.info("%s %s %s %.0fms user=%s ip=%s", request.method, request.path, resp.status_code, ms,
                            user["email"] if user else "-", request.remote_addr)
        return resp

    @app.get("/healthz")
    def healthz():
        """Untuk monitoring & cek setelah deploy: 200 kalau aplikasi hidup dan database bisa dibaca. Tanpa login."""
        try:
            db.get_db().execute("SELECT 1 FROM users LIMIT 1").fetchall()
        except sqlite3.Error:
            app.logger.exception("Health check gagal: database tidak bisa dibaca")
            return jsonify(status="error"), 503
        return jsonify(status="ok")

    @app.context_processor
    def inject_globals():
        def csrf_token():
            if "_csrf" not in session:
                session["_csrf"] = secrets.token_urlsafe(32)
            return session["_csrf"]

        user = auth.current_user()
        dashboard = registry.current()
        is_admin = auth.is_admin(user)
        return {
            "csrf_token": csrf_token,
            "current_user": user,
            "user_is_admin": is_admin,
            # Jumlah permintaan "Forgot password" yang menunggu, untuk badge menu Admin > Users
            "pending_resets": accounts.pending_reset_count() if is_admin and user["db_id"] is not None else 0,
            "dashboard": dashboard,
            "chat_enabled": bool(dashboard and dashboard.chat and providers.configured()),
            # Status bintang favorit di top bar halaman report
            "report_favorite": bool(user and dashboard and dashboard.slug in db.favorites(user["id"])),
        }

    def _error(code, message):
        if "/api/" in request.path or request.is_json:
            return jsonify(error=message), code
        return render_template("portal/error.html", code=code, message=message), code

    @app.errorhandler(400)
    def bad_request(exc):
        return _error(400, exc.description if isinstance(exc.description, str) else "Bad request.")

    @app.errorhandler(404)
    def not_found(exc):
        return _error(404, "Page not found.")

    @app.errorhandler(500)
    def server_error(exc):

        return _error(500, "Something went wrong on the server. Please try again; if it keeps happening, "
                           "contact the Super Admin.")

    return app


def _check_server_config(app):
    """Di staging & production: tolak start kalau setting development masih aktif, dan beri peringatan untuk setting
    yang kurang tepat. Di dev tidak ada pengecekan. Mengembalikan daftar peringatan."""
    cfg = app.config
    env = cfg["APP_ENV"]
    if env not in APP_ENVS:
        raise RuntimeError(f"APP_ENV={env!r} tidak dikenal. Pilih salah satu: {', '.join(APP_ENVS)}")
    if env == "dev":
        return []

    errors = []
    if cfg["AUTH_DISABLED"]:
        errors.append("AUTH_DISABLED=1: portal terbuka tanpa login. Hapus dari .env")
    if cfg["DEBUG"]:
        errors.append("FLASK_DEBUG=1: debugger bisa menjalankan kode di server. Isi 0")
    if not cfg["SESSION_COOKIE_SECURE"]:
        errors.append("SESSION_COOKIE_SECURE harus 1 (portal dibuka lewat HTTPS)")
    if len(cfg["SECRET_KEY"]) < 32:
        errors.append("FLASK_SECRET_KEY terlalu pendek. Buat baru: python -c \"import secrets; print(secrets.token_hex(32))\"")
    if errors:
        raise RuntimeError(f"Setting tidak aman untuk APP_ENV={env}:\n  - " + "\n  - ".join(errors))

    warnings = []
    if not (cfg["ENTRA_TENANT_ID"] and cfg["ENTRA_CLIENT_ID"] and cfg["ENTRA_CLIENT_SECRET"]):
        warnings.append("ENTRA_* belum diisi: login Microsoft (SSO) tidak tersedia, user hanya bisa login dengan password")
    if not cfg["TRUST_PROXY"]:
        warnings.append("TRUST_PROXY=0: kalau portal di belakang Caddy/nginx, IP user & https tidak terbaca (isi 1)")
    if cfg["DASHBOARD_STRICT"]:
        warnings.append("DASHBOARD_STRICT=1: satu dashboard yang error membuat portal gagal start (isi 0)")
    if Path(cfg["INSTANCE_DIR"]).resolve().is_relative_to(BASE_DIR):
        warnings.append(f"Database ada di dalam folder kode ({cfg['INSTANCE_DIR']}) dan bisa ikut terhapus saat deploy. "
                        "Isi MANTRA_INSTANCE_DIR, mis. /var/lib/mantra")
    for warning in warnings:
        app.logger.warning("APP_ENV=%s: %s", env, warning)
    return warnings
