"""Fixture test MANTRA: database sementara (instance/mantra.db tidak disentuh), login wajib, tanpa Power BI/AI asli."""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mantra import create_app  # noqa: E402
from mantra.config import Config  # noqa: E402
from mantra.core import accounts, auth, db, powerbi  # noqa: E402
from mantra.core.chat import routes as chat_routes  # noqa: E402

# config.py memuat .env dengan override=True, jadi nilai di os.environ TIDAK bisa dipakai untuk test (selalu ditimpa
# .env). Nilai test dipasang langsung ke Config setelah import: secret key khusus test, tanpa AI asli (Gemini tidak
# pernah dipanggil), tanpa SSO, tanpa kredensial Power BI asli (request ke Power BI juga diblokir di bawah), dan
# selalu mode dev tanpa proxy (test staging membuat app sendiri, lihat test_server_config.py).
TEST_CONFIG = {"SECRET_KEY": "test-secret", "AUTH_DISABLED": False, "DEBUG": False, "DASHBOARD_STRICT": True,
               "APP_ENV": "dev", "TRUST_PROXY": 0,
               "GEMINI_API_KEY": "", "ENTRA_CLIENT_ID": "", "ENTRA_CLIENT_SECRET": "",
               "PBI_CLIENT_ID": "test-client-id", "PBI_CLIENT_SECRET": "test-client-secret"}
for _key, _value in TEST_CONFIG.items():
    setattr(Config, _key, _value)

PASSWORD = "Rahasia-Test-2026"
EMAILS = {"admin": "pbi_premium@merdeka.com", "a": "pbi_pro_a@merdeka.com", "b": "pbi_pro_b@merdeka.com"}
PAGES = {
    "material-readiness": ["/d/material-readiness/", "/d/material-readiness/detail"],
    "pani-processing": ["/d/pani-processing/", "/d/pani-processing/equipment", "/d/pani-processing/mining",
                        "/d/pani-processing/production"],
}
APIS = {"material-readiness": "/d/material-readiness/api/detail"}


@pytest.fixture(scope="session")
def app():
    tmp = Path(tempfile.mkdtemp(prefix="mantra-test-"))
    application = create_app({"TESTING": True, "AUTH_DISABLED": False, "INSTANCE_DIR": tmp,
                              "APP_DB": tmp / "mantra.db"})
    yield application


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    """Power BI tidak boleh dipanggil di test. Halaman dashboard yang lolos cek akses akan tampil sebagai error 502."""
    def blocked(self, *args, **kwargs):
        raise powerbi.PowerBIError("Power BI diblokir di test")
    monkeypatch.setattr(powerbi.PowerBI, "request", blocked)


@pytest.fixture(autouse=True)
def fresh_data(app):
    """Setiap test mulai dari data yang sama: 3 akun awal (sudah ganti password), semua dashboard aktif."""
    auth.reset_ip_throttle()
    chat_routes.reset_rate_limit()
    with app.app_context():
        conn = db.get_db()
        conn.executescript("""DELETE FROM user_dashboard_access; DELETE FROM users; DELETE FROM audit_log;
                              DELETE FROM favorites; DELETE FROM history; UPDATE dashboards SET is_active = 1;""")
        ids = {}
        for key, role, slugs in [("admin", "super_admin", []), ("a", "user", ["material-readiness"]),
                                 ("b", "user", ["pani-processing"])]:
            ids[key] = accounts.create_user(EMAILS[key], key, PASSWORD, role=role, must_change_password=False)
            if slugs:
                accounts.set_access(ids[key], accounts.dashboard_ids_for(slugs))
        conn.execute("DELETE FROM audit_log")
        conn.commit()
    yield ids


class Client:
    """Test client + helper login dengan CSRF yang benar."""

    def __init__(self, app):
        self.app = app
        self.c = app.test_client()

    def csrf(self):
        with self.c.session_transaction() as s:
            s.setdefault("_csrf", "test-csrf")
            return s["_csrf"]

    def login(self, email, password=PASSWORD, **kw):
        return self.c.post("/login", data={"email": email, "password": password, "_csrf": self.csrf(), **kw})

    def post(self, url, data=None, **kw):
        data = dict(data or {})
        data.setdefault("_csrf", self.csrf())
        return self.c.post(url, data=data, **kw)

    def __getattr__(self, name):
        return getattr(self.c, name)


@pytest.fixture
def client(app):
    return Client(app)


@pytest.fixture
def login_as(app):
    def make(key):
        c = Client(app)
        r = c.login(EMAILS[key])
        assert r.status_code == 302, r.get_data(as_text=True)[:500]
        return c
    return make


@pytest.fixture
def query(app):
    def run(sql, params=()):
        with app.app_context():
            return db.get_db().execute(sql, params).fetchall()
    return run
