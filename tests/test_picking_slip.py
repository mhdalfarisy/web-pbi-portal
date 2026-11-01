"""Dashboard Picking Slip: DAX di queries.py, data digabung seperti CONCATENATEX, halaman memakai header MANTRA."""
import re

import pytest

from mantra.core.cache import Cache
from mantra.dashboards.picking_slip import queries


@pytest.fixture
def fake_powerbi(monkeypatch):
    """Query data: 2 baris teks (satu berisi </script> & baris baru). Query jumlah company: 46."""
    calls = []

    def fake_query(dataset, dax):
        calls.append(dax)
        return [{"v": 46}] if dax is queries.COMPANY_COUNT else [{"r": "baris1</script>"}, {"r": "baris\r\n2"}]
    monkeypatch.setattr(queries, "query", fake_query)
    monkeypatch.setattr(queries, "_cache", Cache(0))
    return calls


@pytest.mark.parametrize("name, data_vars", [
    ("SUMMARY", {"jsRaw", "jsStat", "jsTer", "jsComp", "jsProj", "jsItems"}),
    ("DETAIL", {"jsRaw", "jsOrd", "jsStk", "jsDesc", "jsJob", "jsStat", "jsTer", "jsComp", "jsProj"}),
])
def test_dax_is_typed_in_queries_py(name, data_vars):
    queries_ = getattr(queries, name)
    assert set(queries_) == data_vars
    for var, dax in queries_.items():
        assert "VAR SEP_F = UNICHAR ( 57344 )" in dax and 'SELECTCOLUMNS' in dax and '"r",' in dax, var
        assert "\\x3C" not in dax and '"\\\\"' not in dax, var   # escape literal JS measure tidak dipakai (data lewat JSON)


def test_rows_are_joined_like_concatenatex(fake_powerbi):
    data, _ = queries.summary()
    assert data["jsRaw"] == "baris1</script>" + queries.SEP_R + "baris  2"   # baris baru -> spasi, sama dengan measure
    assert data["totalMasterCompCount"] == 46 and data["jsPbiFilters"] == ""
    assert len(fake_powerbi) == len(queries.SUMMARY) + 1


@pytest.mark.parametrize("url, title, script", [
    ("/d/picking-slip/", "Picking Slip Summary", "summary.js"),
    ("/d/picking-slip/detail", "Picking Slip Detail", "detail.js"),
])
def test_pages_use_mantra_header_and_safe_json(login_as, fake_powerbi, url, title, script):
    html = login_as("admin").get(url).get_data(as_text=True)
    assert f'<h1 class="hd-main-title">{title}</h1>' in html and "<iframe" not in html
    assert re.search(rf'src="/d/picking-slip/static/{script}"', html)
    payload = re.search(r"window\.PICKING_SLIP = (.*?);</script>", html).group(1)
    assert "</script>" not in payload and "\\u003c/script\\u003e" in payload   # data tidak bisa menutup tag script


def test_pages_need_login_and_access(client, login_as, fake_powerbi):
    assert client.get("/d/picking-slip/detail").status_code == 302      # belum login -> halaman login
    assert login_as("a").get("/d/picking-slip/").status_code == 403      # tidak punya akses Picking Slip
    assert fake_powerbi == []                                            # ditolak sebelum Power BI ditanya
