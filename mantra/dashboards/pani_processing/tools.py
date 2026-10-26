"""Tools AI agent PANI. Setiap tool memakai fungsi yang sama dengan halaman dashboard (queries.py), jadi angkanya sama.

Tanggal yang tidak disebut user mengikuti rentang tanggal halaman yang sedang dibuka (parse_dash), lalu default
halaman (tanggal data terakhir).
"""
from datetime import date

from ...core.chat.guards import ToolArgError, resolve
from ...core.registry import Tool
from . import queries

PERIODS = ("DAILY", "MTD", "YTD")
STATUSES = ("active", "inactive")
NO_DATA = {"error": "This page has no data in the semantic model yet. Tell the user; do not guess any numbers."}
DATE_PROPS = {
    "start": {"type": "string", "description": "Tanggal awal YYYY-MM-DD. Kosongkan untuk mengikuti filter halaman."},
    "end": {"type": "string", "description": "Tanggal akhir YYYY-MM-DD. Kosongkan untuk mengikuti filter halaman."},
}


def _round(value, decimals=2):
    return round(value, decimals) if isinstance(value, float) else value


def _clean(obj, decimals=2):
    """Bulatkan angka supaya hasil tool ringkas untuk AI."""
    if isinstance(obj, dict):
        return {k: _clean(v, decimals) for k, v in obj.items() if k not in ("spark",)}
    if isinstance(obj, list):
        return [_clean(v, decimals) for v in obj]
    return _round(obj, decimals)


def _dates(args, dash, bounds, default_start, default_end):
    """Rentang dari AI / filter halaman / default, dibatasi ke tanggal data yang ada (sama seperti halaman)."""
    end = queries.parse_date(args.get("end") or dash.get("end"), default_end)
    start = queries.parse_date(args.get("start") or dash.get("start"), default_start)
    return queries.date_range(start, end, bounds)


# ---------------------------------------------------------------- Processing

def _processing_date(args, dash, b):
    """Tanggal Processing; tanggal setelah data terakhir dimundurkan ke tanggal data terakhir (default dashboard)."""
    at = queries.parse_date(args.get("date") or dash.get("end"), b["max"])
    note = None
    if at > b["max"]:
        note = f"Latest data is {b['max'].isoformat()}, so date {at.isoformat()} was replaced with that date."
        at = b["max"]
    elif at < b["min"]:
        note = f"First data is {b['min'].isoformat()}, so date {at.isoformat()} was replaced with that date."
        at = b["min"]
    return at, note


def tool_processing_metrics(args, dash):
    b = queries.processing_bounds()
    if not queries.has_data(b):
        return NO_DATA
    at, date_note = _processing_date(args, dash, b)
    period = args.get("period") or "YTD"
    rows = queries.processing_metric(args.get("metric"), period, at)
    defs = queries.metrics()
    group = (args.get("group") or "").upper()
    if group:
        rows = [r for r in rows if defs.get(r["code"], {}).get("group") == group]
    rows = [{**r, "section": defs.get(r["code"], {}).get("section")} for r in rows if r["actual"] is not None or r["target"] is not None]
    result = {"date": at.isoformat(), "period": period, "metrics": rows,
              "data_range": {"first": b["min"].isoformat(), "last": b["max"].isoformat(),
                             "last_crushing_actual": b["last"].isoformat()}}
    notes = [n for n in (date_note, "Some numbers are still provisional (they may change once final data arrives)."
                         if any(r["provisional"] for r in rows) else None) if n]
    if notes:
        result["note"] = " ".join(notes)
    return _clean(result)


def tool_processing_trend(args, dash):
    if not args.get("metric"):
        raise ToolArgError("metric", "", sorted(queries.metrics()))
    b = queries.processing_bounds()
    if not queries.has_data(b):
        return NO_DATA
    start, end = _dates(args, dash, b, date(b["last"].year, b["last"].month, 1), b["last"])
    points = queries.processing_trend(args["metric"], start, end)
    actual = [p["actual"] for p in points if p["actual"] is not None]
    target = [p["target"] for p in points if p["target"] is not None]
    below = [p["date"] for p in points if p["actual"] is not None and p["target"] and p["actual"] < p["target"]]
    return _clean({"metric": args["metric"], "start": start.isoformat(), "end": end.isoformat(), "days": len(points),
                   "sum_actual": sum(actual) if actual else None, "sum_target": sum(target) if target else None,
                   "avg_actual": sum(actual) / len(actual) if actual else None,
                   "days_below_target": len(below), "last_points": points[-14:]})


