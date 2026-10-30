"""Pertanyaan acuan untuk python scripts/check_ai_agent.py --dashboard __SLUG__

Setiap fungsi case_<nama>() mengembalikan dict:
    question  : pertanyaan ke agent
    filters   : filter dashboard aktif (seperti dikirim browser), mis. {"year": 2026, "month": 10}
    context   : teks filter aktif (boleh "")
    checks    : fungsi (answer, used) -> list (label, lulus?)
atau {"skip": "alasan"}. Hitung jawaban acuan dari queries/tools saat tes, jangan ditulis manual.
"""
from . import tools


def case_tables():
    expected = tools.tool_tables({}, {})["tables"]

    def checks(answer, used):
        return [("memakai get_tables", any(u["name"] == "get_tables" for u in used)),
                ("menyebut tabel pertama", not expected or expected[0] in answer)]
    return {"question": "Tabel apa saja yang ada di semantic model ini?", "filters": {}, "context": "", "checks": checks}


CASES = [case_tables]
