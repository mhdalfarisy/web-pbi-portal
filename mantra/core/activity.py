"""Riwayat chat AI per user dan log aktivitas user di website (tabel chat_messages & activity_log di mantra.db).

Riwayat chat AI:
- Yang disimpan: pertanyaan, jawaban AI, nama tool + parameternya, model, lama proses, dan status (berhasil / error).
  Hasil query Power BI (data mentah), password, token, dan secret TIDAK disimpan.
- Kuota CHAT_QUOTA_BYTES per user. Kalau terlewati, chat paling lama milik user itu dihapus otomatis.
- User hanya melihat chat miliknya sendiri (menu AI Chats) dan bisa menghapusnya. Chat semua user (menu Chat Log) hanya
  untuk Super Admin dan user yang diberi izin (kolom users.can_view_chats, diatur di Admin > Users).

Log aktivitas (menu Admin > Activity, hanya Super Admin): login/logout, halaman dashboard yang dibuka, pertanyaan AI
(tanpa isi pertanyaan; isinya ada di riwayat chat), export, dan pembukaan Chat Log. Disimpan ACTIVITY_KEEP_DAYS hari,
lalu dihapus otomatis. Kejadian keamanan (login gagal, perubahan akun & hak akses) tetap dicatat di audit_log
(core/accounts.py).
"""
import csv
import io
import json
import re
import time
import uuid

from flask import Response, has_request_context, request

from .db import get_db

CHAT_QUOTA_BYTES = 1024 * 1024        # 1 MB riwayat chat per user
ACTIVITY_KEEP_DAYS = 365
PRUNE_EVERY_SECONDS = 3600            # pembersihan log aktivitas lama cukup sekali sejam per proses
EXPORT_LIMIT = 50000                  # baris maksimal per file CSV
CONVERSATION_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_last_prune = 0.0

ACTIVITY_LABELS = {
    "login": "Signed in", "logout": "Signed out", "page_view": "Page opened", "ai_question": "AI question",
    "export": "Export", "chat_history_deleted": "Chat history deleted", "chat_log_viewed": "Chat Log opened",
}


def _user_key(user):
    return str(user["id"])


def format_size(size):
    """Ukuran byte -> teks singkat (dipakai di template lewat filter |filesize)."""
    size = size or 0
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB".replace(".0 KB", " KB")
    return f"{size / 1024 / 1024:.2f}".rstrip("0").rstrip(".") + " MB"


def clean_filters(args):
    """Filter dari query string halaman Chat Log / Activity. Nilai yang tidak valid diabaikan."""
    def date(name):
        value = (args.get(name) or "").strip()
        return value if DATE_RE.match(value) else ""
    return {"user": (args.get("user") or "").strip()[:64], "dashboard": (args.get("dashboard") or "").strip()[:64],
            "action": (args.get("action") or "").strip()[:64], "q": (args.get("q") or "").strip()[:200],
            "date_from": date("from"), "date_to": date("to")}


