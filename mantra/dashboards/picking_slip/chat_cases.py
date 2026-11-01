"""Pertanyaan acuan untuk python scripts/check_ai_agent.py --dashboard picking-slip

Jawaban acuan dihitung dari queries/tools saat tes dijalankan. Format kasus: lihat dashboards/_template/chat_cases.py.
"""
import re

from . import tools


def numbers(text):
    """Angka di jawaban tanpa pemisah ribuan, dibulatkan: '1.531' / '1,531' / '72,536,794.41' -> 1531 / 72536794."""
    found = set()
    for n in re.findall(r"\d[\d.,]*", text):
        digits = re.sub(r"[.,](\d{1,2})$", "", n)          # buang desimal 1-2 digit di akhir
        digits = re.sub(r"[.,]", "", digits)
        if digits:
            found.add(int(digits))
    return found


def _names(used):
    return [u["name"] for u in used]


def case_backorder_count():
    card = next(c for c in tools.tool_status_summary({}, {})["kpi_cards"] if c["card"] == "Backorder")

    def checks(answer, used):
        return [("memakai get_status_summary", "get_status_summary" in _names(used)),
                (f"jumlah picking slip backorder = {card['picking_slips']:,}", card["picking_slips"] in numbers(answer))]
    return {"question": "Berapa jumlah picking slip yang backorder?", "filters": {"page": "Picking Slip Summary"},
            "context": "Halaman Picking Slip Summary; semua company", "checks": checks}


def case_top_item():
    top = tools.tool_top_items({"limit": 5}, {})["items"][0]

    def checks(answer, used):
        return [("memakai get_top_items", "get_top_items" in _names(used)),
                (f"menyebut item teratas {top['item']}", top["item"] in answer)]
    return {"question": "Apa 5 item dengan amount picking slip terbesar?", "filters": {"page": "Picking Slip Summary"},
            "context": "Halaman Picking Slip Summary; semua company", "checks": checks}


def case_ps_detail():
    lines = tools.queries.detail_records()[0]
    sample = lines[0]
    rows = [r for r in lines if r["company"] == sample["company"] and r["ps_number"] == sample["ps_number"]]

    def checks(answer, used):
        return [("memakai get_picking_slip_detail", "get_picking_slip_detail" in _names(used)),
                (f"menyebut item {rows[0]['item']}", rows[0]["item"] in answer),
                (f"menyebut status {sample['status']}", sample["status"].lower() in answer.lower())]
    return {"question": f"Apa isi picking slip {sample['ps_number']} di {sample['company']}?",
            "filters": {"page": "Picking Slip Detail"}, "context": "Halaman Picking Slip Detail", "checks": checks}


def case_out_of_scope():
    def checks(answer, used):
        return [("tidak memanggil tool", not used), ("menolak dengan sopan", "picking" in answer.lower())]
    return {"question": "Berapa harga emas dunia hari ini?", "filters": {}, "context": "", "checks": checks}


CASES = [case_backorder_count, case_top_item, case_ps_detail, case_out_of_scope]
