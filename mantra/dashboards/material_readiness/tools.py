"""Tools AI agent Material Readiness. Setiap tool menjalankan query lewat queries.py ke semantic model.

Aturan menjawab dan kamus data ada di prompts/*.md. Mesin agent (loop AI, provider, pengaman) ada di core/chat/.
"""
from ...core.chat.guards import ToolArgError, resolve, resolve_week
from ...core.registry import Tool
from . import queries

FILTER_PROPS = {
    "type": {"type": "string", "enum": ["PO", "SO"],
             "description": "PO = Material/Work Order PO Readiness, SO = Material/Work Order SO Readiness. Default PO."},
    "year": {"type": "integer", "description": "Tahun Start Date, mis. 2026. Kosongkan untuk semua tahun."},
    "month": {"type": "integer", "description": "Bulan Start Date 1-12. Kosongkan untuk semua bulan."},
    "company": {"type": "string", "description": "Nama company (lihat kamus data) atau kodenya, mis. MMI."},
    "plant": {"type": "string", "description": "Kode plant (Plant_No) persis, mis. HT018."},
    "warehouse": {"type": "string", "description": "Kode warehouse persis, mis. WSPC."},
    "status": {"type": "string", "description": "Status legend persis. PO: FP Ready, FP In Progress, FP Approval, "
                                                "FP Not Ready. SO: All Ready, All Inprogress, All Not Ready, On Hold."},
    "week": {"type": "string", "description": "Week category persis, format '44 - 2026'."},
    "doc": {"type": "string", "description": "Document No (Doc_No) persis, mis. 193221."},
    "search": {"type": "string", "description": "Teks yang dicari di job code, deskripsi job, stock code, doc no, plant."},
}

ROW_COLUMNS = ["company_name", "job_code", "job_desc", "start_date", "schedule_date", "plant_no", "plant_desc",
               "doc_no", "warehouse", "stock_code", "qty_order"]


def _schema(extra=None, required=None):
    props = dict(FILTER_PROPS)
    props.update(extra or {})
    return {"type": "object", "properties": props, "required": required or []}


CHART_PROPS = {k: FILTER_PROPS[k] for k in ("type", "year", "month", "company", "week", "status")}
CHART_PROPS["measure"] = {
    "type": "string", "enum": ["material", "work_order"],
    "description": "material = count QTY_Order (chart 'ALL Material ... Readiness'), "
                   "work_order = count Job_Code (chart 'ALL Work Order ... Readiness'). Default material.",
}
CHART_PROPS["all_months"] = {
    "type": "boolean",
    "description": "true hanya kalau user eksplisit minta semua bulan / seluruh week. Default: periode kosong "
                   "mengikuti filter bulan yang aktif di dashboard, sama seperti chart.",
}


def _filters(args):
    return queries.parse_filters({
        "type": args.get("type") or "PO",
        "tm": "0",
        "year": args.get("year"),
        "month": args.get("month"),
        "company": args.get("company"),
        "plant": args.get("plant"),
        "warehouse": args.get("warehouse"),
        "status": args.get("status"),
        "week": args.get("week"),
        "doc": args.get("doc"),
        "q": args.get("search"),
        "sort": args.get("sort_by"),
        "dir": "desc" if args.get("descending") else "asc",
    })


def _limit(args, default):
    try:
        return max(1, min(int(args.get("limit") or default), 30))
    except (TypeError, ValueError):
        return default


def _pct(n, total):
    return round(n / total * 100, 1) if total else 0.0