def tool_variance_drivers(args, dash):
    b = queries.processing_bounds()
    if not queries.has_data(b):
        return NO_DATA
    end, date_note = _processing_date(args, dash, b)
    # Sama seperti halaman: tanggal akhir = data terakhir -> YTD; tanggal lebih awal -> drivers DAILY pada tanggal itu
    data, _ = queries.processing(b["min"], end)
    result = {"date": end.isoformat(), "period": data["driver_period"], "top_negative_drivers": data["drivers"],
              "overall_achievement": data["overall"], "stages": data["stages"]}
    if date_note:
        result["note"] = date_note
    return _clean(result)


# ---------------------------------------------------------------- Equipment / Mining / Production

def tool_equipment(args, dash):
    b = queries.equipment_bounds()
    if not queries.has_data(b):
        return NO_DATA
    start, end = _dates(args, dash, b, b["max"], b["max"])
    data, _ = queries.equipment(start, end, args.get("status") or "")
    models = data["models"]
    if args.get("model"):
        name = resolve("model", args["model"], {m["model"] for m in models}, prefixes=())
        models = [m for m in models if m["model"] == name]
    result = {"start": start.isoformat(), "end": end.isoformat(), "total_units": data["total"], "active_units": data["active"],
              "inactive_units": data["inactive"], "avg_pa_pct": data["avg_pa"], "avg_ua_pct": data["avg_ua"],
              "targets": {"pa": data["pa_target"], "ua": data["ua_target"]},
              "top5_duration": [{k: u[k] for k in ("unit", "model", "dur", "pa", "ua", "active")} for u in data["top"]],
              "net_gainloss_hours": data["net_gainloss"],
              "models": [{"model": m["model"], "units": len(m["units"]), "pa_pct": m["pa"], "ua_pct": m["ua"],
                          "meets_target": m["ok"], "has_active_unit": m["active"],
                          "units_below_target": [u["unit"] for u in m["units"]
                                                 if u["pa"] < data["pa_target"] or u["ua"] < data["ua_target"]]}
                         for m in models],
              "data_range": {"first": b["min"].isoformat(), "last": b["max"].isoformat()}}
    if args.get("model"):
        result["unit_detail"] = [{k: u[k] for k in ("unit", "dur", "pa", "ua", "active")} for m in models for u in m["units"]]
    return _clean(result)


def tool_mining(args, dash):
    b = queries.mining_bounds()
    if not queries.has_data(b):
        return NO_DATA
    start, end = _dates(args, dash, b, date(b["last"].year, b["last"].month, 1), b["last"])
    data, _ = queries.mining(start, end)
    return _clean({"unit": "ton", "daily_range": [start.isoformat(), end.isoformat()],
                   "mtd_range": [data["month_start"], end.isoformat()], "ytd_range": [data["year_start"], end.isoformat()],
                   "periods": data["periods"], "achievement_pct": {k: v["achv"] for k, v in data["charts"].items()},
                   # Donut halaman Mining dihitung dari rentang filter (daily_range), bukan MTD
                   "movement_composition_range": data["donut"],
                   "data_range": {"first": b["min"].isoformat(), "last_actual": b["last"].isoformat()}}, 0)


def tool_stockpile(args, dash):
    b = queries.production_bounds()
    if not queries.has_data(b):
        return NO_DATA
    start, end = _dates(args, dash, b, date(b["max"].year, b["max"].month, 1), b["max"])
    data, _ = queries.production(start, end)
    return _clean({"unit": "ton", "start": start.isoformat(), "end": end.isoformat(), "total_input": data["input"],
                   "total_output": data["output"], "net_movement": data["net"], "grand_total": data["grand"],
                   "output_pct_of_input": data["output_pct"], "flow_stages_input": data["stages"],
                   "locations": data["locations"][:15],
                   "data_range": {"first": b["min"].isoformat(), "last": b["max"].isoformat()}})


