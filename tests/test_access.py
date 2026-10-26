"""Login, RBAC, dan hak akses dashboard (acceptance criteria 1-10, 14)."""
import re

import pytest

from conftest import APIS, EMAILS, PAGES, PASSWORD

ALL = {"material-readiness", "pani-processing"}


def report_links(html):
    return set(re.findall(r'href="/d/([a-z0-9-]+)/"', html))


# ---------------------------------------------------------------- 1-4: login & daftar dashboard

def test_super_admin_login_success(client, query):
    r = client.login(EMAILS["admin"])
    assert r.status_code == 302 and r.headers["Location"].endswith("/")
    home = client.get("/")
    assert home.status_code == 200 and "Super Admin" in home.get_data(as_text=True)
    assert query("SELECT action FROM audit_log WHERE action = 'login_success'")


def test_wrong_password_rejected_with_generic_message(client):
    for email in (EMAILS["admin"], "tidak-ada@merdeka.com"):
        r = client.login(email, "salah-password-123")
        assert r.status_code == 401
        assert "Email atau password salah." in r.get_data(as_text=True)
    assert client.get("/").status_code == 302  # tetap belum login


def test_email_is_normalized(client):
    assert client.login("  PBI_PRO_A@Merdeka.COM ").status_code == 302


def test_super_admin_sees_all_active_dashboards(login_as):
    html = login_as("admin").get("/reports").get_data(as_text=True)
    assert report_links(html) == ALL


@pytest.mark.parametrize("key,expected", [("a", {"material-readiness"}), ("b", {"pani-processing"})])
def test_user_sees_only_granted_dashboards(login_as, key, expected):
    c = login_as(key)
    for page in ("/", "/reports"):
        assert report_links(c.get(page).get_data(as_text=True)) == expected


# ---------------------------------------------------------------- 5-6: akses URL langsung

@pytest.mark.parametrize("key,allowed,denied", [("a", "material-readiness", "pani-processing"),
                                                ("b", "pani-processing", "material-readiness")])
def test_direct_url_to_other_dashboard_is_403(login_as, query, key, allowed, denied):
    c = login_as(key)
    for url in PAGES[denied]:
        r = c.get(url)
        assert r.status_code == 403, url
        assert "Akses ditolak" in r.get_data(as_text=True)
    for url in PAGES[allowed]:
        # Lolos cek akses; Power BI diblokir di test sehingga halaman tampil sebagai error data (502), bukan 403
        assert c.get(url).status_code == 502, url
    denials = query("SELECT target_id FROM audit_log WHERE action = 'access_denied'")
    assert {r["target_id"] for r in denials} == {denied}


def test_data_api_static_and_chat_are_protected(login_as):
    b = login_as("b")
    r = b.get(APIS["material-readiness"])
    assert r.status_code == 403 and r.is_json
    assert b.get("/d/material-readiness/static/summary.js").status_code == 403
    r = b.c.post("/d/material-readiness/api/chat", json={"message": "berapa PO?"},
               headers={"X-CSRF-Token": b.csrf()})
    assert r.status_code in (403, 404)  # 404 kalau dashboard tidak punya agent; tidak pernah 200


def test_anonymous_is_redirected_or_401(client):
    assert client.get("/d/material-readiness/").status_code == 302
    assert client.get(APIS["material-readiness"]).status_code == 401
    assert client.get("/admin/users").status_code == 302


# ---------------------------------------------------------------- 7: halaman admin

ADMIN_GETS = ["/admin/users", "/admin/users/new", "/admin/dashboards", "/admin/audit"]


def test_regular_user_cannot_open_admin(login_as, fresh_data):
    c = login_as("a")
    for url in ADMIN_GETS + [f"/admin/users/{fresh_data['b']}"]:
        assert c.get(url).status_code == 403, url
    html = c.get("/").get_data(as_text=True)
    assert "/admin/users" not in html  # menu admin juga tidak tampil


def test_super_admin_can_open_admin(login_as):
    c = login_as("admin")
    for url in ADMIN_GETS:
        assert c.get(url).status_code == 200, url


# ---------------------------------------------------------------- 8-10: nonaktif, cabut akses, dashboard nonaktif

