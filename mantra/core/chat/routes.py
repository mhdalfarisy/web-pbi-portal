"""Endpoint agent setiap dashboard: POST /d/<slug>/api/chat (tanya) dan GET /d/<slug>/api/chat/history.

Setiap tanya-jawab disimpan ke riwayat chat user (core/activity.py): pertanyaan, jawaban, nama tool + parameter.
Hasil query Power BI tidak disimpan."""
import threading
import time
from collections import defaultdict, deque

from flask import Blueprint, current_app, jsonify, request

from ...config import Config
from .. import accounts, activity, auth, registry
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


def _open(slug):
    """(dashboard, user, None) kalau user boleh memakai agent dashboard ini, atau (None, None, respons_error)."""
    dashboard = registry.get(slug)
    if dashboard is None or dashboard.chat is None or not dashboard.ready:
        return None, None, (jsonify(error="This dashboard has no AI agent."), 404)
    user = auth.current_user()
    if user is None:
        return None, None, (jsonify(error="Your session has expired. Please reload the page."), 401)
    if not auth.can_open(user, dashboard):
        accounts.audit("access_denied", "dashboard", slug, actor=user, path=request.path)
        return None, None, (jsonify(error="You do not have access to this dashboard."), 403)
    return dashboard, user, None


@bp.post("/d/<slug>/api/chat")
def chat(slug):
    dashboard, user, error = _open(slug)
    if error:
        return error
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
    conversation = activity.conversation_id(body.get("conversation"))
    started = time.perf_counter()

    def record(answer, used=(), model=None, failed=False):
        """Simpan tanya-jawab ke riwayat chat user + log aktivitas (tanpa data mentah Power BI)."""
        ms = round((time.perf_counter() - started) * 1000)
        activity.save_chat(user, slug, conversation, message, answer, used, model, "error" if failed else "ok", ms)
        activity.log("ai_question", user=user, slug=slug, status="error" if failed else "ok",
                     tools=[u["name"] for u in used], ms=ms, **({"error": answer} if failed else {}))

    try:
        answer, used, model = engine.answer(dashboard, message, body.get("history"),
                                            str(body.get("context") or "")[:500], body.get("filters"))
    except providers.AIUnavailable:
        text = "The AI service is busy or has reached its usage limit. Please try again shortly."
        record(text, failed=True)
        return jsonify(error=text, conversation=conversation), 503
    except providers.AIError as exc:
        current_app.logger.exception("AI provider gagal")
        text = f"The AI service rejected the request ({exc.code})."
        record(text, failed=True)
        return jsonify(error=text, conversation=conversation), 502
    except DATA_ERRORS as exc:
        resp, code = data_error_json(exc)
        record(resp.get_json()["error"], failed=True)
        return resp, code
    record(answer, used, model)
    return jsonify(answer=answer, tools=used, model=model, conversation=conversation)


@bp.get("/d/<slug>/api/chat/history")
def chat_history(slug):
    """Percakapan terakhir user di dashboard ini, untuk ditampilkan lagi saat panel Ask AI dibuka."""
    _dashboard, user, error = _open(slug)
    if error:
        return error
    conversation, chats = activity.last_conversation(user, slug)
    return jsonify(conversation=conversation,
                   messages=[{k: c[k] for k in ("question", "answer", "tools", "status", "created_at")} for c in chats])
