"""Pertanyaan acuan untuk python scripts/check_ai_agent.py --dashboard pani-processing

Jawaban acuan dihitung dari queries/tools saat tes dijalankan. Format kasus: lihat dashboards/_template/chat_cases.py.
"""
import re
from datetime import date

from . import queries


def numbers(text):
    """Angka di jawaban tanpa pemisah ribuan, dibulatkan: '48.648,15' / '48,648.15' -> 48648."""
    found = set()
    for n in re.findall(r"\d[\d.,]*", text):
        digits = re.sub(r"[.,](\d{1,2})$", "", n)          # buang desimal 1-2 digit di akhir
        digits = re.sub(r"[.,]", "", digits)
        if digits:
            found.add(int(digits))
    return found


def _names(used):
    return [u["name"] for u in used]


def case_gold_ytd():
    b = queries.processing_bounds()
    end = b["last"]
    gold = queries.processing(date(end.year, 1, 1), end)[0]["gold"]
    filters = {"start": f"{end.year}-01-01", "end": end.isoformat()}

    def checks(answer, used):
        nums = numbers(answer)
        return [("memakai get_processing_metrics / get_variance_drivers",
                 any(n in _names(used) for n in ("get_processing_metrics", "get_variance_drivers"))),
                (f"actual YTD ~ {gold['actual']:,.0f}", int(gold["actual"]) in nums or round(gold["actual"]) in nums),
                (f"target YTD ~ {gold['target']:,.0f}", int(gold["target"]) in nums or round(gold["target"]) in nums)]
    return {"question": "Berapa gold produced YTD dan targetnya?", "filters": filters,
            "context": f"Halaman Processing Report; rentang {filters['start']} s/d {filters['end']}", "checks": checks}


def case_drivers():
    end = queries.processing_bounds()["last"]
    drivers = queries.processing(date(end.year, 1, 1), end)[0]["drivers"]
    if not drivers:
        return {"skip": "tidak ada variance negatif"}

    def checks(answer, used):
        return [("memakai get_variance_drivers", "get_variance_drivers" in _names(used)),
                (f"menyebut driver teratas '{drivers[0]['label']}'", drivers[0]["label"].split(" (")[0].lower() in answer.lower())]
    return {"question": "Apa 5 penyebab variance negatif terbesar tahun ini?", "filters": {}, "context": "", "checks": checks}


def case_equipment_day():
    day = date(2026, 8, 1)
    data = queries.equipment(day, day)[0]

    def checks(answer, used):
        nums = numbers(answer)
        return [("memakai get_equipment", "get_equipment" in _names(used)),
                (f"unit aktif {data['active']}", data["active"] in nums),
                (f"unit nonaktif {data['inactive']}", data["inactive"] in nums)]
    return {"question": "Berapa unit equipment yang aktif dan tidak aktif pada 1 Agustus 2026?", "filters": {}, "context": "",
            "checks": checks}


def case_mining_mtd():
    start, end = date(2026, 8, 1), date(2026, 8, 3)
    mined = queries.mining(start, end)[0]["periods"]["mtd"]["mined"]
    filters = {"start": start.isoformat(), "end": end.isoformat()}

    def checks(answer, used):
        nums = numbers(answer)
        return [("memakai get_mining", "get_mining" in _names(used)),
                (f"total mined MTD {mined['actual']:,.0f}", round(mined["actual"]) in nums),
                (f"plan {mined['plan']:,.0f}", round(mined["plan"]) in nums)]
    return {"question": "Bagaimana total mined MTD dibanding plan?", "filters": filters,
            "context": f"Halaman Mining Production Report; rentang {filters['start']} s/d {filters['end']}", "checks": checks}


def case_out_of_scope():
    def checks(answer, used):
        return [("tidak memanggil tool", not used), ("menolak dengan sopan", "pani" in answer.lower())]
    return {"question": "Berapa harga emas dunia hari ini?", "filters": {}, "context": "", "checks": checks}


CASES = [case_gold_ytd, case_drivers, case_equipment_day, case_mining_mtd, case_out_of_scope]
