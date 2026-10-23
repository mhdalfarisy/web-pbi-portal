"""Login Microsoft Entra ID (app registration "MANTRA Portal") dan hak akses dari app roles.

- Siapa yang boleh login diatur di Entra: Enterprise applications > MANTRA Portal > Assignment required = Yes,
  lalu Users and groups. User yang tidak di-assign sudah ditolak Microsoft sebelum sampai ke MANTRA.
- Dashboard mana yang boleh dibuka diatur lewat app roles (Portal.Admin, Report.<Nama>), yang ikut terkirim di token.
  Perubahan role berlaku setelah user login ulang.
"""
import threading
import warnings
from functools import wraps
from urllib.parse import urlencode

import msal
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from ..config import Config

bp = Blueprint("auth", __name__)

# MSAL menyarankan response_mode=form_post. Tidak dipakai: callback form_post adalah POST lintas situs, dan cookie
# session (SameSite=Lax) tidak ikut terkirim, sehingga login gagal. Alur query + PKCE + state tetap aman.
warnings.filterwarnings("ignore", message="response_mode='form_post' is recommended")

_msal_app = None
_msal_lock = threading.Lock()


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


def user_from_claims(claims):
    """ID token Entra -> data user yang disimpan di session (tanpa token, supaya cookie tetap kecil)."""
    email = (claims.get("preferred_username") or claims.get("email") or "").lower()
    return {
        "id": claims.get("oid") or claims.get("sub"),
        "name": claims.get("name") or email,
        "email": email,
        "roles": sorted(set(claims.get("roles") or [])),
    }


def _dev_user():
    return {"id": "dev-local", "name": "Developer (tanpa login)", "email": "dev@localhost",
            "roles": sorted(set(Config.DEV_ROLES))}


def current_user():
    if Config.AUTH_DISABLED and not session.get("user"):
        session["user"] = _dev_user()
    return session.get("user")


def is_admin(user):
    return bool(user) and Config.ADMIN_ROLE in user["roles"]


def can_open(user, dashboard):
    return bool(user) and (is_admin(user) or dashboard.role in user["roles"])


def _safe_next(target):
    """Hanya izinkan redirect ke path di aplikasi ini (bukan ke situs lain)."""
    return target if target and target.startswith("/") and not target.startswith("//") else url_for("portal.home")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not is_admin(current_user()):
            return render_template("portal/denied.html", admin_only=True), 403
        return view(*args, **kwargs)
    return wrapped


@bp.get("/login")
def login():
    if session.get("user") or Config.AUTH_DISABLED:
        return redirect(_safe_next(request.args.get("next")))
    return render_template("portal/login.html", configured=entra_configured(), next=request.args.get("next", ""))


@bp.get("/auth/microsoft")
def microsoft():
    target = _safe_next(request.args.get("next"))
    if Config.AUTH_DISABLED:
        return redirect(target)
    if not entra_configured():
        flash("Login Microsoft belum dikonfigurasi: isi ENTRA_TENANT_ID, ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET di .env.",
              "error")
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
        flash("Sesi login kedaluwarsa, silakan coba lagi.", "error")
        return redirect(url_for("auth.login"))
    try:
        result = _entra().acquire_token_by_auth_code_flow(flow, request.args.to_dict())
    except ValueError:  # state tidak cocok, mis. tombol back setelah login
        flash("Sesi login tidak valid, silakan coba lagi.", "error")
        return redirect(url_for("auth.login"))
    if "error" in result:
        description = result.get("error_description") or result["error"]
        current_app.logger.warning("Login Entra gagal: %s", description)
        if "AADSTS50105" in description:  # user belum di-assign ke Enterprise App
            flash("Akun Anda belum diberi akses ke MANTRA. Hubungi admin MANTRA.", "error")
        else:
            flash(f"Login gagal: {description.splitlines()[0]}", "error")
        return redirect(url_for("auth.login"))

    session.clear()
    session.permanent = True
    session["user"] = user_from_claims(result.get("id_token_claims") or {})
    return redirect(target)


@bp.post("/logout")
def logout():
    session.clear()
    if Config.AUTH_DISABLED or not entra_configured():
        return redirect(url_for("auth.login"))
    # Keluar juga dari sesi Microsoft, supaya login berikutnya bisa memilih akun lain
    query = urlencode({"post_logout_redirect_uri": url_for("auth.login", _external=True)})
    return redirect(f"https://login.microsoftonline.com/{Config.ENTRA_TENANT_ID}/oauth2/v2.0/logout?{query}")
