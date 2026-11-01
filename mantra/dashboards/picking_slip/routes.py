"""Halaman dashboard Picking Slip: Summary dan Detail. Login & cek akses dipasang otomatis oleh registry."""
from flask import Blueprint, render_template

from ...core.errors import data_error_page
from . import queries

bp = Blueprint("picking_slip", __name__, url_prefix="/d/picking-slip", template_folder="templates", static_folder="static")


def _page(template, page, load):
    try:
        data, fetched = load()
    except queries.DATA_ERRORS as exc:
        return data_error_page(exc)
    return render_template(f"picking_slip/{template}", payload={**data, "page": page},
                           header=queries.stamp_info(fetched))


@bp.get("/")
def summary():
    return _page("summary.html", "summary", queries.summary)


@bp.get("/detail")
def detail():
    return _page("detail.html", "detail", queries.detail)
