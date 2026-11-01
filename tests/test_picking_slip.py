"""Dashboard Picking Slip: DAX di queries.py, data seperti CONCATENATEX, header MANTRA, tools AI agent, hak akses."""
import re

import pytest

from mantra.core.cache import Cache
from mantra.core.chat.guards import ToolArgError
from mantra.dashboards.picking_slip import queries, tools


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


@pytest.mark.parametrize("url, title, page", [
    ("/d/picking-slip/", "Picking Slip Summary", "summary"),
    ("/d/picking-slip/detail", "Picking Slip Detail", "detail"),
])
def test_pages_use_mantra_header_and_safe_json(login_as, fake_powerbi, url, title, page):
    html = login_as("admin").get(url).get_data(as_text=True)
    assert f'<h1 class="hd-main-title">{title}</h1>' in html and "<iframe" not in html
    assert 'src="/d/picking-slip/static/picking.js"' in html and 'href="/d/picking-slip/static/picking.css"' in html
    payload = re.search(r"window\.PICKING_SLIP = (.*?);</script>", html).group(1)
    assert f'"page": "{page}"' in payload
    assert "</script>" not in payload and "\\u003c/script\\u003e" in payload   # data tidak bisa menutup tag script


def test_pages_need_login_and_access(client, login_as, fake_powerbi):
    assert client.get("/d/picking-slip/detail").status_code == 302      # belum login -> halaman login
    assert login_as("a").get("/d/picking-slip/").status_code == 403      # tidak punya akses Picking Slip
    assert fake_powerbi == []                                            # ditolak sebelum Power BI ditanya


# ---------------------------------------------------------------- AI agent (tools.py) dengan data kecil yang realistis
F, R = "\ue000", queries.SEP_R
FAKE = {
    "summary": {"jsRaw": F.join(["BTR", "100", "ITEM1", "11", "EA", "MAIN", "DEPT0001", "1500.5", "20261030", "2"]) + R
                         + F.join(["BTR", "101", "ITEM2", "40", "EA", "MAIN", "DEPT0001", "200", "20261031", "1"]),
                "jsStat": f"11{F}Backorder{R}40{F}Picking Slip printed", "jsTer": "",
                "jsComp": f"BTR{F}PT Batutua Tembaga Raya{F}#123456", "jsProj": f"BTR|100{F}W1{F}Repair pump",
                "jsItems": f"ITEM1{F}Filter{R}ITEM2{F}Gasket"},
    "detail": {"jsRaw": F.join(["BTR", "100", "1", "SN", "ITEM1", "EA", "W1", "2", "0", "2"]),
               "jsOrd": F.join(["BTR|100", "BTR - 100", "DEPT0001", "20261030", "20261029", "20261105", "11", "MAIN"]),
               "jsStk": F.join(["BTR|ITEM1|MAIN", "5", "1", "10"]), "jsDesc": f"BTR|ITEM1{F}Filter",
               "jsJob": f"BTR|W1{F}In Progress{F}Repair pump", "jsStat": f"11{F}Backorder", "jsTer": "",
               "jsComp": f"BTR{F}PT Batutua Tembaga Raya{F}#123456", "jsProj": ""},
}


@pytest.fixture
def fake_data(monkeypatch):
    def load(page):
        return lambda: ({**FAKE[page], "totalMasterCompCount": 1, "jsPbiFilters": ""}, 0)
    monkeypatch.setattr(queries, "summary", load("summary"))
    monkeypatch.setattr(queries, "detail", load("detail"))


def test_tools_answer_from_page_data(fake_data):
    args = tools.clean_args({"company": "batutua tembaga", "status": "backorder"})
    assert args == {"company": "BTR", "status": "Backorder"}
    s = tools.tool_status_summary(args, {})
    assert s["total"] == {"picking_slips": 1, "lines": 2, "amount": 1500.5}
    assert tools.tool_top_items({}, {})["items"][0] == {"item": "ITEM1", "description": "Filter", "amount": 1500.5,
                                                         "lines": 2, "picking_slips": 1}
    latest = tools.tool_find_picking_slips({}, {})["picking_slips"]
    assert [p["ps_number"] for p in latest] == ["101", "100"] and latest[1]["wo_number"] == "W1"
    d = tools.tool_picking_slip_detail({"ps_number": "100"}, {})
    assert d["found"] and d["status"] == "Backorder" and d["lines"][0]["qty_on_hand"] == 5.0
    assert tools.tool_picking_slip_detail({"ps_number": "999"}, {})["found"] is False


def test_tools_reject_unknown_values(fake_data):
    with pytest.raises(ToolArgError):
        tools.clean_args({"status": "tidak ada"})
    with pytest.raises(ToolArgError):
        tools.clean_args({"start": "kemarin"})
