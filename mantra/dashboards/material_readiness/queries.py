"""Query dashboard Material Readiness langsung ke semantic model Power BI (executeQueries), dengan cache di memori.

Semantic model "All Site - AMNT - Material Readiness" memakai mode Import dengan refresh terjadwal harian 09:00 WIB,
jadi data sesegar refresh terakhir dataset.
"""
import csv
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from ...config import Config
from ...core.cache import Cache
from ...core.powerbi import DATA_ERRORS, Dataset, query  # noqa: F401  (DATA_ERRORS dipakai routes.py)

# ID bisa ditimpa lewat .env: MATERIAL_READINESS_WORKSPACE_ID / MATERIAL_READINESS_DATASET_ID
DATASET = Dataset("MATERIAL_READINESS", workspace_id="076fb2d0-f8c2-44c9-8e6f-3cd3f8aa103c",
                  dataset_id="6dfa0b74-c265-4d2c-8643-fd6ea1797a8e")
BRANCHES = ("FP", "ME")  # branch yang tampil di dashboard, sama seperti report Power BI aslinya
DETAIL_LIMIT = 15_000    # batas baris tabel Detail per filter (KPI tetap dihitung dari semua baris)

WIB = timezone(timedelta(hours=7))
NO_COMPANY = "Unidentified"
PAGE_SIZES = (25, 50, 100, 200)
FILTER_KEYS = ("type", "year", "month", "company", "plant", "warehouse", "status", "doc", "week", "q")

T = "'DWMaterialReadiness'"
C = "'DWMasterIconCompany'"


def dax_str(value):
    return '"' + str(value).replace('"', '""') + '"'


BRANCH = f"TREATAS({{{', '.join(dax_str(b) for b in BRANCHES)}}}, {T}[branch_code])"
LEGEND = {"PO": f"{T}[PO Legend Description]", "SO": f"{T}[SO Legend Description]"}
STATUS_DESC = {"PO": "PO_Status Description", "SO": "Status SO Description"}
SEARCH_TEXT = " & \"|\" & ".join(f"{T}[{c}]" for c in ("Job_Code", "Job_Code_Desc", "Stock_Code", "Doc_No", "Plant_No", "Plant_Desc"))

COLUMNS = {
    "company_name": ("Company", "text", f"RELATED({C}[Company Name])"),
    "job_code": ("Job Code", "text", f"{T}[Job_Code]"),
    "job_desc": ("Job Code Description", "text", f"{T}[Job_Code_Desc]"),
    "start_date": ("Start Date", "date", f"{T}[Start_Date]"),
    "schedule_date": ("Schedule Date", "date", f"{T}[Schedule_Date]"),
    "plant_no": ("Plant No", "text", f"{T}[Plant_No]"),
    "plant_desc": ("Plant Description", "text", f"{T}[Plant_Desc]"),
    "type": ("Type", "type", f"{T}[Type]"),
    "doc_no": ("Document No", "text", f"{T}[Doc_No]"),
    "doc_suffix": ("Document Suffix", "text", f"{T}[Doc_Suffix]"),
    "warehouse": ("Warehouse", "text", f"{T}[Warehouse]"),
    "po_status": ("PO Status", "text", f"{T}[PO_Status]"),
    "so_status": ("SO Status", "text", f"{T}[SO_Status]"),
    "so_status_desc": ("SO Status Description", "text", f"{T}[Status SO Description]"),
    "stock_code": ("Stock Code", "text", f"{T}[Stock_Code]"),
    "qty_order": ("QTY Order", "number", f"{T}[QTY_Order]"),
    "received_date": ("Received Date", "date", f"{T}[Received_Date]"),
    "po_legend": ("PO Legend Description", "status", LEGEND["PO"]),
    "so_legend": ("SO Legend Description", "status", LEGEND["SO"]),
}
_COMMON = ["company_name", "job_code", "job_desc", "start_date", "schedule_date", "plant_no", "plant_desc", "type",
           "doc_no", "doc_suffix", "warehouse"]