def test_deactivated_user_is_logged_out_immediately(login_as, fresh_data):
    a = login_as("a")
    admin = login_as("admin")
    assert a.get("/").status_code == 200
    assert admin.post(f"/admin/users/{fresh_data['a']}/status", {"active": "0"}).status_code == 303
    assert a.get("/").status_code == 302  # sesi lama langsung tidak berlaku
    assert a.get(PAGES["material-readiness"][0]).status_code == 302
    r = a.login(EMAILS["a"])
    assert r.status_code == 401 and "nonaktif" in r.get_data(as_text=True)


def test_revoked_access_applies_on_next_request(login_as, fresh_data, query):
    a = login_as("a")
    admin = login_as("admin")
    assert a.get(PAGES["material-readiness"][0]).status_code == 502  # masih boleh (data diblokir di test)
    assert admin.post(f"/admin/users/{fresh_data['a']}/access", {}).status_code == 303  # semua centang dihapus
    assert a.get(PAGES["material-readiness"][0]).status_code == 403
    assert report_links(a.get("/reports").get_data(as_text=True)) == set()
    assert query("SELECT count(*) n FROM audit_log WHERE action = 'access_revoked'")[0]["n"] == 1


def test_granting_access_through_admin_is_persisted(login_as, fresh_data, query):
    admin = login_as("admin")
    ids = {r["slug"]: r["id"] for r in query("SELECT id, slug FROM dashboards")}
    admin.post(f"/admin/users/{fresh_data['a']}/access",
               {"dashboard": [str(ids["material-readiness"]), str(ids["pani-processing"])]})
    rows = query("""SELECT d.slug, a.granted_by FROM user_dashboard_access a JOIN dashboards d ON d.id = a.dashboard_id
                    WHERE a.user_id = ?""", (fresh_data["a"],))
    assert {r["slug"] for r in rows} == ALL
    assert {r["granted_by"] for r in rows if r["slug"] == "pani-processing"} == {fresh_data["admin"]}
    assert login_as("a").get(PAGES["pani-processing"][0]).status_code == 502


def test_inactive_dashboard_is_blocked_for_everyone(login_as, query):
    admin = login_as("admin")
    mr = query("SELECT id FROM dashboards WHERE slug = 'material-readiness'")[0]["id"]
    assert admin.post(f"/admin/dashboards/{mr}/status", {"active": "0"}).status_code == 303
    for c in (login_as("a"), admin):
        assert c.get(PAGES["material-readiness"][0]).status_code == 403
        assert "material-readiness" not in report_links(c.get("/reports").get_data(as_text=True))


# ---------------------------------------------------------------- 14: manipulasi request

def test_user_cannot_change_access_by_manipulating_requests(login_as, fresh_data, query):
    a = login_as("a")
    ids = [str(r["id"]) for r in query("SELECT id FROM dashboards")]
    assert a.post(f"/admin/users/{fresh_data['a']}/access", {"dashboard": ids}).status_code == 403
    assert a.post(f"/admin/users/{fresh_data['b']}/status", {"active": "0"}).status_code == 403
    assert a.post("/admin/users/new", {"email": "x@merdeka.com", "dashboard": ids}).status_code == 403
    assert a.post("/api/favorites/pani-processing", headers={"X-CSRF-Token": a.csrf()}).status_code == 404
    assert a.get(PAGES["pani-processing"][0] + "?slug=material-readiness").status_code == 403
    rows = query("SELECT dashboard_id FROM user_dashboard_access WHERE user_id = ?", (fresh_data["a"],))
    assert len(rows) == 1
    assert query("SELECT count(*) n FROM users")[0]["n"] == 3


def test_post_without_csrf_is_rejected(login_as, fresh_data):
    admin = login_as("admin")
    r = admin.c.post(f"/admin/users/{fresh_data['a']}/status", data={"active": "0"})
    assert r.status_code == 400
    assert login_as("a").get("/").status_code == 200  # tidak berubah


def test_admin_rejects_unknown_dashboard_id(login_as, fresh_data, query):
    admin = login_as("admin")
    r = admin.post(f"/admin/users/{fresh_data['a']}/access", {"dashboard": ["99999"]}, follow_redirects=True)
    assert "Dashboard tidak dikenal." in r.get_data(as_text=True)
    assert len(query("SELECT * FROM user_dashboard_access WHERE user_id = ?", (fresh_data["a"],))) == 1


