"""Halaman dashboard Picking Slip. Login dan cek akses dipasang otomatis oleh core/registry.py (termasuk /frame)."""
from flask import Blueprint, Response, abort, render_template

from ...core.errors import data_error_page
from . import queries

bp = Blueprint("picking_slip", __name__, url_prefix="/d/picking-slip", template_folder="templates", static_folder="static")


def _page(page):
    return render_template("picking_slip/page.html", page=page)


@bp.get("/")
def summary():
    return _page("summary")


@bp.get("/detail")
def detail():
    return _page("detail")


@bp.get("/frame/<page>")
def frame(page):
    """Isi halaman (HTML measure + data) untuk iframe di page.html. Iframe di-sandbox tanpa allow-same-origin, jadi
    JS di dalamnya tidak bisa membaca cookie / halaman MANTRA."""
    if page not in queries.MEASURES:
        abort(404)
    try:
        html, _ = queries.page_html(page)
    except queries.DATA_ERRORS as exc:
        return data_error_page(exc)
    resp = Response(html, mimetype="text/html")
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"   # header bawaan MANTRA: DENY (tidak boleh di-iframe sama sekali)
    resp.headers["Cache-Control"] = "private, no-store"
    return resp