VIEWS = {
    "PO": _COMMON + ["po_status", "stock_code", "qty_order", "received_date", "po_legend"],
    "SO": _COMMON + ["so_status", "so_status_desc", "stock_code", "qty_order", "so_legend"],
}


_pool = ThreadPoolExecutor(max_workers=4)
_cache = Cache(Config.CACHE_SECONDS)


def _query(dax):
    """Jalankan DAX ke semantic model dashboard ini, kembalikan list of dict."""
    return query(DATASET, dax)


def now_wib():
    return datetime.now(WIB)


def stamp_info(ts):
    dt = datetime.fromtimestamp(ts, WIB)
    return {"date": dt.strftime("%d/%m/%Y"), "time": dt.strftime("%H:%M WIB")}


def status_rank(status):
    """Urutan status seperti di Power BI: Approval -> In Progress -> Not Ready -> Ready."""
    s = (status or "").lower()
    if "approv" in s:
        return 1
    if "progress" in s:
        return 2
    if "not" in s:
        return 3
    if "ready" in s:
        return 4
    return 9


_CUBE_PART = """SELECTCOLUMNS(
    GROUPBY(
        ADDCOLUMNS(
            FILTER(_base,
                VAR st = TRIM({T}[{desc}] & "")
                VAR lg = TRIM({legend} & "")
                RETURN st <> "" && st <> "(Blank)" && lg <> "" && lg <> "(Blank)"
                    && TRIM({T}[dax_week_category_year] & "") <> ""),
            "@S", TRIM({legend} & ""),
            "@W", TRIM({T}[dax_week_category_year] & ""),
            "@Y", IF(ISBLANK({T}[Start_Date]), 0, YEAR({T}[Start_Date])),
            "@M", IF(ISBLANK({T}[Start_Date]), 0, MONTH({T}[Start_Date])),
            "@C", TRIM(RELATED({C}[Company Name]) & "")),
        [@S], [@W], [@Y], [@M], [@C],
        "@Q", COUNTX(CURRENTGROUP(), {T}[QTY_Order]),
        "@J", COUNTX(CURRENTGROUP(), {T}[Job_Code])),
    "t", {t}, "s", [@S], "w", [@W], "y", [@Y], "m", [@M], "q", [@Q], "j", [@J], "c", [@C])"""


def summary_cube():
    """Sama dengan poCube/soCube di measure v16: [tipe, status, week, tahun, bulan, count qty, count job, company]."""
    def load():
        po = _CUBE_PART.format(T=T, C=C, t=0, desc=STATUS_DESC["PO"], legend=LEGEND["PO"])
        so = _CUBE_PART.format(T=T, C=C, t=1, desc=STATUS_DESC["SO"], legend=LEGEND["SO"])
        rows = _query(f"DEFINE VAR _base = CALCULATETABLE({T}, {BRANCH})\nEVALUATE UNION({po}, {so})")
        return [[int(r["t"]), r["s"], r["w"], int(r["y"]), int(r["m"]), int(r["q"] or 0), int(r["j"] or 0), r["c"] or ""]
                for r in rows]
    return _cache.get("cube", load)


def company_logos():
    """company name -> [logo group, logo company, warna group]."""
    def fix(url):

        return (url or "").replace("i.ibb.co/", "i.ibb.co.com/")

    def load():
        rows = _query(f'EVALUATE SELECTCOLUMNS({C}, "n", {C}[Company Name], "g", {C}[Company Group Icon], '
                      f'"i", {C}[Company Code Icon], "c", {C}[Company Group Color])')
        return {r["n"]: [fix(r["g"]), fix(r["i"]), r["c"] or ""] for r in rows if r["n"]}
    return _cache.get("logo", load)[0]



