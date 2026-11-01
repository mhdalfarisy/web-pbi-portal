"""Halaman riwayat chat AI: AI Chats (milik sendiri, semua user) dan Chat Log (chat semua user).

Chat Log hanya untuk Super Admin dan user yang diberi izin di Admin > Users (cek di server, bukan sekadar menu
disembunyikan). Setiap pembukaan Chat Log dicatat di log aktivitas, setiap download CSV dicatat di audit log.
"""
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .core import accounts, activity, auth, registry
from .core.auth import login_required

bp = Blueprint("chats", __name__, url_prefix="/chats")

CSV_HEADER = ["Time", "User", "Dashboard", "Question", "Answer", "Data used", "Model", "Status", "Duration (ms)",
              "Conversation"]


def chat_viewer_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        user = auth.current_user()
        if not auth.can_view_chats(user):
            accounts.audit("access_denied", "page", request.path, actor=user, required=["chat_viewer"])
            return render_template("portal/denied.html", chat_log=True), 403
        return view(*args, **kwargs)
    return wrapped


def _dashboard_names():
    return {d.slug: d.title for d in registry.all_dashboards()}


def _tools_text(tools):
    return "; ".join(t.get("label") or t["name"] for t in tools)


@bp.get("")
@login_required
def mine():
    user = auth.current_user()
    slug = request.args.get("dashboard") or None
    return render_template("portal/chats.html", rows=activity.chats_of(user, slug), names=_dashboard_names(),
                           dashboard_filter=slug or "",
                           usage=activity.chat_usage(user["id"]), quota=activity.CHAT_QUOTA_BYTES)


@bp.post("/delete")
@login_required
def delete_mine():
    user = auth.current_user()
    count = activity.delete_chats(user)
    activity.log("chat_history_deleted", user=user, count=count)
    flash(f"Your AI chat history was deleted ({count} chats)." if count else "You have no saved AI chats.", "success")
    return redirect(url_for("chats.mine")), 303


@bp.get("/all")
@chat_viewer_required
def all_users():
    filters = activity.clean_filters(request.args)
    activity.log("chat_log_viewed", user=auth.current_user(),
                 **{k: v for k, v in filters.items() if v and k != "action"})
    return render_template("portal/chat_log.html", rows=activity.chat_entries(filters), total=activity.chat_count(filters),
                           names=_dashboard_names(), users=activity.chat_users(), filters=filters)


@bp.get("/all.csv")
@chat_viewer_required
def all_users_csv():
    filters = activity.clean_filters(request.args)
    rows = activity.chat_entries(filters, limit=activity.EXPORT_LIMIT)
    names = _dashboard_names()
    accounts.audit("chat_log_exported", actor=auth.current_user(), rows=len(rows),
                   filters={k: v for k, v in filters.items() if v and k != "action"})
    return activity.csv_response(
        "mantra-chat-log.csv", CSV_HEADER,
        ([r["created_at"], r["user_email"], names.get(r["slug"], r["slug"]), r["question"], r["answer"],
          _tools_text(r["tools"]), r["model"] or "", r["status"], r["duration_ms"], r["conversation"]] for r in rows))
