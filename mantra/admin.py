"""Halaman Super Admin: User Management, Dashboard Access, katalog dashboard, audit log.

Semua route di sini hanya untuk role super_admin (cek di server, bukan sekadar menu disembunyikan) dan semua POST
dilindungi CSRF (lihat create_app). Role super_admin TIDAK bisa diberikan dari sini; pakai scripts/manage_users.py.
Password sementara (user baru / reset) hanya ditampilkan sekali di respons, tidak disimpan di session atau log.
"""
from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, url_for

from .core import accounts, registry
from .core.auth import admin_required, current_user

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _dashboard_ids(form):
    try:
        return [int(v) for v in form.getlist("dashboard")]
    except ValueError:
        raise accounts.AccountError("Pilihan dashboard tidak valid.") from None


def _show_temp_password(user_id, password, created):
    """Halaman yang menampilkan password sementara sekali saja; jangan disimpan di cache browser."""
    resp = make_response(render_template("admin/temp_password.html", user=accounts.get_user(user_id),
                                         password=password, created=created))
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _user_or_404(user_id):
    user = accounts.get_user(user_id)
    if user is None:
        abort(404)
    return user


@bp.get("/users")
@admin_required
def users():
    return render_template("admin/users.html", rows=accounts.list_users(), roles=accounts.ROLES)


@bp.route("/users/new", methods=["GET", "POST"])
@admin_required
def new_user():
    dashboards = accounts.list_dashboards()
    form = {"email": "", "name": "", "dashboard": []}
    if request.method == "POST":
        form = {"email": request.form.get("email", ""), "name": request.form.get("name", ""),
                "dashboard": request.form.getlist("dashboard")}
        actor = current_user()
        try:
            ids = _dashboard_ids(request.form)
            password = accounts.temporary_password()
            user_id = accounts.create_user(form["email"], form["name"], password, role="user", actor=actor)
            accounts.set_access(user_id, ids, actor=actor)
        except accounts.AccountError as exc:
            flash(str(exc), "error")
            return render_template("admin/user_new.html", dashboards=dashboards, form=form), 400
        return _show_temp_password(user_id, password, created=True)
    return render_template("admin/user_new.html", dashboards=dashboards, form=form)


@bp.get("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    user = _user_or_404(user_id)
    return render_template("admin/user_detail.html", user=user, roles=accounts.ROLES,
                           dashboards=accounts.list_dashboards(), granted=accounts.granted_ids(user_id),
                           history=accounts.describe_audit(accounts.audit_for_user(user_id)))


@bp.post("/users/<int:user_id>/access")
@admin_required
def user_access(user_id):
    _user_or_404(user_id)
    try:
        granted, revoked = accounts.set_access(user_id, _dashboard_ids(request.form), actor=current_user())
    except accounts.AccountError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin.user_detail", user_id=user_id)), 303
    if granted or revoked:
        parts = ([f"diberi akses: {', '.join(granted)}"] if granted else []) + \
                ([f"dicabut: {', '.join(revoked)}"] if revoked else [])
        flash("Hak akses disimpan (" + "; ".join(parts) + ").", "success")
    else:
        flash("Tidak ada perubahan hak akses.", "info")
    return redirect(url_for("admin.user_detail", user_id=user_id)), 303


@bp.post("/users/<int:user_id>/status")
@admin_required
def user_status(user_id):
    user = _user_or_404(user_id)
    actor = current_user()
    active = request.form.get("active") == "1"
    if not active and actor["db_id"] == user["id"]:
        flash("Anda tidak bisa menonaktifkan akun Anda sendiri.", "error")
    else:
        try:
            accounts.set_active(user_id, active, actor=actor)
            flash(f"Akun {user['email']} {'diaktifkan' if active else 'dinonaktifkan'}.", "success")
        except accounts.AccountError as exc:
            flash(str(exc), "error")
    return redirect(url_for("admin.user_detail", user_id=user_id)), 303


@bp.post("/users/<int:user_id>/reset-password")
@admin_required
def user_reset_password(user_id):
    user = _user_or_404(user_id)
    actor = current_user()
    if actor["db_id"] == user["id"]:
        flash("Ganti password Anda sendiri lewat menu Ganti Password.", "error")
        return redirect(url_for("admin.user_detail", user_id=user_id)), 303
    password = accounts.temporary_password()
    accounts.set_password(user_id, password, must_change=True, actor=actor, action="password_reset")
    return _show_temp_password(user_id, password, created=False)


@bp.get("/dashboards")
@admin_required
def dashboards():
    registered = {d.slug: d for d in registry.all_dashboards()}
    return render_template("admin/dashboards.html", rows=accounts.list_dashboards(), registered=registered)


@bp.post("/dashboards/<int:dashboard_id>/status")
@admin_required
def dashboard_status(dashboard_id):
    try:
        accounts.set_dashboard_active(dashboard_id, request.form.get("active") == "1", actor=current_user())
        flash("Status dashboard disimpan.", "success")
    except accounts.AccountError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin.dashboards")), 303


@bp.get("/audit")
@admin_required
def audit():
    action = request.args.get("action") or None
    return render_template("admin/audit.html",
                           rows=accounts.describe_audit(accounts.audit_entries(limit=300, action=action)),
                           actions=accounts.audit_actions(), action=action)