def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_filters(args):
    type_ = (args.get("type") or "PO").upper()
    if type_ not in VIEWS:
        type_ = "PO"
    f = {"type": type_, "tm": args.get("tm", "1") != "0"}
    if f["tm"]:
        now = now_wib()
        f["year"], f["month"] = now.year, now.month
    else:
        f["year"], f["month"] = _int(args.get("year")), _int(args.get("month"))
    for key in ("company", "plant", "warehouse", "status", "doc", "week", "q"):
        f[key] = (args.get(key) or "").strip()
    sort = args.get("sort") or "start_date"
    f["sort"] = sort if sort in VIEWS[type_] else "start_date"
    f["dir"] = "desc" if args.get("dir") == "desc" else "asc"
    f["page"] = max(1, _int(args.get("page")) or 1)
    size = _int(args.get("size"))
    f["size"] = size if size in PAGE_SIZES else 50
    return f


def _period_args(f):
    col = f"{T}[Start Year Month No]"
    y, m = f["year"], f["month"]
    if y == 0:
        return [f"FILTER(ALL({col}), ISBLANK({col}))"]
    if y is not None and m is not None:
        return [f"TREATAS({{{y * 100 + m}}}, {col})"]
    if y is not None:
        return [f"TREATAS({{{', '.join(str(y * 100 + i) for i in range(1, 13))}}}, {col})"]
    if m is not None:
        return [f"FILTER(ALL({col}), MOD({col}, 100) = {m})"]
    return []


def _filled(col, *empty):
    cond = " && ".join(f"v <> {dax_str(e)}" for e in ("",) + empty)
    return f'FILTER(ALL({col}), VAR v = TRIM({col} & "") RETURN {cond})'


def _summary_rule(type_):
    """Aturan baris chart Summary (_CUBE_PART): status, legend dan week category harus terisi."""
    return [_filled(f"{T}[{STATUS_DESC[type_]}]", "(Blank)"), _filled(LEGEND[type_], "(Blank)"),
            _filled(f"{T}[dax_week_category_year]")]


def _table(f, type_=None, skip=()):
    """Tabel DWMaterialReadiness sesuai filter (kecuali yang ada di skip), sebagai ekspresi DAX.
    Selalu memakai aturan baris chart Summary, supaya angka Detail sama dengan Summary."""
    type_ = type_ or f["type"]
    args = [BRANCH, f"TREATAS({{{dax_str(type_)}}}, {T}[Type])"] + _summary_rule(type_) + _period_args(f)
    if f["company"] and "company" not in skip:
        if f["company"] == NO_COMPANY:
            args.append(f"FILTER(ALL({T}[Company]), NOT {T}[Company] IN ALL({C}[Company Code]))")
        else:
            args.append(f"TREATAS({{{dax_str(f['company'])}}}, {C}[Company Name])")
    for key, col in (("plant", f"{T}[Plant_No]"), ("warehouse", f"{T}[Warehouse]"), ("status", LEGEND[type_]),
                     ("doc", f"{T}[Doc_No]"), ("week", f"{T}[dax_week_category_year]")):
        if f[key] and key not in skip:
            args.append(f"TREATAS({{{dax_str(f[key])}}}, {col})")
    table = f"CALCULATETABLE({T}, {', '.join(args)})"
    if f["q"] and "q" not in skip:
        # CONTAINSSTRING mengenal wildcard * dan ?, di-escape dengan ~
        q = f["q"].replace("~", "~~").replace("*", "~*").replace("?", "~?")
        table = f"FILTER({table}, CONTAINSSTRING({SEARCH_TEXT}, {dax_str(q)}))"
    return table


def _cache_key(prefix, f, *extra):
    return (prefix,) + tuple(f[k] for k in FILTER_KEYS) + extra


def _sort_key(col):
    return lambda r: (r[col] is not None, r[col] if r[col] is not None else "")


def _detail_rows(f):
    """Maksimal DETAIL_LIMIT baris sesuai filter, sudah diurutkan."""
    def load():
        cols = VIEWS[f["type"]]
        pairs = ", ".join(f'"{k}", {COLUMNS[k][2]}' for k in cols)
        order = "DESC" if f["dir"] == "desc" else "ASC"
        rows = _query(f"DEFINE VAR _rows = SELECTCOLUMNS({_table(f)}, {pairs})\n"
                      f"EVALUATE TOPN({DETAIL_LIMIT}, _rows, [{f['sort']}], {order})")
        rows.sort(key=_sort_key(f["sort"]), reverse=f["dir"] == "desc")
        return rows
    return _cache.get(_cache_key("rows", f, f["sort"], f["dir"]), load)


