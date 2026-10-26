"""Halaman dashboard __TITLE__. Login dan cek role dipasang otomatis oleh core/registry.py."""
from flask import Blueprint, render_template

from ...core.errors import data_error_page
from . import queries

bp = Blueprint("__NAME__", __name__, url_prefix="/d/__SLUG__", template_folder="templates", static_folder="static")


@bp.get("/")
def overview():
    try:
        rows, fetched = queries.tables()
    except queries.DATA_ERRORS as exc:
        return data_error_page(exc)
    return render_template("__NAME__/overview.html", tables=[r["table"] for r in rows],
                           header=queries.stamp_info(fetched))
