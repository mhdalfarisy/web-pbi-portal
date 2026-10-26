"""Halaman Summary & Detail Material Readiness. Login dan cek role dipasang otomatis oleh core/registry.py."""
from flask import Blueprint, Response, jsonify, render_template, request, url_for

from ...core.errors import data_error_json, data_error_page, data_error_text
from . import queries

bp = Blueprint("material_readiness", __name__, url_prefix="/d/material-readiness",
               template_folder="templates", static_folder="static")


@bp.get("/")
def summary():
    try:
        cube, fetched = queries.summary_cube()
        logo = queries.company_logos()
    except queries.DATA_ERRORS as exc:
        return data_error_page(exc)
    now = queries.now_wib()
    payload = {"data": cube, "logo": logo, "curY": now.year, "curM": now.month,
               "detailUrl": url_for("material_readiness.detail")}
    return render_template("material_readiness/summary.html", payload=payload, header=queries.stamp_info(fetched))


@bp.get("/detail")
def detail():
    try:
        logo = queries.company_logos()
    except queries.DATA_ERRORS as exc:
        return data_error_page(exc)
    payload = {
        "api": url_for("material_readiness.api_detail"),
        "exportUrl": url_for("material_readiness.api_detail_export"),
        "logo": logo,
    }
    return render_template("material_readiness/detail.html", payload=payload, header={"date": "-", "time": ""})


@bp.get("/api/detail")
def api_detail():
    try:
        return jsonify(queries.detail(queries.parse_filters(request.args)))
    except queries.DATA_ERRORS as exc:
        return data_error_json(exc)


@bp.get("/api/detail/export")
def api_detail_export():
    try:
        text = queries.export_tsv(queries.parse_filters(request.args))
    except queries.DATA_ERRORS as exc:
        return data_error_text(exc)
    return Response(text, mimetype="text/tab-separated-values; charset=utf-8")
