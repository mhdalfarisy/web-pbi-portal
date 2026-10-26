"""Lupa password: permintaan dari halaman login diteruskan ke Super Admin, tanpa membocorkan email yang terdaftar."""
from conftest import EMAILS

SENT = "Request sent"


def _request(client, email):
    return client.post("/forgot-password", {"email": email})


def _flag(query, key):
    return query("SELECT reset_requested_at FROM users WHERE email = ?", (EMAILS[key],))[0]["reset_requested_at"]


def test_login_page_links_to_forgot_password(client):
    html = client.get("/login").get_data(as_text=True)
    assert 'href="/forgot-password"' in html and "Forgot password?" in html
    page = client.get("/forgot-password")
    assert page.status_code == 200 and 'name="email"' in page.get_data(as_text=True)


def test_request_for_registered_email_reaches_super_admin(client, login_as, query, fresh_data):
    r = _request(client, "  PBI_PRO_A@Merdeka.com ")
    assert r.status_code == 200 and SENT in r.get_data(as_text=True)
    assert _flag(query, "a") is not None
    assert query("SELECT count(*) n FROM audit_log WHERE action = 'password_reset_requested'")[0]["n"] == 1

    admin = login_as("admin")
    users = admin.get("/admin/users").get_data(as_text=True)
    assert "1 password reset request" in users and 'class="nav-badge"' in users and "Reset requested" in users
    detail = admin.get(f"/admin/users/{fresh_data['a']}").get_data(as_text=True)
    assert "This user asked for a password reset" in detail

    # Reset oleh Super Admin menyelesaikan permintaan
    assert admin.post(f"/admin/users/{fresh_data['a']}/reset-password").status_code == 200
    assert _flag(query, "a") is None
    assert 'class="nav-badge"' not in admin.get("/admin/users").get_data(as_text=True)


def test_unknown_and_inactive_emails_get_the_same_response(client, login_as, query, fresh_data):
    known = _request(client, EMAILS["b"]).get_data(as_text=True)
    unknown = _request(client, "tidak-terdaftar@merdeka.com").get_data(as_text=True)
    # Halaman hanya berbeda di email yang diketik user; tidak ada petunjuk email terdaftar atau tidak
    assert known.replace(EMAILS["b"], "X") == unknown.replace("tidak-terdaftar@merdeka.com", "X")
    assert query("SELECT count(*) n FROM users WHERE reset_requested_at IS NOT NULL")[0]["n"] == 1

    login_as("admin").post(f"/admin/users/{fresh_data['a']}/status", {"active": "0"})
    _request(client, EMAILS["a"])
    assert _flag(query, "a") is None  # akun nonaktif tidak ditandai
    results = {r["detail"] for r in query("SELECT detail FROM audit_log WHERE action = 'password_reset_requested'")}
    assert any('"not_registered"' in d for d in results) and any('"inactive"' in d for d in results)


def test_super_admin_can_dismiss_request(client, login_as, query, fresh_data):
    _request(client, EMAILS["a"])
    a = login_as("a")
    assert a.post(f"/admin/users/{fresh_data['a']}/dismiss-reset").status_code == 403  # bukan Super Admin
    assert _flag(query, "a") is not None

    admin = login_as("admin")
    r = admin.post(f"/admin/users/{fresh_data['a']}/dismiss-reset", follow_redirects=True)
    assert r.status_code == 200 and "dismissed" in r.get_data(as_text=True)
    assert _flag(query, "a") is None
    assert a.get("/").status_code == 200  # password & sesi user tidak berubah
    assert query("SELECT count(*) n FROM audit_log WHERE action = 'password_reset_dismissed'")[0]["n"] == 1


def test_invalid_email_is_rejected(client, query):
    r = _request(client, "bukan-email")
    assert r.status_code == 400 and "valid email" in r.get_data(as_text=True)
    assert not query("SELECT * FROM audit_log WHERE action = 'password_reset_requested'")


def test_requests_are_throttled_per_ip(client):
    for i in range(5):
        assert _request(client, f"user{i}@merdeka.com").status_code == 200
    assert _request(client, EMAILS["a"]).status_code == 429


def test_signed_in_user_is_sent_home(login_as):
    assert login_as("a").get("/forgot-password").status_code == 302


def test_post_requires_csrf(client, query):
    assert client.c.post("/forgot-password", data={"email": EMAILS["a"]}).status_code == 400
    assert _flag(query, "a") is None