def _where(filters, time_col, text_cols=(), with_action=False):
    """Klausa WHERE + parameter dari clean_filters(). Tanggal dibandingkan sebagai teks 'YYYY-MM-DD HH:MM:SS'.
    text_cols = kolom yang dicari dengan kata kunci q; with_action = tabel punya kolom action (activity_log)."""
    parts, params = [], []
    if filters.get("user"):
        parts.append("user_id = ?")
        params.append(filters["user"])
    if filters.get("dashboard"):
        parts.append("slug = ?")
        params.append(filters["dashboard"])
    if filters.get("action") and with_action:
        parts.append("action = ?")
        params.append(filters["action"])
    if filters.get("date_from"):
        parts.append(f"{time_col} >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        parts.append(f"{time_col} < date(?, '+1 day')")
        params.append(filters["date_to"])
    if filters.get("q") and text_cols:
        like = "%" + re.sub(r"([\\%_])", r"\\\1", filters["q"]) + "%"
        parts.append("(" + " OR ".join(f"{c} LIKE ? ESCAPE '\\'" for c in text_cols) + ")")
        params.extend([like] * len(text_cols))
    return (" WHERE " + " AND ".join(parts)) if parts else "", params


def csv_response(filename, header, rows):
    """File CSV untuk diunduh. Sel yang diawali = + - @ diberi tanda kutip satu supaya tidak dijalankan Excel."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    for row in rows:
        writer.writerow(["'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v for v in row])
    resp = Response("﻿" + out.getvalue(), mimetype="text/csv")  # BOM: Excel membaca UTF-8 dengan benar
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ------------------------------------------------------------------ riwayat chat AI

def conversation_id(value):
    """ID percakapan yang dikirim panel Ask AI; dibuat baru kalau kosong atau formatnya tidak valid."""
    value = str(value or "")
    return value if CONVERSATION_RE.match(value) else uuid.uuid4().hex


def save_chat(user, slug, conversation, question, answer, tools=(), model=None, status="ok", duration_ms=None):
    """Simpan satu tanya-jawab, lalu hapus chat paling lama milik user ini kalau total melewati kuota.

    tools = daftar {"name", "label", "args"} dari engine.answer(); hanya nama, label, dan parameter yang disimpan."""
    tools_json = json.dumps([{"name": t["name"], "label": t.get("label") or t["name"], "args": t.get("args") or {}}
                             for t in tools], ensure_ascii=False, default=str) if tools else None
    size = sum(len(s.encode("utf-8")) for s in (question, answer or "", tools_json or ""))
    key = _user_key(user)
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO chat_messages (user_id, user_email, slug, conversation, question, answer, tools, model, status,
                                      duration_ms, size_bytes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (key, user["email"], slug, conversation, question, answer or "", tools_json, model, status, duration_ms, size))
    conn.execute(
        """DELETE FROM chat_messages WHERE id IN (
               SELECT id FROM (SELECT id, sum(size_bytes) OVER (ORDER BY id DESC) AS total
                               FROM chat_messages WHERE user_id = ?) WHERE total > ?)""",
        (key, CHAT_QUOTA_BYTES))
    conn.commit()
    return cur.lastrowid


def _chat(row):
    try:
        tools = json.loads(row["tools"]) if row["tools"] else []
    except ValueError:
        tools = []
    return {"id": row["id"], "created_at": row["created_at"], "user_id": row["user_id"],
            "user_email": row["user_email"], "slug": row["slug"], "conversation": row["conversation"],
            "question": row["question"], "answer": row["answer"], "tools": tools, "model": row["model"],
            "status": row["status"], "duration_ms": row["duration_ms"], "size_bytes": row["size_bytes"]}


def chat_usage(user_id):
    """Total ukuran riwayat chat milik user (byte)."""
    return get_db().execute("SELECT coalesce(sum(size_bytes), 0) FROM chat_messages WHERE user_id = ?",
                            (str(user_id),)).fetchone()[0]


def last_conversation(user, slug, limit=20):
    """Percakapan terakhir user di dashboard ini: (conversation_id, [chat lama -> baru]), atau (None, [])."""
    key = _user_key(user)
    conn = get_db()
    row = conn.execute("SELECT conversation FROM chat_messages WHERE user_id = ? AND slug = ? ORDER BY id DESC LIMIT 1",
                       (key, slug)).fetchone()
    if row is None:
        return None, []
    rows = conn.execute(
        """SELECT * FROM (SELECT * FROM chat_messages WHERE user_id = ? AND slug = ? AND conversation = ?
                          ORDER BY id DESC LIMIT ?) ORDER BY id""",
        (key, slug, row["conversation"], limit)).fetchall()
    return row["conversation"], [_chat(r) for r in rows]


def chats_of(user, slug=None, limit=200):
    filters = {"user": _user_key(user), "dashboard": slug or ""}
    where, params = _where(filters, "created_at")
    rows = get_db().execute(f"SELECT * FROM chat_messages{where} ORDER BY id DESC LIMIT ?", (*params, limit))
    return [_chat(r) for r in rows]


def delete_chats(user):
    """Hapus seluruh riwayat chat milik user. Mengembalikan jumlah chat yang dihapus."""
    conn = get_db()
    count = conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (_user_key(user),)).rowcount
    conn.commit()
    return count


def chat_entries(filters, limit=200):
    """Chat semua user (halaman Chat Log), terbaru dulu."""
    where, params = _where(filters, "created_at", text_cols=("question", "answer"))
    rows = get_db().execute(f"SELECT * FROM chat_messages{where} ORDER BY id DESC LIMIT ?", (*params, limit))
    return [_chat(r) for r in rows]


def chat_count(filters):
    where, params = _where(filters, "created_at", text_cols=("question", "answer"))
    return get_db().execute(f"SELECT count(*) FROM chat_messages{where}", params).fetchone()[0]


def chat_users():
    """[(user_id, email)] yang punya riwayat chat, untuk filter halaman Chat Log."""
    return [(r["user_id"], r["email"]) for r in get_db().execute(
        "SELECT user_id, max(user_email) AS email FROM chat_messages GROUP BY user_id ORDER BY email")]


# ------------------------------------------------------------------ log aktivitas

def log(action, user=None, slug=None, **detail):
    """Catat aktivitas user. Seperti audit(): JANGAN memasukkan password, token, secret, atau data Power BI ke detail."""
    ip = request.remote_addr if has_request_context() else None
    conn = get_db()
    conn.execute(
        "INSERT INTO activity_log (user_id, user_email, action, slug, detail, ip) VALUES (?, ?, ?, ?, ?, ?)",
        (_user_key(user) if user else None, user.get("email") if user else None, action, slug,
         json.dumps(detail, ensure_ascii=False, default=str) if detail else None, ip))
    _prune(conn)
    conn.commit()


def _prune(conn):
    global _last_prune
    now = time.monotonic()
    if _last_prune and now - _last_prune < PRUNE_EVERY_SECONDS:
        return
    _last_prune = now
    conn.execute("DELETE FROM activity_log WHERE at < datetime('now', 'localtime', ?)", (f"-{ACTIVITY_KEEP_DAYS} days",))


def reset_prune_timer():
    global _last_prune
    _last_prune = 0.0


def activity_entries(filters, limit=300):
    where, params = _where(filters, "at", with_action=True)
    return get_db().execute(f"SELECT * FROM activity_log{where} ORDER BY at DESC, id DESC LIMIT ?",
                            (*params, limit)).fetchall()


def activity_summary(filters):
    """Rekap per user untuk filter yang sama: terakhir aktif, jumlah login, halaman, pertanyaan AI, export."""
    where, params = _where(filters, "at", with_action=True)
    return get_db().execute(
        f"""SELECT user_id, max(user_email) AS email, max(at) AS last_at, sum(action = 'login') AS logins,
                   sum(action = 'page_view') AS page_views, sum(action = 'ai_question') AS questions,
                   sum(action = 'export') AS exports
            FROM activity_log{where} GROUP BY user_id ORDER BY last_at DESC""", params).fetchall()


def activity_users():
    return [(r["user_id"], r["email"]) for r in get_db().execute(
        """SELECT user_id, max(user_email) AS email FROM activity_log WHERE user_id IS NOT NULL
           GROUP BY user_id ORDER BY email""")]


def activity_actions():
    codes = [r["action"] for r in get_db().execute("SELECT DISTINCT action FROM activity_log")]
    return sorted(((c, ACTIVITY_LABELS.get(c, c)) for c in codes), key=lambda item: item[1])


def describe_activity(rows, dashboard_names):
    """Baris activity_log -> {e, label, text} yang mudah dibaca. dashboard_names = {slug: nama}."""
    out = []
    for e in rows:
        try:
            d = json.loads(e["detail"]) if e["detail"] else {}
        except ValueError:
            d = {}
        action, dash = e["action"], dashboard_names.get(e["slug"], e["slug"] or "")
        if action == "login":
            text = f"Signed in with {'a Microsoft account' if d.get('method') == 'entra' else 'email + password'}"
        elif action == "logout":
            text = "Signed out"
        elif action == "page_view":
            text = f"{dash} · {d.get('page') or '-'}"
        elif action == "ai_question":
            tools = ", ".join(d.get("tools") or []) or "no data tool"
            text = (f"Asked the {dash} AI agent ({tools})" if d.get("status") == "ok"
                    else f"Asked the {dash} AI agent, failed: {d.get('error') or 'error'}")
        elif action == "export":
            text = f"Exported data from {dash} ({d.get('path') or '-'})"
        elif action == "chat_history_deleted":
            text = f"Deleted own AI chat history ({d.get('count', 0)} chats)"
        elif action == "chat_log_viewed":
            text = "Opened the Chat Log of all users"
        else:
            text = e["detail"] or ""
        out.append({"e": e, "label": ACTIVITY_LABELS.get(action, action), "text": text})
    return out
