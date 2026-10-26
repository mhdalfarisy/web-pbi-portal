"""Halaman portal: Home, Reports, Favorites, History, Settings."""
from flask import Blueprint, current_app, jsonify, render_template, request

from .config import Config
from .core import auth, db, registry
from .core.auth import login_required
from .core.chat import providers

bp = Blueprint("portal", __name__)

QUICK_ACCESS = 5


def _cards(user, dashboards):
    favs = set(db.favorites(user["id"]))
    return [{"d": d, "fav": d.slug in favs} for d in dashboards]


@bp.get("/")
@login_required
def home():
    user = auth.current_user()
    visible = registry.visible_for(user)
    favs = db.favorites(user["id"])
    # Quick Access: favorit dulu (urutan saat ditambahkan), lalu dashboard siap pakai lainnya
    order = {slug: i for i, slug in enumerate(favs)}
    quick = sorted(visible, key=lambda d: (d.slug not in order, order.get(d.slug, 0), not d.ready, d.order))
    return render_template("portal/home.html", cards=_cards(user, quick[:QUICK_ACCESS]), total=len(visible))


@bp.get("/reports")
@login_required
def reports():
    user = auth.current_user()
    visible = registry.visible_for(user)
    return render_template("portal/reports.html", cards=_cards(user, visible),
                           categories=sorted({d.category for d in visible}),
                           q=request.args.get("q", ""), category=request.args.get("category", ""))


@bp.get("/favorites")
@login_required
def favorites():
    user = auth.current_user()
    visible = {d.slug: d for d in registry.visible_for(user)}
    dashboards = [visible[s] for s in db.favorites(user["id"]) if s in visible]
    return render_template("portal/favorites.html", cards=_cards(user, dashboards))


@bp.get("/history")
@login_required
def history():
    user = auth.current_user()
    visible = {d.slug: d for d in registry.visible_for(user)}
    rows = [{"d": visible[r["slug"]], "title": r["title"], "url": r["url"], "visited_at": r["visited_at"]}
            for r in db.history(user["id"]) if r["slug"] in visible]
    return render_template("portal/history.html", rows=rows)


@bp.get("/settings")
@login_required
def settings():
    user = auth.current_user()
    status = None
    if auth.is_admin(user):
        status = {
            "entra": auth.entra_configured(),
            "auth_disabled": current_app.config["AUTH_DISABLED"],
            "powerbi": bool(Config.PBI_TENANT_ID and Config.PBI_CLIENT_ID and Config.PBI_CLIENT_SECRET),
            "ai": providers.configured(),
            "ai_provider": Config.AI_PROVIDER,
            "dashboards": registry.all_dashboards(),
        }
    return render_template("portal/settings.html", dashboards=registry.visible_for(user), status=status)


@bp.post("/api/favorites/<slug>")
@login_required
def toggle_favorite(slug):
    user = auth.current_user()
    dashboard = registry.get(slug)
    if dashboard is None or not auth.can_open(user, dashboard):
        return jsonify(error="Dashboard tidak ditemukan."), 404
    return jsonify(favorite=db.toggle_favorite(user["id"], slug))
