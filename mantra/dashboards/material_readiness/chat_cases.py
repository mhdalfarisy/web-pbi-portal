"""Pertanyaan acuan untuk python scripts\\check_ai_agent.py --dashboard material-readiness

Jawaban acuan dihitung dari tools/queries saat tes dijalankan, jadi tes tetap valid walaupun datanya berubah.
Format setiap kasus dijelaskan di dashboards/_template/chat_cases.py.
"""
import re

from ...core.chat.prompt import MONTHS_ID
from . import queries, tools

SITE_JOB = "W0417321"  # work order contoh di branch SITE (tidak tampil di dashboard)


def numbers(text):
    """Semua bilangan bulat di jawaban, tanpa pemisah ribuan: '98.597' / '98,597' -> 98597."""
    return {int(re.sub(r"[.,]", "", n)) for n in re.findall(r"\d{1,3}(?:[.,]\d{3})+(?![.,]?\d)|\d+", text)}


def _names(used):
    return [u["name"] for u in used]


def _this_month():
    now = queries.now_wib()
    filters = {"year": now.year, "month": now.month, "company": None}
    context = (f"Halaman Summary; periode This Month ({MONTHS_ID[now.month - 1]} {now.year}) "
               f"(year={now.year}, month={now.month}); company: semua")
    return filters, context


def case_lookup_site_job():
    truth = tools.tool_lookup({"field": "job_code", "value": SITE_JOB}, {})
    if not truth.get("found"):
        return {"skip": f"{SITE_JOB} sudah tidak ada di semantic model, ganti SITE_JOB"}
    statuses = {s: n for t in truth["types"].values() for s, n in t["status_description"].items()}
    types_ = list(truth["types"])

    def checks(answer, used):
        nums = numbers(answer)
        out = [("memakai lookup", "lookup" in _names(used)),
               (f"menyebut type {types_}", all(t in answer for t in types_)),
               ("menjelaskan branch SITE (alasan tidak tampil di dashboard)", "SITE" in answer)]
        out += [(f"status '{s}' = {n}", s in answer and n in nums) for s, n in statuses.items()]
        return out
    return {"question": f"apa type dari work order {SITE_JOB} dan apa PO_Status Description nya ?",
            "filters": {}, "context": "", "checks": checks}


def case_lookup_not_found():
    def checks(answer, used):
        return [("memakai lookup", "lookup" in _names(used)),
                ("menyatakan tidak ditemukan", "tidak" in answer.lower())]
    return {"question": "apa status work order ZZ99999999?", "filters": {}, "context": "", "checks": checks}


def case_chart_total_this_month():
    filters, context = _this_month()
    truth = tools.tool_chart({"type": "PO"}, tools.parse_dash(filters))

    def checks(answer, used):
        nums = numbers(answer)
        out = [("memakai get_chart_totals", "get_chart_totals" in _names(used)),
               (f"total = {truth['total']}", truth["total"] in nums)]
        out += [(f"{s} = {v['count']}", v["count"] in nums) for s, v in truth["by_status"].items()]
        return out
    return {"question": "Berapa total material PO bulan ini per status?", "filters": filters, "context": context,
            "checks": checks}


def case_status_alias_so():
    filters, context = _this_month()
    truth = tools.tool_chart({"type": "SO", "status": "All Not Ready"}, tools.parse_dash(filters))["total"]

    def checks(answer, used):
        return [("memakai get_chart_totals", "get_chart_totals" in _names(used)),
                (f"angka = {truth}", truth in numbers(answer))]
    return {"question": "Berapa item SO yang not ready bulan ini?", "filters": filters, "context": context,
            "checks": checks}


def case_company_code():
    filters, context = _this_month()
    name = queries.company_names().get("MMI")
    if not name:
        return {"skip": "kode company MMI tidak ada di DWMasterIconCompany"}
    truth = tools.tool_chart({"type": "PO", "company": name}, tools.parse_dash(filters))["total"]

    def checks(answer, used):
        args = [u["args"] for u in used if u["name"] == "get_chart_totals"]
        return [("memakai get_chart_totals", bool(args)),
                (f"company dinormalkan ke '{name}'", any(a.get("company") == name for a in args)),
                (f"total = {truth}", truth in numbers(answer))]
    return {"question": "Berapa total material PO bulan ini untuk MMI?", "filters": filters, "context": context,
            "checks": checks}


def case_breakdown_plant():
    year = queries.now_wib().year
    groups = tools.tool_breakdown({"type": "PO", "status": "FP Not Ready", "year": year, "group_by": "plant"}, {})["groups"]
    if not groups:
        return {"skip": f"tidak ada FP Not Ready di tahun {year}"}
    top = groups[0]

    def checks(answer, used):
        return [("memakai get_breakdown", "get_breakdown" in _names(used)),
                (f"plant teratas {top['plant_no']} ({top['rows']} baris)",
                 top["plant_no"] in answer and top["rows"] in numbers(answer))]
    return {"question": f"Plant mana yang paling banyak FP Not Ready di tahun {year}?", "filters": {}, "context": "",
            "checks": checks}


def case_out_of_scope():
    def checks(answer, used):
        return [("tidak memanggil tool", not used),
                ("menolak dengan sopan", "material readiness" in answer.lower())]
    return {"question": "Siapa presiden pertama Indonesia?", "filters": {}, "context": "", "checks": checks}


def case_unavailable_column():
    def checks(answer, used):
        low = answer.lower()
        return [("menyatakan data belum tersedia", "belum" in low or "tidak tersedia" in low)]
    return {"question": f"Work order {SITE_JOB} dikerjakan oleh section apa?", "filters": {}, "context": "",
            "checks": checks}


CASES = [case_lookup_site_job, case_lookup_not_found, case_chart_total_this_month, case_status_alias_so,
         case_company_code, case_breakdown_plant, case_out_of_scope, case_unavailable_column]
