"""Riwayat chat AI per user (kuota 1 MB, izin Chat Log) dan log aktivitas user."""
import json

from conftest import EMAILS, PAGES

from mantra.core import activity, db
from mantra.core.chat import providers


class _FakeProvider:
    """Provider palsu: memanggil satu tool, lalu menjawab dengan teks tetap (tanpa AI & Power BI asli)."""

    def __init__(self, tool="get_breakdown", args=None, answer="Jawaban AI"):
        self.tool, self.args, self.answer = tool, args or {"group_by": "galaxy"}, answer

    def chat(self, system, history, message, tools, call_tool, max_rounds):
        call_tool(self.tool, self.args)
        return self.answer, "fake-model"


def _use_fake_ai(monkeypatch, **kw):
    monkeypatch.setattr(providers, "configured", lambda: True)
    monkeypatch.setattr(providers, "get", lambda: _FakeProvider(**kw))


def _ask(client, message="Berapa PO?", slug="material-readiness", conversation="conv-test-0001"):
    return client.c.post(f"/d/{slug}/api/chat", json={"message": message, "conversation": conversation},
                         headers={"X-CSRF-Token": client.csrf()})


def test_chat_is_saved_without_power_bi_data(login_as, monkeypatch, query, fresh_data):
    _use_fake_ai(monkeypatch)
    r = _ask(login_as("a"))
    assert r.status_code == 200 and r.get_json()["conversation"] == "conv-test-0001"
    (row,) = query("SELECT * FROM chat_messages")
    assert (row["user_id"], row["user_email"], row["slug"]) == (str(fresh_data["a"]), EMAILS["a"], "material-readiness")
    assert (row["question"], row["answer"], row["model"], row["status"]) == ("Berapa PO?", "Jawaban AI", "fake-model", "ok")
    tools = json.loads(row["tools"])
    # Hanya nama, label, dan parameter tool; hasil query (di sini pesan valid_options) tidak ikut disimpan
    assert [set(t) for t in tools] == [{"name", "label", "args"}] and tools[0]["args"] == {"group_by": "galaxy"}
    assert "valid_options" not in row["tools"] and row["size_bytes"] > 0
    (log,) = query("SELECT * FROM activity_log WHERE action = 'ai_question'")
    assert log["slug"] == "material-readiness" and "Berapa PO" not in (log["detail"] or "")


def test_failed_ai_call_is_saved_as_error(login_as, monkeypatch, query):
    def busy():
        raise providers.AIUnavailable("kuota habis")
    monkeypatch.setattr(providers, "configured", lambda: True)
    monkeypatch.setattr(providers, "get", busy)
    assert _ask(login_as("a")).status_code == 503
    (row,) = query("SELECT status, answer FROM chat_messages")
    assert row["status"] == "error" and "busy" in row["answer"]


def test_invalid_conversation_id_is_replaced(login_as, monkeypatch, query):
    _use_fake_ai(monkeypatch)
    r = _ask(login_as("a"), conversation="<script>")
    conv = r.get_json()["conversation"]
    assert conv != "<script>" and activity.CONVERSATION_RE.match(conv)
    assert query("SELECT conversation FROM chat_messages")[0]["conversation"] == conv


def test_last_conversation_is_restored_per_user_and_dashboard(login_as, monkeypatch):
    _use_fake_ai(monkeypatch)
    a = login_as("a")
    _ask(a, "pertanyaan lama", conversation="conv-old-00001")
    _ask(a, "pertanyaan 1", conversation="conv-new-00001")
    _ask(a, "pertanyaan 2", conversation="conv-new-00001")
    data = a.get("/d/material-readiness/api/chat/history").get_json()
    assert data["conversation"] == "conv-new-00001"
    assert [m["question"] for m in data["messages"]] == ["pertanyaan 1", "pertanyaan 2"]
    assert set(data["messages"][0]) == {"question", "answer", "tools", "status", "created_at"}
    # User lain tidak melihat percakapan a, dan dashboard tanpa akses ditolak
    b = login_as("b")
    assert b.get("/d/pani-processing/api/chat/history").get_json()["messages"] == []
    assert b.get("/d/material-readiness/api/chat/history").status_code == 403


def test_quota_removes_oldest_chats_of_that_user_only(app, fresh_data):
    a = {"id": str(fresh_data["a"]), "email": EMAILS["a"]}
    b = {"id": str(fresh_data["b"]), "email": EMAILS["b"]}
    big = "x" * 100_000
    with app.test_request_context():
        activity.save_chat(b, "pani-processing", "conv-b-000001", "punya b", big)
        for i in range(15):
            activity.save_chat(a, "material-readiness", "conv-a-000001", f"q{i}", big)
        rows = db.get_db().execute("SELECT question FROM chat_messages WHERE user_id = ? ORDER BY id",
                                   (a["id"],)).fetchall()
        assert activity.chat_usage(a["id"]) <= activity.CHAT_QUOTA_BYTES
        assert [r["question"] for r in rows] == [f"q{i}" for i in range(5, 15)]  # 10 x ~100 KB tersisa
        assert activity.chat_usage(b["id"]) > 0  # kuota per user: chat b tidak ikut terhapus