def tool_chart(args, dash):
    """Hitung dari data chart Summary (summary_cube), jadi angkanya sama dengan yang tampil di chart."""
    t = 1 if (args.get("type") or "PO").upper() == "SO" else 0
    idx = 6 if args.get("measure") == "work_order" else 5
    year, month = queries._int(args.get("year")), queries._int(args.get("month"))
    company = args.get("company") or ""
    company = "" if company == queries.NO_COMPANY else company
    week, status = args.get("week") or "", args.get("status") or ""

    # Periode kosong ikut filter dashboard, sama seperti chart (kecuali user minta semua bulan)
    applied_dashboard_period = False
    if not args.get("all_months") and month is None and dash.get("month") is not None:
        if week or year is None:
            year, month = dash.get("year"), dash["month"]
            applied_dashboard_period = True

    def keep(r, with_month=True):
        return (r[0] == t and (year is None or r[3] == year) and (not with_month or month is None or r[4] == month)
                and (not args.get("company") or r[7] == company) and (not week or r[2] == week)
                and (not status or r[1] == status))

    cube, _ = queries.summary_cube()
    by_status = {}
    for r in cube:
        if keep(r):
            by_status[r[1]] = by_status.get(r[1], 0) + r[idx]
    total = sum(by_status.values())
    result = {
        "total": total,
        "by_status": {s: {"count": n, "pct": _pct(n, total)}
                      for s, n in sorted(by_status.items(), key=lambda kv: queries.status_rank(kv[0]))},
        "filters_applied": {"type": "SO" if t else "PO", "year": year, "month": month, "company": args.get("company"),
                            "week": week or None, "status": status or None},
        "measure": "count Job_Code" if idx == 6 else "count QTY_Order",
    }
    if week:
        # Satu week bisa melintasi dua bulan Start Date: laporkan bagian di bulan lain
        others = {}
        for r in cube:
            if month is not None and keep(r, with_month=False) and r[4] != month:
                key = f"{r[3]}-{r[4]:02d}"
                others[key] = others.get(key, 0) + r[idx]
        others = dict(sorted(others.items()))
        if others:
            result["same_week_other_months"] = others
            result["note"] = (f"Week {week} juga punya {sum(others.values())} data dengan Start Date di bulan lain "
                              f"({', '.join(f'{k}: {n}' for k, n in others.items())}); tidak termasuk di total ini"
                              + (" karena mengikuti filter bulan dashboard." if applied_dashboard_period else "."))
    elif applied_dashboard_period:
        result["note"] = "Periode mengikuti filter bulan yang aktif di dashboard."
    return result


def tool_kpi(args, dash):
    k, tabs = queries.kpi(_filters(args))
    return {**k, "pct_ready": _pct(k["ready"], k["total"]), "pct_not_ready": _pct(k["not_ready"], k["total"]),
            "rows_per_type": tabs}


GROUP_BY = ["status", *queries.BREAKDOWN_COLUMNS]


def tool_breakdown(args, dash):
    group_by = str(args.get("group_by") or "status").strip().lower()
    if group_by not in GROUP_BY:
        raise ToolArgError("group_by", group_by, GROUP_BY)
    rows = queries.breakdown(_filters(args), group_by, _limit(args, 10))
    for r in rows:
        if r.get("qty_order") is not None:
            r["qty_order"] = round(r["qty_order"], 2)
    return {"groups": rows}


def tool_rows(args, dash):
    f = _filters(args)
    rows = queries.detail_rows(f)
    cols = ROW_COLUMNS + (["received_date", "po_legend"] if f["type"] == "PO" else ["so_status_desc", "so_legend"])
    result = {"total_rows": len(rows), "rows": [{c: r.get(c) for c in cols} for r in rows[:_limit(args, 15)]]}
    if len(rows) >= queries.DETAIL_LIMIT:
        # Baris yang dimuat dibatasi DETAIL_LIMIT, jadi len(rows) bukan jumlah sebenarnya
        result["total_rows"] = queries.kpi(f)[0]["total"]
        result["note"] = f"Contoh baris diambil dari {queries.DETAIL_LIMIT:,} baris pertama sesuai urutan."
    return result


def _blank(value):
    return str(value or "").strip() in ("", "(Blank)")


def _ym_label(ym):
    ym = queries._int(ym) or 0
    return f"{ym // 100}-{ym % 100:02d}" if ym else "tanpa Start Date"


