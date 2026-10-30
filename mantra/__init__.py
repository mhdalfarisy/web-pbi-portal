"""Power BI Portal (nama project & package: MANTRA). Application factory: create_app()."""
import hmac
import secrets
from datetime import datetime

from flask import Flask, abort, jsonify, render_template, request, session

from . import admin, portal
from .config import ENV_OVERRIDDEN, Config
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