def test_user_sees_and_deletes_only_own_chats(login_as, monkeypatch, query):
    _use_fake_ai(monkeypatch)
    _ask(login_as("a"), "pertanyaan milik a")
    b = login_as("b")
    _ask(b, "pertanyaan milik b", slug="pani-processing")
    page = b.get("/chats").get_data(as_text=True)
    assert "pertanyaan milik b" in page and "pertanyaan milik a" not in page
    assert b.post("/chats/delete").status_code == 303
    assert [r["question"] for r in query("SELECT question FROM chat_messages")] == ["pertanyaan milik a"]
    assert query("SELECT count(*) FROM activity_log WHERE action = 'chat_history_deleted'")[0][0] == 1


def test_chat_log_needs_permission_from_super_admin(login_as, monkeypatch, query, fresh_data):
    _use_fake_ai(monkeypatch)
    _ask(login_as("a"), "rahasia dagang a")
    b, admin = login_as("b"), login_as("admin")
    assert b.get("/chats/all").status_code == 403
    assert b.get("/chats/all.csv").status_code == 403
    assert "rahasia dagang a" in admin.get("/chats/all").get_data(as_text=True)

    assert "Allow viewing all AI chats" in admin.get(f"/admin/users/{fresh_data['b']}").get_data(as_text=True)
    assert admin.post(f"/admin/users/{fresh_data['b']}/chat-viewer", {"allowed": "1"}).status_code == 303
    assert "Remove Chat Log access" in admin.get(f"/admin/users/{fresh_data['b']}").get_data(as_text=True)
    page = b.get("/chats/all?q=dagang").get_data(as_text=True)
    assert "rahasia dagang a" in page and EMAILS["a"] in page
    csv = b.get(f"/chats/all.csv?user={fresh_data['a']}")
    assert csv.status_code == 200 and csv.mimetype == "text/csv" and "rahasia dagang a" in csv.get_data(as_text=True)
    assert query("SELECT count(*) FROM audit_log WHERE action = 'chat_log_exported'")[0][0] == 1
    assert query("SELECT count(*) FROM activity_log WHERE action = 'chat_log_viewed'")[0][0] >= 1

    assert admin.post(f"/admin/users/{fresh_data['b']}/chat-viewer", {"allowed": "0"}).status_code == 303
    assert b.get("/chats/all").status_code == 403
    actions = [r["action"] for r in query("SELECT action FROM audit_log WHERE action LIKE 'chat_viewer_%' ORDER BY id")]
    assert actions == ["chat_viewer_granted", "chat_viewer_revoked"]


def test_chat_log_search_and_csv_are_safe(app, login_as, fresh_data):
    a = {"id": str(fresh_data["a"]), "email": EMAILS["a"]}
    with app.test_request_context():
        activity.save_chat(a, "material-readiness", "conv-a-000001", "=HYPERLINK(\"x\")", "100% siap")
        activity.save_chat(a, "material-readiness", "conv-a-000001", "biasa", "jawaban")
    admin = login_as("admin")
    assert "biasa" not in admin.get("/chats/all?q=%25").get_data(as_text=True)  # % dicari sebagai huruf, bukan wildcard
    body = admin.get("/chats/all.csv").get_data(as_text=True)
    assert "'=HYPERLINK" in body  # rumus Excel dinetralkan


def test_activity_log_records_login_pages_and_logout(login_as, query):
    a = login_as("a")
    a.get(PAGES["material-readiness"][0])  # 502 karena Power BI diblokir di test, tetapi tetap tercatat
    a.post("/logout")
    rows = query("SELECT action, slug, detail FROM activity_log ORDER BY id")
    assert [r["action"] for r in rows] == ["login", "page_view", "logout"]
    assert rows[1]["slug"] == "material-readiness" and json.loads(rows[1]["detail"])["page"]


def test_activity_page_is_super_admin_only(login_as, query):
    a = login_as("a")
    a.get(PAGES["material-readiness"][0])
    assert a.get("/admin/activity").status_code == 403
    admin = login_as("admin")
    page = admin.get("/admin/activity?action=page_view").get_data(as_text=True)
    assert EMAILS["a"] in page and "Page opened" in page
    csv = admin.get("/admin/activity.csv")
    assert csv.status_code == 200 and "Page opened" in csv.get_data(as_text=True)
    assert query("SELECT count(*) FROM audit_log WHERE action = 'activity_exported'")[0][0] == 1


def test_old_activity_is_pruned(app):
    with app.test_request_context():
        conn = db.get_db()
        conn.execute("INSERT INTO activity_log (action, at) VALUES ('page_view', datetime('now', 'localtime', '-400 days'))")
        conn.commit()
        activity.reset_prune_timer()
        activity.log("login", user={"id": "1", "email": "x@merdeka.com"})
        assert [r["action"] for r in conn.execute("SELECT action FROM activity_log")] == ["login"]


def test_ask_ai_panel_shows_storage_notice(login_as, monkeypatch):
    from mantra.dashboards.material_readiness import queries as mr

    monkeypatch.setattr(providers, "configured", lambda: True)
    monkeypatch.setattr(mr, "company_logos", lambda: {})
    page = login_as("a").get(PAGES["material-readiness"][1]).get_data(as_text=True)
    assert "Questions and answers are saved" in page and "Do not type passwords" in page
    assert "/d/material-readiness/api/chat/history" in page


def test_sidebar_menus_follow_permission(login_as, fresh_data):
    a = login_as("a")
    page = a.get("/").get_data(as_text=True)
    assert "AI Chats" in page and "Chat Log" not in page
    login_as("admin").post(f"/admin/users/{fresh_data['a']}/chat-viewer", {"allowed": "1"})
    page = a.get("/").get_data(as_text=True)
    assert "Monitoring" in page and "Chat Log" in page and "/admin/activity" not in page