def _meta(f):
    """KPI, jumlah per tab dan opsi filter dalam satu query (UNION baris k/v/l/n/x)."""
    def load():
        legend = LEGEND[f["type"]]
        date_ok = f"{T}[Start_Date] >= DATE(1901, 1, 1) && {T}[Schedule_Date] >= DATE(1901, 1, 1)"
        type_filter = f"TREATAS({{{dax_str(f['type'])}}}, {T}[Type])"

        def facet(k, table, v, label='""'):
            return f'SELECTCOLUMNS({table}, "k", "{k}", "v", {v} & "", "l", {label} & "", "n", 0, "x", 0.0)'

        def tab(t):
            return f'ROW("k", "tab", "v", "{t}", "l", "", "n", COUNTROWS({_table(f, t, ("status", "doc"))}) + 0, "x", 0.0)'

        dax = f"""
DEFINE
VAR _rows = {_table(f)}
VAR _lead = FILTER(_rows, {date_ok})
VAR _kpi = SELECTCOLUMNS(GROUPBY(_rows, {legend}, "@n", COUNTX(CURRENTGROUP(), 1)),
    "k", "kpi", "v", {legend} & "", "l", "", "n", [@n], "x", 0.0)
VAR _avg = ROW("k", "lead", "v", "", "l", "", "n", COUNTROWS(_lead) + 0,
    "x", AVERAGEX(_lead, 1.0 * ({T}[Schedule_Date] - {T}[Start_Date])))
VAR _co = {facet("company", f"SUMMARIZE({_table(f, skip=('company',))}, {C}[Company Name])", f"{C}[Company Name]")}
VAR _plant = {facet("plant", f"SUMMARIZE({_table(f, skip=('plant',))}, {T}[Plant_No], {T}[Plant_Desc])",
                    f"{T}[Plant_No]", f"{T}[Plant_Desc]")}
VAR _wh = {facet("warehouse", f"SUMMARIZE({_table(f, skip=('warehouse',))}, {T}[Warehouse])", f"{T}[Warehouse]")}
VAR _st = {facet("status", f"SUMMARIZE({_table(f, skip=('status',))}, {legend})", legend)}
VAR _doc = {facet("doc", f"TOPN(1000, SUMMARIZE({_table(f, skip=('doc',))}, {T}[Doc_No]), {T}[Doc_No], ASC)", f"{T}[Doc_No]")}
VAR _ym = {facet("ym", f"SUMMARIZE(CALCULATETABLE({T}, {BRANCH}, {type_filter}, {', '.join(_summary_rule(f['type']))}), "
                       f"{T}[Start Year Month No])",
                 f"{T}[Start Year Month No]")}
EVALUATE UNION(_kpi, _avg, {tab("PO")}, {tab("SO")}, _co, _plant, _wh, _st, _doc, _ym)
"""
        names = {1: "approval", 2: "in_progress", 3: "not_ready", 4: "ready"}
        kpi = {"total": 0, "ready": 0, "in_progress": 0, "approval": 0, "not_ready": 0, "other": 0,
               "lead_days": None, "lead_rows": 0}
        tabs, opt = {"PO": 0, "SO": 0}, {"company": set(), "plant": {}, "warehouse": set(), "status": set(), "doc": set(), "ym": set()}
        for r in _query(dax):
            k, v = r["k"], r["v"] or ""
            if k == "kpi":
                kpi["total"] += int(r["n"])
                kpi[names.get(status_rank(v), "other")] += int(r["n"])
            elif k == "lead":
                kpi["lead_rows"] = int(r["n"] or 0)
                kpi["lead_days"] = round(r["x"], 1) if r["x"] is not None else None
            elif k == "tab":
                tabs[v] = int(r["n"] or 0)
            elif k == "plant":
                if v:
                    opt["plant"].setdefault(v, r["l"] or "")
            elif k == "company":
                opt["company"].add(v or NO_COMPANY)
            elif v:
                opt[k].add(v)
        yms = sorted(int(float(v)) for v in opt["ym"])
        return {
            "kpi": kpi,
            "tabs": tabs,
            "options": {
                "years": sorted({ym // 100 for ym in yms}, reverse=True),
                "yms": yms,
                "companies": sorted(opt["company"]),
                "plants": sorted(opt["plant"].items()),
                "warehouses": sorted(opt["warehouse"]),
                "statuses": sorted(opt["status"], key=lambda s: (status_rank(s), s)),
                "docs": sorted(opt["doc"]),
            },
        }
    return _cache.get(_cache_key("meta", f), load)


def detail_rows(f):
    """Baris detail sesuai filter (maks DETAIL_LIMIT), sudah diurutkan."""
    return _detail_rows(f)[0]


def kpi(f):
    """KPI dan jumlah baris per tab untuk filter ini."""
    meta, _ = _meta(f)
    return meta["kpi"], meta["tabs"]


def company_names():
    """company code -> company name."""
    def load():
        rows = _query(f'EVALUATE SELECTCOLUMNS({C}, "code", {C}[Company Code], "name", {C}[Company Name])')
        return {r["code"]: r["name"] for r in rows if r["code"]}
    return _cache.get("company_names", load)[0]


BREAKDOWN_COLUMNS = {
    "company": [("company", f"{T}[Company]")],
    "plant": [("plant_no", f"{T}[Plant_No]"), ("plant_desc", f"{T}[Plant_Desc]")],
    "warehouse": [("warehouse", f"{T}[Warehouse]")],
    "week": [("week", f"{T}[dax_week_category_year]")],
    "month": [("year_month", f"{T}[Start Year Month No]")],
    "job": [("job_code", f"{T}[Job_Code]"), ("job_desc", f"{T}[Job_Code_Desc]")],
    "stock_code": [("stock_code", f"{T}[Stock_Code]")],
    "doc": [("doc_no", f"{T}[Doc_No]")],
}


def breakdown(f, group_by, limit=10):
    """Jumlah baris per kelompok (plant, week, dll) beserta pecahan status, urut dari yang terbanyak."""
    legend = LEGEND[f["type"]]
    cols = [("status", legend)] if group_by == "status" else BREAKDOWN_COLUMNS[group_by]
    limit = max(1, min(int(limit), 50))

    def count_if(condition):
        return f"SUMX(CURRENTGROUP(), IF({condition}, 1, 0))"

    def load():
        names = ", ".join(f'"{key}", {expr}' for key, expr in cols)
        rows = _query(f"""
DEFINE VAR _rows = {_table(f)}
EVALUATE SELECTCOLUMNS(
    TOPN({limit}, GROUPBY(_rows, {", ".join(expr for _, expr in cols)},
        "@rows", COUNTX(CURRENTGROUP(), 1),
        "@ready", {count_if(f'CONTAINSSTRING({legend}, "ready") && NOT CONTAINSSTRING({legend}, "not")')},
        "@not_ready", {count_if(f'CONTAINSSTRING({legend}, "not")')},
        "@in_progress", {count_if(f'CONTAINSSTRING({legend}, "progress")')},
        "@approval", {count_if(f'CONTAINSSTRING({legend}, "approv")')},
        "@qty", SUMX(CURRENTGROUP(), {T}[QTY_Order])),
    [@rows], DESC),
    {names}, "rows", [@rows], "ready", [@ready], "not_ready", [@not_ready],
    "in_progress", [@in_progress], "approval", [@approval], "qty_order", [@qty])
""")
        if group_by == "company":
            names_map = company_names()
            for r in rows:
                r["company"] = names_map.get(r["company"], r["company"] or NO_COMPANY)
        rows.sort(key=lambda r: -(r["rows"] or 0))
        return rows
    return _cache.get(_cache_key("bd", f, group_by, limit), load)[0]


LOOKUP_FIELDS = {"job_code": "Job_Code", "doc_no": "Doc_No", "stock_code": "Stock_Code"}
LOOKUP_GROUPS = 30


def lookup(field, value):
    """Cari satu Job Code / Doc No / Stock Code di SEMUA branch (tanpa filter FP & ME). Dipakai chatbot."""
    match = f"TREATAS({{{dax_str(value)}}}, {T}[{LOOKUP_FIELDS[field]}])"

    def load():
        status = _pool.submit(_query, f"""
EVALUATE SUMMARIZECOLUMNS({T}[branch_code], {T}[Type], {T}[PO_Status Description], {T}[Status SO Description],
    {LEGEND["PO"]}, {LEGEND["SO"]}, {match},
    "rows", COUNTROWS({T}),
    "no_week", COUNTROWS(FILTER({T}, TRIM({T}[dax_week_category_year] & "") = "")))""")
        periods = _pool.submit(_query, f"""
EVALUATE SUMMARIZECOLUMNS({T}[branch_code], {T}[Start Year Month No], {match}, "rows", COUNTROWS({T}))""")
        # Kombinasi job / plant / company / status per baris, supaya status tidak perlu ditebak pasangannya
        info = _pool.submit(_query, f"""
EVALUATE TOPN({LOOKUP_GROUPS}, SUMMARIZECOLUMNS({T}[Job_Code], {T}[Job_Code_Desc], {T}[Plant_No], {T}[Plant_Desc],
    {T}[Company], {T}[branch_code], {T}[Type], {T}[{STATUS_DESC["PO"]}], {T}[{STATUS_DESC["SO"]}],
    {match}, "rows", COUNTROWS({T})), [rows], DESC)""")
        names = company_names()
        info_rows = info.result()
        for r in info_rows:
            r["Company"] = names.get(r["Company"], r["Company"] or NO_COMPANY)
        return {"status": status.result(), "periods": periods.result(), "info": info_rows}
    return _cache.get(("lookup", field, value.upper()), load)[0]


def detail(f):
    rows_job = _pool.submit(_detail_rows, f)
    meta_job = _pool.submit(_meta, f)
    rows, fetched = rows_job.result()
    meta, _ = meta_job.result()

    options = dict(meta["options"])
    yms = options.pop("yms")
    options["months"] = sorted({ym % 100 for ym in yms if f["year"] is None or ym // 100 == f["year"]})

    pages = max(1, -(-len(rows) // f["size"]))
    page = min(f["page"], pages)
    start = (page - 1) * f["size"]
    return {
        "filters": {k: f[k] for k in ("type", "tm", "year", "month", "sort", "dir")},
        "columns": [{"key": k, "label": COLUMNS[k][0], "kind": COLUMNS[k][1]} for k in VIEWS[f["type"]]],
        "rows": rows[start:start + f["size"]],
        "total": len(rows),               
        "matched": meta["kpi"]["total"],  
        "page": page,
        "pages": pages,
        "size": f["size"],
        "kpi": meta["kpi"],
        "tabs": meta["tabs"],
        "options": options,
        "fetched": stamp_info(fetched),
    }


def _export_value(value, kind):
    if value is None:
        return ""
    if kind == "date":
        y, m, d = str(value)[:10].split("-")
        return f"{d}/{m}/{y}"
    return value


def export_tsv(f):
    """Baris yang dimuat untuk filter ini, format tab-separated supaya bisa langsung di-paste ke Excel."""
    rows, _ = _detail_rows(f)
    cols = VIEWS[f["type"]]
    out = io.StringIO()
    writer = csv.writer(out, delimiter="\t", lineterminator="\n")
    writer.writerow([COLUMNS[k][0] for k in cols])
    for r in rows:
        writer.writerow([_export_value(r[k], COLUMNS[k][1]) for k in cols])
    return out.getvalue()