def tool_lookup(args, dash):
    """Cari Job Code / Doc No / Stock Code di semua branch, plus alasan kenapa data ini tampil / tidak di dashboard."""
    field = args.get("field") or "job_code"
    value = str(args.get("value") or "").strip()[:50]
    if field not in queries.LOOKUP_FIELDS or not value:
        return {"error": "field dan value wajib diisi"}
    data = queries.lookup(field, value)
    if not data["status"]:
        return {"found": False, "note": f"{value} tidak ada di semantic model (semua branch sudah dicek)."}

    shown_branches = set(queries.BRANCHES)
    per_branch, by_type, blank_rows = {}, {}, 0
    for r in data["status"]:
        branch, type_, n = r["branch_code"] or "(kosong)", r["Type"] or "(kosong)", int(r["rows"] or 0)
        status = r["PO_Status Description"] if type_ == "PO" else r["Status SO Description"]
        legend = r["PO Legend Description"] if type_ == "PO" else r["SO Legend Description"]
        per_branch[branch] = per_branch.get(branch, 0) + n
        t = by_type.setdefault(type_, {"rows": 0, "status_description": {}, "legend": {}})
        t["rows"] += n
        t["status_description"][status or "(kosong)"] = t["status_description"].get(status or "(kosong)", 0) + n
        t["legend"][legend or "(kosong)"] = t["legend"].get(legend or "(kosong)", 0) + n
        if branch in shown_branches:
            # Dashboard (Summary & Detail) hanya menampilkan baris yang status, legend dan week-nya terisi
            blank_rows += n if _blank(status) or _blank(legend) else int(r["no_week"] or 0)
    for t in by_type.values():
        t["status_description"] = dict(sorted(t["status_description"].items(), key=lambda kv: -kv[1]))
        t["legend"] = dict(sorted(t["legend"].items(), key=lambda kv: -kv[1]))

    total = sum(per_branch.values())
    in_branch = sum(n for b, n in per_branch.items() if b in shown_branches)
    other = {b: n for b, n in per_branch.items() if b not in shown_branches}
    other_txt = ", ".join(f"{b} ({n} baris)" for b, n in other.items())
    dash_txt = "branch " + " & ".join(queries.BRANCHES)

    notes = []
    if not in_branch:
        notes.append(f"Semua {total} baris {value} ada di branch {other_txt}. Dashboard (Summary & Detail) hanya "
                     f"menampilkan {dash_txt}, sama seperti report Power BI aslinya, jadi {value} tidak akan muncul "
                     f"di dashboard. Jawaban ini dibaca langsung dari tabel semantic model.")
    elif other:
        notes.append(f"{in_branch} dari {total} baris ada di {dash_txt}. {total - in_branch} baris lainnya ada di "
                     f"branch {other_txt}, yang tidak ditampilkan dashboard.")
    if blank_rows:
        notes.append(f"{blank_rows} baris di {dash_txt} status atau week category-nya kosong, jadi tidak ditampilkan "
                     f"di dashboard (Summary maupun Detail).")

    periods = {}
    in_period = 0
    year, month = dash.get("year"), dash.get("month")
    for r in data["periods"]:
        n, ym = int(r["rows"] or 0), queries._int(r["Start Year Month No"]) or 0
        label = _ym_label(ym)
        periods[label] = periods.get(label, 0) + n
        if r["branch_code"] in shown_branches and ym and (year is None or ym // 100 == year) \
                and (month is None or ym % 100 == month):
            in_period += n
    if in_branch and (year is not None or month is not None) and in_period < in_branch:
        active = f"{month:02d}/{year}" if year and month else (str(year) if year else f"bulan {month}")
        notes.append(f"{in_branch - in_period} dari {in_branch} baris di {dash_txt} punya Start Date di luar periode "
                     f"filter dashboard yang sedang aktif ({active}), jadi baru terlihat setelah filter Year/Month "
                     f"diubah (matikan This Month bila aktif).")

    result = {
        "found": True,
        "field": field,
        "value": value,
        "total_rows": total,
        "rows_per_branch": per_branch,
        "rows_shown_in_dashboard": in_branch - blank_rows,
        "types": by_type,
        "start_periods": dict(sorted(periods.items())),
        # Satu kelompok = kombinasi job / plant / company / branch / status yang benar-benar ada di data
        "detail_groups": [{
            "job_code": r["Job_Code"], "job_desc": r["Job_Code_Desc"], "plant_no": r["Plant_No"],
            "plant_desc": r["Plant_Desc"], "company": r["Company"], "branch": r["branch_code"], "type": r["Type"],
            "status_description": r["PO_Status Description"] if r["Type"] == "PO" else r["Status SO Description"],
            "rows": int(r["rows"] or 0),
        } for r in data["info"]],
        "dashboard_notes": notes,
    }
    if len(data["info"]) >= queries.LOOKUP_GROUPS:
        result["note"] = f"detail_groups hanya berisi {queries.LOOKUP_GROUPS} kelompok terbesar."
    return result


TOOLS = [
    Tool("lookup", "Lookup (all branches)",
         "Cari satu Job Code (work order), Doc No, atau Stock Code tertentu di SEMUA branch, termasuk yang tidak tampil "
         "di dashboard. Mengembalikan Type, branch, PO_Status Description / Status SO Description beserta jumlah baris, "
         "legend, periode Start Date, job/plant/company, dan dashboard_notes yang menjelaskan kenapa data ini tampil "
         "atau tidak tampil di dashboard.",
         {"type": "object", "properties": {
             "field": {"type": "string", "enum": list(queries.LOOKUP_FIELDS),
                       "description": "job_code untuk work order (mis. W0417321), doc_no, atau stock_code."},
             "value": {"type": "string", "description": "Nilai persis yang dicari, mis. W0417321."},
         }, "required": ["field", "value"]},
         tool_lookup),
    Tool("get_chart_totals", "Totals (chart logic)",
         "Total per status dengan logika yang SAMA PERSIS dengan chart di halaman Summary (hanya baris yang status dan "
         "week-nya terisi). Juga mengembalikan pembagian per bulan Start Date, berguna kalau satu week melintasi dua "
         "bulan. Pakai ini untuk semua pertanyaan total/jumlah.",
         {"type": "object", "properties": CHART_PROPS, "required": []},
         tool_chart),
    Tool("get_readiness_kpi", "Detail KPIs",
         "KPI halaman Detail (aturan baris sama dengan chart Summary): jumlah per status, rata-rata schedule lead time "
         "(hari), dan jumlah baris PO vs SO. Bisa difilter plant/warehouse/search.",
         _schema(), tool_kpi),
    Tool("get_breakdown", "Breakdown",
         "Jumlah baris per kelompok (urut dari terbanyak) beserta pecahan ready / not_ready / in_progress / approval "
         "dan total QTY order. Pakai untuk pertanyaan 'plant/company/week mana yang paling ...'.",
         _schema({
             "group_by": {"type": "string", "enum": GROUP_BY},
             "limit": {"type": "integer", "description": "Jumlah kelompok teratas, 1-30. Default 10."},
         }, required=["group_by"]),
         tool_breakdown),
    Tool("get_rows", "Detail rows",
         "Contoh baris detail (item material) sesuai filter, maksimal 30 baris.",
         _schema({
             "sort_by": {"type": "string", "enum": ["start_date", "schedule_date", "qty_order", "plant_no", "doc_no"]},
             "descending": {"type": "boolean"},
             "limit": {"type": "integer", "description": "1-30. Default 15."},
         }),
         tool_rows),
]


def clean_args(args):
    """Normalkan type / status / company / week dari AI ke nilai asli di data sebelum query dijalankan."""
    args = dict(args)
    if args.get("type"):
        args["type"] = str(args["type"]).strip().upper()
        if args["type"] not in queries.VIEWS:
            raise ToolArgError("type", args["type"], list(queries.VIEWS))
    if not any(args.get(k) for k in ("status", "company", "week")):
        return args
    cube, _ = queries.summary_cube()
    t = 1 if args.get("type") == "SO" else 0
    if args.get("status"):
        args["status"] = resolve("status", args["status"], {r[1] for r in cube if r[0] == t})
    if args.get("company"):
        company = str(args["company"]).strip()
        company = queries.company_names().get(company.upper(), company)  # kode company, mis. MMI
        args["company"] = resolve("company", company, set(queries.company_logos()) | {queries.NO_COMPANY})
    if args.get("week"):
        args["week"] = resolve_week(args["week"], {r[2] for r in cube})
    return args


def parse_dash(raw):
    """Filter dashboard aktif dari browser: {year, month, company}."""
    raw = raw if isinstance(raw, dict) else {}
    month = queries._int(raw.get("month"))
    return {"year": queries._int(raw.get("year")), "month": month if month and 1 <= month <= 12 else None,
            "company": str(raw.get("company") or "")[:100] or None}


def prompt_values():
    return {"branches": " & ".join(queries.BRANCHES), "companies": ", ".join(sorted(queries.company_logos())) or "-"}


SUGGESTIONS = [
    "What percentage of PO is ready this month?",
    "Which plant has the most FP In Progress this month?",
    "Compare SO readiness per company in 2026",
    "What is the status of work order W0417321?",
]
