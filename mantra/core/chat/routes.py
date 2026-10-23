"""Endpoint agent setiap dashboard: POST /d/<slug>/api/chat."""
from flask import Blueprint, current_app, jsonify, request

from .. import auth, registry
from ..powerbi import DATA_ERRORS
from . import engine, providers

bp = Blueprint("chat", __name__)


@bp.post("/d/<slug>/api/chat")
def chat(slug):
    dashboard = registry.get(slug)
    if dashboard is None or dashboard.chat is None or not dashboard.ready:
        return jsonify(error="Dashboard ini tidak punya AI agent."), 404
    user = auth.current_user()
    if user is None:
        return jsonify(error="Sesi login habis, silakan muat ulang halaman."), 401
    if not auth.can_open(user, dashboard):
        return jsonify(error="Tidak punya akses ke dashboard ini."), 403
    if not providers.configured():
        return jsonify(error="AI agent belum dikonfigurasi (API key di .env)."), 503

    body = request.get_json(silent=True) or {}
    message = str(body.get("message") or "").strip()[:engine.MAX_MESSAGE]
    if not message:
        return jsonify(error="Pertanyaan kosong"), 400
    try:
        answer, used, model = engine.answer(dashboard, message, body.get("history"),
                                            str(body.get("context") or "")[:500], body.get("filters"))
    except providers.AIUnavailable:
        return jsonify(error="Layanan AI sedang sibuk atau kena batas pemakaian. Coba lagi sebentar."), 503
    except providers.AIError as exc:
        current_app.logger.exception("AI provider gagal")
        return jsonify(error=f"Layanan AI menolak permintaan ({exc.code})."), 502
    except DATA_ERRORS as exc:
        current_app.logger.exception("Power BI gagal")
        return jsonify(error=f"Gagal mengambil data dari Power BI: {exc}"), 502
    return jsonify(answer=answer, tools=used, model=model)
