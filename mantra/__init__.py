"""MANTRA: Multi-Agent Network for Tracking & Reporting Analytics."""
import hmac
import secrets

from flask import Flask, abort, render_template, request, session

from . import portal
from .config import Config
from .core import auth, db, registry
from .core.chat import providers
from .core.chat import routes as chat_routes


def create_app():
    app = Flask(__name__, instance_path=str(Config.INSTANCE_DIR))
    app.config.from_object(Config)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("FLASK_SECRET_KEY belum diisi di .env")

    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(portal.bp)
    app.register_blueprint(chat_routes.bp)
    registry.init_app(app)  # semua folder di mantra/dashboards/

    if Config.AUTH_DISABLED:
        app.logger.warning("AUTH_DISABLED=1: portal bisa dibuka tanpa login. Jangan dipakai di production.")

    @app.before_request
    def csrf_protect():
        if request.method == "POST":
            expected = session.get("_csrf", "")
            # Form biasa kirim lewat field _csrf, request fetch/JSON lewat header X-CSRF-Token
            given = request.form.get("_csrf") or request.headers.get("X-CSRF-Token", "")
            if not expected or not hmac.compare_digest(expected, given):
                abort(400, "CSRF token tidak valid, silakan muat ulang halaman.")

    @app.context_processor
    def inject_globals():
        def csrf_token():
            if "_csrf" not in session:
                session["_csrf"] = secrets.token_urlsafe(32)
            return session["_csrf"]

        user = auth.current_user()
        dashboard = registry.current()
        return {
            "csrf_token": csrf_token,
            "current_user": user,
            "user_is_admin": auth.is_admin(user),
            "dashboard": dashboard,
            "chat_enabled": bool(dashboard and dashboard.chat and providers.configured()),
        }

    @app.errorhandler(404)
    def not_found(exc):
        return render_template("portal/error.html", code=404, message="Halaman tidak ditemukan."), 404

    return app
