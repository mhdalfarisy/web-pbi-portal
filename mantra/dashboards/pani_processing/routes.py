"""Halaman dashboard PANI: Processing, Equipment, Mining, Production. Login & cek role dipasang otomatis oleh registry.

Filter tanggal dibaca dari URL (?start=YYYY-MM-DD&end=YYYY-MM-DD), jadi link halaman bisa dibagikan apa adanya.
"""
import time
from datetime import date, datetime

from flask import Blueprint, current_app, render_template, request

from . import queries

bp = Blueprint("pani_processing", __name__, url_prefix="/d/pani-processing",
               template_folder="templates", static_folder="static")


@bp.context_processor
def helpers():
    def fmt(value, decimals=0):
        return queries.fmt_num(value, decimals)

    def sgn(value, decimals=1, suffix="%"):
        return "-" if value is None else queries.fmt_num(value, decimals, sign=True) + suffix

    def tone(value, flat=0.05):
        return "flat" if value is None or abs(value) < flat else ("pos" if value > 0 else "neg")

    def arrow(value):
        return "" if value is None or abs(value) < 0.05 else ("↑" if value > 0 else "↓")

    def ring(achv):
        return "#16a34a" if achv is not None and achv >= 99.95 else "#f59e0b" if achv is not None and achv >= 90 else "#dc2626"

    def ring_mtd(achv):
        """Warna ring achievement Mining seperti report: >= 90% hijau, >= 70% oranye, di bawahnya merah."""
        return "#10b981" if achv is not None and achv >= 90 else "#f59e0b" if achv is not None and achv >= 70 else "#dc2626"

    def dlabel(value):
        return datetime.fromisoformat(str(value)[:10]).strftime("%d-%b-%y").upper() if value else "-"

    def dfull(value):
        """Tanggal seperti FORMAT(..., "dd MMM yyyy") di DAX, mis. 22 Oct 2026."""
        return datetime.fromisoformat(str(value)[:10]).strftime("%d %b %Y") if value else "-"

    return {"fmt": fmt, "sgn": sgn, "tone": tone, "arrow": arrow, "ring": ring, "ring_mtd": ring_mtd, "dlabel": dlabel,
            "dfull": dfull}


def _range(default_start, default_end):
    start = queries.parse_date(request.args.get("start"), default_start)
    end = queries.parse_date(request.args.get("end"), default_end)
    return (end, start) if start > end else (start, end)


def _page(template, data, fetched, bounds, **extra):
    company, logo = queries.header_company(data["company"])
    return render_template(f"pani_processing/{template}", d=data, bounds=bounds, header=queries.stamp_info(fetched),
                           refresh=queries.model_refresh(), payload={"company": company, "logo": logo, "data": data},
                           **extra)


def _error(exc):
    current_app.logger.exception("Gagal mengambil data dari Power BI")
    return render_template("dashboard/error.html", message=str(exc), header=queries.stamp_info(time.time())), 502


@bp.get("/")
def processing():
    try:
        b = queries.processing_bounds()
        # Default = seluruh rentang data -> mode YTD, sama seperti report tanpa filter
        start, end = _range(b["min"], b["max"])
        data, fetched = queries.processing(start, end)
        return _page("processing.html", data, fetched, b)
    except queries.DATA_ERRORS as exc:
        return _error(exc)


@bp.get("/equipment")
def equipment():
    try:
        b = queries.equipment_bounds()
        start, end = _range(b["max"], b["max"])
        status = request.args.get("status") if request.args.get("status") in ("active", "inactive") else ""
        data, fetched = queries.equipment(start, end, status)
        return _page("equipment.html", data, fetched, b)
    except queries.DATA_ERRORS as exc:
        return _error(exc)


@bp.get("/mining")
def mining():
    try:
        b = queries.mining_bounds()
        start, end = _range(date(b["last"].year, b["last"].month, 1), b["last"])
        data, fetched = queries.mining(start, end)
        return _page("mining.html", data, fetched, b)
    except queries.DATA_ERRORS as exc:
        return _error(exc)


@bp.get("/production")
def production():
    try:
        b = queries.production_bounds()
        start, end = _range(date(b["max"].year, b["max"].month, 1), b["max"])
        data, fetched = queries.production(start, end)
        try:  # PA% hari terakhir rentang ini untuk kartu insight (data equipment bisa belum ada)
            eq = queries.equipment(start, end)[0]
            pa, pa_day = eq["avg_pa"], eq["last_day"]
        except queries.DATA_ERRORS:
            pa = pa_day = None
        return _page("production.html", data, fetched, b, avg_pa=pa, pa_day=pa_day)
    except queries.DATA_ERRORS as exc:
        return _error(exc)
