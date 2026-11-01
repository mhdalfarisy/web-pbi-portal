"""Dashboard Picking Slip: measure HTML Power BI dijalankan per tabel, iframe aman, dan hak akses."""
import re

import pytest

from mantra.core.cache import Cache
from mantra.dashboards.picking_slip import queries
from mantra.dashboards.picking_slip.measure_html import SEP_R, Measure

VALUES = {"totalMasterCompCount": "1", "hdLastUpdate": "01/01/2026", "jsPbiFilters": ""}


@pytest.fixture
def fake_powerbi(monkeypatch):
    """Setiap query data mengembalikan 2 baris teks; query satu nilai mengembalikan 46."""
    calls = []

    def fake_query(dataset, dax):
        calls.append(dax)
        return [{"v": 46}] if "EVALUATE ROW" in dax else [{"r": "baris1"}, {"r": "baris2"}]
    monkeypatch.setattr(queries, "query", fake_query)
    monkeypatch.setattr(queries, "_cache", Cache(0))
    return calls


@pytest.mark.parametrize("page, data_vars", [
    ("summary", {"jsRaw", "jsStat", "jsTer", "jsComp", "jsProj", "jsItems"}),
    ("detail", {"jsRaw", "jsOrd", "jsStk", "jsDesc", "jsJob", "jsStat", "jsTer", "jsComp", "jsProj"}),
])
def test_measure_is_split_into_data_queries_and_html(page, data_vars):
    measure = queries.MEASURES[page]
    assert set(measure.data) == data_vars
    for name, dax in measure.queries().items():
        assert dax.startswith("DEFINE") and 'EVALUATE SELECTCOLUMNS' in dax, name
    html = measure.render({**VALUES, **{n: "x" for n in data_vars}})
    assert html.lstrip().startswith("<!DOCTYPE html>") and "</html>" in html
    assert "__MANTRA_" not in html


def test_rows_are_joined_like_concatenatex():
    m = Measure('VAR SEP_R = UNICHAR ( 57345 )\nVAR jsA = CONCATENATEX ( T, T[c], SEP_R )\nRETURN\n"<p>" & jsA & "</p>"')
    assert set(m.data) == {"jsA"}
    assert m.render({"jsA": "a" + SEP_R + "b"}) == "<p>a" + SEP_R + "b</p>"


def test_frame_serves_measure_html_in_sandboxable_frame(login_as, fake_powerbi):
    c = login_as("admin")
    page = c.get("/d/picking-slip/").get_data(as_text=True)
    iframe = re.search(r"<iframe[^>]+>", page).group(0)
    assert 'src="/d/picking-slip/frame/summary"' in iframe and "sandbox=" in iframe and "allow-same-origin" not in iframe
    r = c.get("/d/picking-slip/frame/summary")
    assert r.status_code == 200 and r.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "var RAW_TXT  = 'baris1" + SEP_R + "baris2';" in r.get_data(as_text=True)
    assert c.get("/d/picking-slip/frame/lain").status_code == 404


def test_frame_needs_login_and_access(client, login_as, fake_powerbi):
    assert client.get("/d/picking-slip/frame/detail").status_code == 302   # belum login -> halaman login
    assert login_as("a").get("/d/picking-slip/frame/detail").status_code == 403   # tidak punya akses Picking Slip
    assert fake_powerbi == []   # ditolak sebelum Power BI ditanya
