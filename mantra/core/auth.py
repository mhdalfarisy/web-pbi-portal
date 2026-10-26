"""Login & hak akses portal.

Login:
- Email + password (akun di tabel users, password disimpan sebagai hash Werkzeug). Akun baru / password yang di-reset
  admin wajib diganti saat login pertama.
- Lupa password: user mengisi email di /forgot-password, permintaannya muncul di Admin > Users, lalu Super Admin
  me-reset password dan memberikan password sementara (tidak ada pengiriman email dari portal).
- Microsoft Entra ID (opsional, kalau ENTRA_* diisi): hanya untuk email yang SUDAH terdaftar & aktif di tabel users.
  App roles Entra tidak dipakai lagi untuk hak akses.

Hak akses (sumbernya database, lihat core/accounts.py):
- Session hanya menyimpan id user + session_version. Setiap request data user dibaca ulang dari database, jadi
  menonaktifkan akun, reset password, dan mencabut akses dashboard langsung berlaku di request berikutnya.
- Super Admin: semua dashboard aktif. User: hanya dashboard yang diberi akses. Selain itu ditolak (default deny).
"""
import threading
import time
import warnings
from collections import defaultdict, deque
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode

import msal
from flask import (Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash

from ..config import Config
from . import accounts

bp = Blueprint("auth", __name__)

# MSAL menyarankan response_mode=form_post. Tidak dipakai: callback form_post adalah POST lintas situs, dan cookie
# session (SameSite=Lax) tidak ikut terkirim, sehingga login gagal. Alur query + PKCE + state tetap aman.
warnings.filterwarnings("ignore", message="response_mode='form_post' is recommended")

_msal_app = None
_msal_lock = threading.Lock()

# Batas per alamat IP (di memori, berlaku per proses). Kunci per akun ada di accounts.py.
IP_MAX_FAILURES = 20        # login gagal
IP_MAX_RESET_REQUESTS = 5   # permintaan "Forgot password"
IP_WINDOW_SECONDS = 15 * 60


class _IpThrottle:
    """Hitung kejadian per IP dalam jendela waktu bergeser; blocked() = sudah mencapai batas."""

    def __init__(self, limit, window=IP_WINDOW_SECONDS):
        self.limit, self.window = limit, window
        self.hits = defaultdict(deque)
        self.lock = threading.Lock()

    def blocked(self, ip):
        now = time.monotonic()
        with self.lock:
            hits = self.hits[ip]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            return len(hits) >= self.limit

    def hit(self, ip):
        with self.lock:
            self.hits[ip].append(time.monotonic())

    def clear(self):
        with self.lock:
            self.hits.clear()


_login_failures = _IpThrottle(IP_MAX_FAILURES)
_reset_requests = _IpThrottle(IP_MAX_RESET_REQUESTS)

# Endpoint yang tetap boleh dibuka selama user belum mengganti password sementara
_PASSWORD_CHANGE_ALLOWED = {"auth.change_password", "auth.logout", "auth.login", "static"}


def entra_configured():
    return bool(Config.ENTRA_TENANT_ID and Config.ENTRA_CLIENT_ID and Config.ENTRA_CLIENT_SECRET)


def _entra():
    global _msal_app
    with _msal_lock:
        if _msal_app is None:
            _msal_app = msal.ConfidentialClientApplication(
                Config.ENTRA_CLIENT_ID,
                authority=f"https://login.microsoftonline.com/{Config.ENTRA_TENANT_ID}",
                client_credential=Config.ENTRA_CLIENT_SECRET,
            )
        return _msal_app


def auth_disabled():
    return bool(current_app.config.get("AUTH_DISABLED"))


def _dev_user():
    return {"id": "dev-local", "db_id": None, "name": "Developer (tanpa login)", "email": "dev@localhost",
            "role": "super_admin", "role_label": accounts.ROLES["super_admin"], "must_change_password": False}


def _session_user(row):
    return {"id": str(row["id"]), "db_id": row["id"], "name": row["name"] or row["email"].split("@")[0],
            "email": row["email"], "role": row["role"], "role_label": accounts.ROLES[row["role"]],
            "must_change_password": bool(row["must_change_password"]) and not session.get("sso")}


def current_user():
    """User yang login (dict), atau None. Dibaca ulang dari database sekali per request."""
    if "user" in g:
        return g.user
    user = None
    if auth_disabled():
        user = _dev_user()
    elif session.get("uid") is not None:
        row = accounts.get_user(session["uid"])
        if row is not None and row["is_active"] and row["session_version"] == session.get("sv"):
            user = _session_user(row)
        else:
            session.clear()  # akun dinonaktifkan / password diganti / role berubah: sesi lama tidak berlaku
    g.user = user
    return user


def is_admin(user):
    return bool(user) and user["role"] == "super_admin"


def allowed_slugs(user):
    """Slug dashboard yang boleh dibuka user (cache per request)."""
    if not user:
        return set()
    if "allowed_slugs" not in g:
        g.allowed_slugs = accounts.allowed_slugs(user["db_id"], is_admin(user))
    return g.allowed_slugs


def can_open(user, dashboard):
    return bool(user) and dashboard.slug in allowed_slugs(user)


def _safe_next(target):
    """Hanya izinkan redirect ke path di aplikasi ini (bukan ke situs lain)."""
    return target if target and target.startswith("/") and not target.startswith("//") else url_for("portal.home")


def _login_url():
    """URL halaman login; `next` hanya ditambahkan kalau user membuka halaman selain Home."""
    target = request.full_path.rstrip("?")
    return url_for("auth.login", next=target) if target != "/" else url_for("auth.login")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(_login_url())
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    """Batasi route ke role tertentu, mis. @role_required("super_admin")."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            user = current_user()
            if user["role"] not in roles:
                accounts.audit("access_denied", "page", request.path, actor=user, required=list(roles))
                if "/api/" in request.path:
                    return jsonify(error="You do not have access."), 403
                return render_template("portal/denied.html", admin_only=True), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator


admin_required = role_required("super_admin")


@bp.before_app_request
def require_password_change():
    """User dengan password sementara hanya boleh membuka halaman ganti password (dan logout)."""
    endpoint = request.endpoint or ""
    if endpoint in _PASSWORD_CHANGE_ALLOWED or endpoint.endswith(".static"):
        return None
    user = current_user()
    if user and user["must_change_password"]:
        if "/api/" in request.path:
            return jsonify(error="Please change your temporary password first."), 403
        return redirect(url_for("auth.change_password", next=request.full_path.rstrip("?")))
    return None


def _start_session(row, sso=False):
    session.clear()  # cegah session fixation
    session.permanent = True
    session["uid"] = row["id"]
    session["sv"] = row["session_version"]
    if sso:
        session["sso"] = True
    g.pop("user", None)
    g.pop("allowed_slugs", None)


def reset_ip_throttle():
    _login_failures.clear()
    _reset_requests.clear()


def _login_background():
    """Foto latar halaman login hanya dipakai kalau file-nya ada (opsional, lihat README)."""
    if (Path(current_app.static_folder) / "img" / "login-bg.jpg").is_file():
        return url_for("static", filename="img/login-bg.jpg")
    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    if auth_disabled() or current_user():
        return redirect(_safe_next(request.values.get("next")))
    next_url = request.values.get("next", "")
    email = ""
    status = 200
    if request.method == "POST":
        email = accounts.normalize_email(request.form.get("email"))
        password = request.form.get("password") or ""
        ip = request.remote_addr or "-"
        if _login_failures.blocked(ip):
            accounts.audit("login_throttled", "ip", ip, email=email)
            flash("Too many login attempts from this device. Please try again in 15 minutes.", "error")
            status = 429
        else:
            row, reason = accounts.authenticate(email, password)
            if row is not None:
                _start_session(row)
                if row["must_change_password"]:
                    return redirect(url_for("auth.change_password", next=next_url))
                return redirect(_safe_next(next_url))
            _login_failures.hit(ip)
            status = 401
            flash({"locked": f"Too many failed attempts. Your account is locked for {accounts.LOCK_MINUTES} minutes.",
                   "inactive": "Your account is inactive. Please contact the Power BI Portal Super Admin."}
                  .get(reason, "Wrong email or password."), "error")
    return render_template("portal/login.html", entra=entra_configured(), next=next_url, email=email,
                           login_bg=_login_background()), status


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Minta reset password ke Super Admin. Respons selalu sama, terdaftar atau tidak (tidak membocorkan email)."""
    if auth_disabled() or current_user():
        return redirect(url_for("portal.home"))
    email, sent, status = "", False, 200
    if request.method == "POST":
        email = accounts.normalize_email(request.form.get("email"))
        ip = request.remote_addr or "-"
        if _reset_requests.blocked(ip):
            flash("Too many requests from this device. Please try again in 15 minutes.", "error")
            status = 429
        elif not accounts.EMAIL_RE.match(email) or len(email) > 254:
            flash("Please enter a valid email address.", "error")
            status = 400
        else:
            _reset_requests.hit(ip)
            accounts.request_password_reset(email)
            sent = True
    return render_template("portal/forgot_password.html", email=email, sent=sent,
                           login_bg=_login_background()), status


@bp.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    user = current_user()
    if user["db_id"] is None:  # user development (AUTH_DISABLED=1) tidak punya password
        flash("Development mode (AUTH_DISABLED=1) does not use passwords.", "warn")
        return redirect(url_for("portal.settings"))
    next_url = request.values.get("next", "")
    if request.method == "POST":
        row = accounts.get_user(user["db_id"])
        current = request.form.get("current_password") or ""
        new = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""
        problem = None
        if not row["password_hash"] or not check_password_hash(row["password_hash"], current):
            problem = "Your current password is incorrect."
        elif new != confirm:
            problem = "The new passwords do not match."
        elif new == current:
            problem = "The new password must be different from the current one."
        else:
            problem = accounts.password_problem(new, row["email"])
        if problem:
            flash(problem, "error")
            return render_template("portal/change_password.html", forced=user["must_change_password"],
                                   next=next_url), 400
        version = accounts.set_password(row["id"], new, actor=user)
        session["sv"] = version  # sesi ini tetap berlaku; sesi lain user ini otomatis logout
        g.pop("user", None)
        flash("Your password has been changed.", "success")
        return redirect(_safe_next(next_url))
    return render_template("portal/change_password.html", forced=user["must_change_password"], next=next_url)


@bp.get("/auth/microsoft")
def microsoft():
    target = _safe_next(request.args.get("next"))
    if auth_disabled():
        return redirect(target)
    if not entra_configured():
        flash("Microsoft sign-in is not configured: fill in ENTRA_TENANT_ID, ENTRA_CLIENT_ID and "
              "ENTRA_CLIENT_SECRET in .env.", "error")
        return redirect(url_for("auth.login"))
    flow = _entra().initiate_auth_code_flow(
        scopes=[], redirect_uri=url_for("auth.callback", _external=True), prompt="select_account")
    session["auth_flow"] = flow
    session["auth_next"] = target
    return redirect(flow["auth_uri"])


@bp.get("/auth/callback")
def callback():
    flow = session.pop("auth_flow", None)
    target = _safe_next(session.pop("auth_next", None))
    if not flow:
        flash("Your sign-in session expired. Please try again.", "error")
        return redirect(url_for("auth.login"))
    try:
        result = _entra().acquire_token_by_auth_code_flow(flow, request.args.to_dict())
    except ValueError:  # state tidak cocok, mis. tombol back setelah login
        flash("Invalid sign-in session. Please try again.", "error")
        return redirect(url_for("auth.login"))
    if "error" in result:
        description = result.get("error_description") or result["error"]
        current_app.logger.warning("Login Entra gagal: %s", description.splitlines()[0])
        if "AADSTS50105" in description:  # user belum di-assign ke Enterprise App
            flash("Your account has not been given access to Power BI Portal. Please contact the administrator.",
                  "error")
        else:
            flash(f"Sign-in failed: {description.splitlines()[0]}", "error")
        return redirect(url_for("auth.login"))

    claims = result.get("id_token_claims") or {}
    email = accounts.normalize_email(claims.get("preferred_username") or claims.get("email"))
    row = accounts.get_user_by_email(email) if email else None
    if row is None or not row["is_active"]:
        accounts.audit("login_failed", "user", row["id"] if row else None, email=email, method="entra",
                       reason="inactive" if row else "not_registered")
        flash("This Microsoft account is not registered or is inactive in Power BI Portal. "
              "Please contact the Super Admin.", "error")
        return redirect(url_for("auth.login"))
    accounts.record_login(row, method="entra")
    _start_session(row, sso=True)
    return redirect(target)


@bp.post("/logout")
def logout():
    user = current_user()
    sso = session.get("sso")
    if user and user["db_id"] is not None:
        accounts.audit("logout", "user", user["db_id"], actor=user)
    session.clear()
    if not sso or auth_disabled() or not entra_configured():
        return redirect(url_for("auth.login"))
    # Keluar juga dari sesi Microsoft, supaya login berikutnya bisa memilih akun lain
    query = urlencode({"post_logout_redirect_uri": url_for("auth.login", _external=True)})
    return redirect(f"https://login.microsoftonline.com/{Config.ENTRA_TENANT_ID}/oauth2/v2.0/logout?{query}")
