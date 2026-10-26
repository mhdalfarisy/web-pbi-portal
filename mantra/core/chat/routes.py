"""Endpoint agent setiap dashboard: POST /d/<slug>/api/chat."""
import threading
import time
from collections import defaultdict, deque

from flask import Blueprint, current_app, jsonify, request

from ...config import Config
from .. import accounts, auth, registry
from ..errors import data_error_json
from ..powerbi import DATA_ERRORS
from . import engine, providers

bp = Blueprint("chat", __name__)

# Batas pertanyaan per user per menit (di memori, per proses). Satu pertanyaan bisa memicu beberapa panggilan AI
# dan query Power BI, jadi tanpa batas ini satu user bisa menghabiskan kuota bersama.
_hits = defaultdict(deque)
_hits_lock = threading.Lock()


def _rate_limited(user_id):
    now = time.monotonic()
    with _hits_lock:
        hits = _hits[user_id]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= Config.CHAT_MAX_PER_MINUTE:
            return True
        hits.append(now)
        return False


def reset_rate_limit():
    with _hits_lock:
        _hits.clear()


@bp.post("/d/<slug>/api/chat")
def chat(slug):
    dashboard = registry.get(slug)
    if dashboard is None or dashboard.chat is None or not dashboard.ready:
        return jsonify(error="This dashboard has no AI agent."), 404
    user = auth.current_user()
    if user is None:
        return jsonify(error="Your session has expired. Please reload the page."), 401
    if not auth.can_open(user, dashboard):
        accounts.audit("access_denied", "dashboard", slug, actor=user, path=request.path)
        return jsonify(error="You do not have access to this dashboard."), 403
    if _rate_limited(user["id"]):
        return jsonify(error="Too many questions. Please wait a minute and try again."), 429
    if not providers.configured():
        return jsonify(error="The AI agent is not configured yet (API key in .env)."), 503

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify(error="Invalid request."), 400
    message = str(body.get("message") or "").strip()[:engine.MAX_MESSAGE]
    if not message:
        return jsonify(error="Please type a question."), 400
    try:
        answer, used, model = engine.answer(dashboard, message, body.get("history"),
                                            str(body.get("context") or "")[:500], body.get("filters"))
    except providers.AIUnavailable:
        return jsonify(error="The AI service is busy or has reached its usage limit. Please try again shortly."), 503
    except providers.AIError as exc:
        current_app.logger.exception("AI provider gagal")
        return jsonify(error=f"The AI service rejected the request ({exc.code})."), 502
    except DATA_ERRORS as exc:
        return data_error_json(exc)
    return jsonify(answer=answer, tools=used, model=model)
