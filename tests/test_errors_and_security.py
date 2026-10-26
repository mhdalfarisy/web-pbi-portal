"""Penanganan error, kebocoran info, batas (tanggal, AI, Power BI), header keamanan, cache, dan CSRF."""
import threading
import time
from datetime import date

import pytest

from conftest import APIS, PAGES

from mantra import create_app
from mantra.config import Config
from mantra.core import cache as cache_mod
from mantra.core import powerbi
from mantra.core.chat import providers
from mantra.dashboards.pani_processing import queries as pani


def _stub_pani(monkeypatch, bounds):
    """Halaman PANI tanpa Power BI: semua query kosong, bounds sesuai argumen."""
    for name in ("processing_bounds", "equipment_bounds", "mining_bounds", "production_bounds"):
        monkeypatch.setattr(pani, name, lambda b=bounds: dict(b))
    # EVALUATE ROW(...) di Power BI selalu mengembalikan tepat satu baris (nilai BLANK = None)
    monkeypatch.setattr(pani, "_query", lambda dax: [{"h": None, "t": None}] if "EVALUATE ROW(" in dax else [])
    monkeypatch.setattr(pani, "_cache", cache_mod.Cache(0))


# ---------------------------------------------------------------- No. 2, 3, 8: tanggal ekstrem & data kosong

def test_extreme_dates_are_clamped_not_500(login_as, monkeypatch):
    _stub_pani(monkeypatch, {"min": date(2026, 1, 1), "max": date(2026, 10, 20), "last": date(2026, 10, 20)})
    b = login_as("b")
    for url in ("/d/pani-processing/equipment?start=0001-01-01&end=0001-01-01",
                "/d/pani-processing/mining?start=9999-12-31&end=0001-01-01",
                "/d/pani-processing/production?start=bukan-tanggal"):
        r = b.get(url)
        assert r.status_code == 200, url
        assert 'value="2026-01-01"' in r.get_data(as_text=True) or 'value="2026-10' in r.get_data(as_text=True)


def test_date_range_is_clamped_to_data():
    b = {"min": date(2026, 1, 1), "max": date(2026, 10, 20)}
    assert pani.date_range(date(1, 1, 1), date(9999, 12, 31), b) == (date(2026, 1, 1), date(2026, 10, 20))
    assert pani.date_range(date(2026, 5, 9), date(2026, 5, 1), b) == (date(2026, 5, 1), date(2026, 5, 9))


def test_empty_model_shows_no_data_page(login_as, monkeypatch):
    _stub_pani(monkeypatch, {"min": None, "max": None, "last": None})
    b = login_as("b")
    for url in PAGES["pani-processing"]:
        r = b.get(url)
        assert r.status_code == 200 and "No data available yet" in r.get_data(as_text=True), url


# ---------------------------------------------------------------- No. 5: detail error Power BI tidak bocor

def test_power_bi_error_details_are_not_shown(login_as, monkeypatch):
    def leaky(self, *a, **k):
        raise powerbi.PowerBIError("POST /groups/WS-SECRET-ID/datasets/DS-SECRET-ID/executeQueries -> HTTP 400")
    monkeypatch.setattr(powerbi.PowerBI, "request", leaky)
    a = login_as("a")
    page = a.get(PAGES["material-readiness"][1])
    api = a.get(APIS["material-readiness"])
    export = a.get(APIS["material-readiness"] + "/export")
    for r in (page, api, export):
        body = r.get_data(as_text=True)
        assert r.status_code == 502 and "WS-SECRET-ID" not in body and "DS-SECRET-ID" not in body
    assert "Reference code" in page.get_data(as_text=True)
    assert api.is_json and api.get_json()["ref"] in api.get_json()["error"]


# ---------------------------------------------------------------- No. 4, 7: AI agent

class _FakeProvider:
    """Provider palsu: memanggil satu tool lalu mengembalikan hasilnya sebagai teks jawaban."""

    def __init__(self, tool, args):
        self.tool, self.args = tool, args

    def chat(self, system, history, message, tools, call_tool, max_rounds):
        return repr(call_tool(self.tool, self.args)), "fake-model"


def _ask(client, slug="material-readiness"):
    return client.c.post(f"/d/{slug}/api/chat", json={"message": "test"}, headers={"X-CSRF-Token": client.csrf()})


def test_invalid_tool_argument_returns_valid_options(login_as, monkeypatch):
    monkeypatch.setattr(providers, "configured", lambda: True)
    monkeypatch.setattr(providers, "get", lambda: _FakeProvider("get_breakdown", {"group_by": "galaxy"}))
    r = _ask(login_as("a"))
    assert r.status_code == 200 and "valid_options" in r.get_json()["answer"] and "plant" in r.get_json()["answer"]


def test_unexpected_tool_error_does_not_break_chat(login_as, monkeypatch):
    from mantra.dashboards.material_readiness import queries as mr

    monkeypatch.setattr(providers, "configured", lambda: True)
    monkeypatch.setattr(providers, "get", lambda: _FakeProvider("get_readiness_kpi", {}))
    monkeypatch.setattr(mr, "kpi", lambda f: {}["boom"])  # KeyError, bukan error Power BI
    r = _ask(login_as("a"))
    assert r.status_code == 200 and "This tool failed to run" in r.get_json()["answer"]


def test_chat_is_rate_limited_per_user(login_as):
    a = login_as("a")
    codes = [_ask(a).status_code for _ in range(Config.CHAT_MAX_PER_MINUTE + 1)]
    assert codes[:-1] == [503] * Config.CHAT_MAX_PER_MINUTE  # AI tidak dikonfigurasi di test
    assert codes[-1] == 429
    assert _ask(login_as("b"), "pani-processing").status_code == 503  # batas per user, bukan global


# ---------------------------------------------------------------- No. 13, 14, CSRF

def test_security_headers(client):
    r = client.get("/login")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Referrer-Policy"] == "same-origin"


def test_non_ascii_csrf_token_is_400_not_500(client):
    client.get("/login")
    r = client.c.post("/login", data={"email": "x@merdeka.com", "password": "x", "_csrf": "tökén-ñ"})
    assert r.status_code == 400 and "Invalid security token" in r.get_data(as_text=True)


def test_404_page_is_english(client):
    r = client.get("/tidak-ada")
    assert r.status_code == 404 and "Page not found." in r.get_data(as_text=True)


# ---------------------------------------------------------------- No. 15, 16, 19

def test_create_app_can_run_twice(tmp_path):
    for i in range(2):
        app = create_app({"TESTING": True, "INSTANCE_DIR": tmp_path, "APP_DB": tmp_path / f"m{i}.db"})
        assert "material_readiness.summary" in app.view_functions


def test_cache_loads_each_key_once_under_concurrency():
    cache, calls = cache_mod.Cache(60), []

    def load():
        calls.append(1)
        time.sleep(0.05)
        return "data"

    threads = [threading.Thread(target=cache.get, args=("k", load)) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1 and cache.get("k", load)[0] == "data"


def test_cache_does_not_store_errors():
    cache = cache_mod.Cache(60)
    with pytest.raises(ValueError):
        cache.get("k", lambda: (_ for _ in ()).throw(ValueError("x")))
    assert cache.get("k", lambda: "ok")[0] == "ok"


def test_login_background_is_only_used_when_file_exists(client):
    html = client.get("/login").get_data(as_text=True)
    assert "login-bg.jpg" not in html  # file opsional tidak ada di repo -> tidak ada request 404