def test_no_web_route_can_promote_to_super_admin(login_as, fresh_data, query):
    admin = login_as("admin")
    admin.post("/admin/users/new", {"email": "baru@merdeka.com", "role": "super_admin"})
    admin.post(f"/admin/users/{fresh_data['a']}/access", {"role": "super_admin"})
    roles = {r["email"]: r["role"] for r in query("SELECT email, role FROM users")}
    assert roles["baru@merdeka.com"] == "user" and roles[EMAILS["a"]] == "user"
    assert not any(rule.rule.endswith("/role") for rule in admin.app.url_map.iter_rules())


def test_admin_cannot_deactivate_self(login_as, fresh_data):
    admin = login_as("admin")
    admin.post(f"/admin/users/{fresh_data['admin']}/status", {"active": "0"})
    assert admin.get("/admin/users").status_code == 200


# ---------------------------------------------------------------- password, lockout, user baru

def test_new_user_must_change_temporary_password(login_as, query):
    admin = login_as("admin")
    mr = query("SELECT id FROM dashboards WHERE slug = 'material-readiness'")[0]["id"]
    r = admin.post("/admin/users/new", {"email": "Baru@Merdeka.com", "name": "Baru", "dashboard": [str(mr)]})
    assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store"
    temp = re.search(r'<code id="tempPass">([^<]+)</code>', r.get_data(as_text=True)).group(1)

    from conftest import Client
    c = Client(admin.app)
    r = c.login("baru@merdeka.com", temp)
    assert r.status_code == 302 and "/account/password" in r.headers["Location"]
    assert c.get("/").status_code == 302                         # halaman lain belum boleh dibuka
    assert c.get(APIS["material-readiness"]).status_code == 403   # API juga
    r = c.post("/account/password", {"current_password": temp, "new_password": "pendek1",
                                     "confirm_password": "pendek1"})
    assert r.status_code == 400
    r = c.post("/account/password", {"current_password": temp, "new_password": "Sandi-Kuat-2026x",
                                     "confirm_password": "Sandi-Kuat-2026x"})
    assert r.status_code == 302
    assert c.get("/").status_code == 200
    assert report_links(c.get("/reports").get_data(as_text=True)) == {"material-readiness"}


def test_reset_password_logs_out_user(login_as, fresh_data):
    a = login_as("a")
    r = login_as("admin").post(f"/admin/users/{fresh_data['a']}/reset-password")
    assert r.status_code == 200 and "tempPass" in r.get_data(as_text=True)
    assert a.get("/").status_code == 302
    assert a.login(EMAILS["a"]).status_code == 401  # password lama tidak berlaku


def test_account_locks_after_repeated_failures(client, query):
    for _ in range(5):
        client.login(EMAILS["a"], "salah-salah-1")
    r = client.login(EMAILS["a"])  # password benar pun ditolak selama terkunci
    assert r.status_code == 401 and "dikunci" in r.get_data(as_text=True)
    assert query("SELECT count(*) n FROM audit_log WHERE action = 'account_locked'")[0]["n"] == 1


def test_ip_throttle(client):
    for i in range(20):
        client.login(f"tidak-ada-{i}@merdeka.com", "x")
    assert client.login(EMAILS["a"]).status_code == 429


def test_session_cookie_cannot_be_forged(app, fresh_data):
    c = app.test_client()
    c.set_cookie("session", "eyJ1aWQiOjF9.forged.signature")  # {"uid": 1} tanpa tanda tangan yang valid
    assert c.get("/admin/users").status_code == 302


def test_audit_log_is_human_readable(login_as, fresh_data):
    admin = login_as("admin")
    admin.post(f"/admin/users/{fresh_data['a']}/access", {})          # cabut Material Readiness dari User A
    login_as("b").get(PAGES["material-readiness"][0])                 # User B mencoba membuka tanpa izin
    html = admin.get("/admin/audit").get_data(as_text=True)
    assert f"Akses {EMAILS['a']} ke Material Readiness dicabut" in html
    assert "Mencoba membuka Material Readiness tanpa izin" in html
    assert "Akses dicabut" in html and "Akses ditolak" in html          # label aktivitas, bukan kode mentah
    assert ">access_revoked<" not in html


def test_root_redirects_to_clean_login_page(client):
    r = client.get("/")
    assert r.status_code == 302 and r.headers["Location"] == "/login"
    page = client.get("/login")
    assert page.status_code == 200 and 'name="password"' in page.get_data(as_text=True)