TOOLS = [
    Tool("get_processing_metrics", "Processing metrics",
         "Actual, target, variance %, dan achievement % metrik Processing (gold/silver produced, crushed ore, leached, "
         "grade, efficiency, availability, dll.) pada satu tanggal untuk periode DAILY, MTD, atau YTD.",
         {"type": "object", "properties": {
             "period": {"type": "string", "enum": list(PERIODS), "description": "Default YTD."},
             "date": {"type": "string", "description": "Tanggal YYYY-MM-DD. Kosongkan = tanggal akhir filter halaman / data terakhir."},
             "metric": {"type": "string", "description": "Kode atau nama metrik (lihat kamus data). Kosongkan untuk semua."},
             "group": {"type": "string", "enum": ["KPI", "STAGE", "METALLURGY", "GRADE", "OTHER"],
                       "description": "Kelompok metrik. Kosongkan untuk semua."},
         }, "required": []},
         tool_processing_metrics),
    Tool("get_processing_trend", "Processing daily trend",
         "Tren harian satu metrik Processing (actual vs target) dalam rentang tanggal: total, rata-rata, jumlah hari di "
         "bawah target, dan 14 hari terakhir.",
         {"type": "object", "properties": {"metric": {"type": "string", "description": "Kode atau nama metrik."}, **DATE_PROPS},
          "required": ["metric"]},
         tool_processing_trend),
    Tool("get_variance_drivers", "Variance drivers",
         "Top 5 metrik dengan variance negatif terbesar (YTD) seperti panel 'Top 5 Negative Variance Drivers', plus "
         "overall achievement gold+silver dan ringkasan per stage.",
         {"type": "object", "properties": {"date": {"type": "string", "description": "Tanggal YYYY-MM-DD (opsional)."}},
          "required": []},
         tool_variance_drivers),
    Tool("get_equipment", "Equipment performance",
         "Ringkasan Equipment Performance: unit aktif/nonaktif, rata-rata PA% & UA%, Top 5 durasi, net gain/loss, dan "
         "PA/UA per model beserta unit di bawah target (PA >= 85%, UA >= 70%).",
         {"type": "object", "properties": {**DATE_PROPS,
             "model": {"type": "string", "description": "Nama model, mis. CAT 320GX (opsional)."},
             "status": {"type": "string", "enum": ["active", "inactive"], "description": "Filter Top 5 (opsional)."}},
          "required": []},
         tool_equipment),
    Tool("get_mining", "Mining production",
         "Mining Production (ton): ore mined, waste mined, total mined, out-pit movement, total movement untuk "
         "periode DAILY (rentang filter), MTD, dan YTD: actual, plan, var, % var, achievement.",
         {"type": "object", "properties": DATE_PROPS, "required": []},
         tool_mining),
    Tool("get_stockpile", "Stockpile production",
         "Production/stockpile (ton): total input, output, net movement, grand total, alur Crushing/Screening/Stockpile, "
         "dan input/output per lokasi.",
         {"type": "object", "properties": DATE_PROPS, "required": []},
         tool_stockpile),
]


def clean_args(args):
    """Normalkan period, status equipment, dan nama metrik dari AI ke nilai asli di data."""
    args = dict(args)
    if args.get("period"):
        args["period"] = str(args["period"]).strip().upper()
        if args["period"] not in PERIODS:
            raise ToolArgError("period", args["period"], PERIODS)
    if args.get("status"):
        args["status"] = str(args["status"]).strip().lower()
        if args["status"] not in STATUSES:
            raise ToolArgError("status", args["status"], STATUSES)
    if args.get("metric"):
        defs = queries.metrics()
        by_label = {d["label"]: code for code, d in defs.items()}
        value = str(args["metric"]).strip()
        if value not in defs:
            label = resolve("metric", value, set(by_label) | set(defs), prefixes=())
            value = by_label.get(label, label)
        args["metric"] = value
    return args


def parse_dash(raw):
    """Filter halaman aktif dari browser: {page, start, end}."""
    raw = raw if isinstance(raw, dict) else {}
    return {k: str(raw.get(k) or "")[:10] or None for k in ("start", "end")} | {"page": str(raw.get("page") or "")[:20]}


SUGGESTIONS = [
    "What is gold produced YTD and its achievement?",
    "What are the top 5 negative variance drivers?",
    "Which equipment models have PA below target?",
    "How does total mined MTD compare to plan?",
]
