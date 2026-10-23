"""Halaman dashboard __TITLE__. Login dan cek role dipasang otomatis oleh core/registry.py."""
import time

from flask import Blueprint, current_app, render_template

from . import queries

bp = Blueprint("__NAME__", __name__, url_prefix="/d/__SLUG__", template_folder="templates", static_folder="static")


@bp.get("/")
def overview():
    try:
        rows, fetched = queries.tables()
    except queries.DATA_ERRORS as exc:
        current_app.logger.exception("Gagal mengambil data dari Power BI")
        return render_template("dashboard/error.html", message=str(exc),
                               header=queries.stamp_info(time.time())), 502
    return render_template("__NAME__/overview.html", tables=[r["table"] for r in rows],
                           header=queries.stamp_info(fetched))
