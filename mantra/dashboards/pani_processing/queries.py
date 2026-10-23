"""Query dashboard PANI ke semantic model "PANI - PRCS - Processing" (workspace PANI-MCG), dengan cache di memori.

Model berisi 4 report yang di MANTRA menjadi 4 halaman:
  Processing  : v_bq_pani_se_fact_period + v_bq_pani_se_dim_metric   (company BSI)
  Equipment   : mpx_dmr_view + mpx_dmr_gainloss_view                   (company MMI)
  Mining      : mpx_daily_pondok_view                                   (company MMI)
  Production  : mpx_stockpile_summary_view                              (company MMI)
Rumus setiap angka direkonstruksi dari data & divalidasi terhadap screenshot report Power BI (lihat README dashboard).
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from ...config import Config
from ...core.cache import Cache
from ...core.powerbi import DATA_ERRORS, Dataset, query  # noqa: F401  (DATA_ERRORS dipakai routes.py)

# ID bisa ditimpa lewat .env: PANI_PROCESSING_WORKSPACE_ID / PANI_PROCESSING_DATASET_ID
DATASET = Dataset("PANI_PROCESSING", workspace_id="f8e25e4f-1d9b-44c5-94b2-069053b7b914",
                  dataset_id="2a7f8bdf-8f64-4fb1-9ba3-c49eb680c9ac")

WIB = timezone(timedelta(hours=7))
P = "'v_bq_pani_se_fact_period'"
DIM = "'v_bq_pani_se_dim_metric'"
EQ = "'mpx_dmr_view'"
GL = "'mpx_dmr_gainloss_view'"
MN = "'mpx_daily_pondok_view'"
SP = "'mpx_stockpile_summary_view'"
MC = "'master_company_with_dates'"

PA_TARGET, UA_TARGET = 85.0, 70.0   # target kartu model di report Equipment Performance
# Warna header per holding (sama dengan warna group company di dashboard Material Readiness)
HOLDING_COLOR = {"PT Merdeka Gold Resource": "#B8860B", "PT Merdeka Copper and Gold": "#B8860B",
                 "PT Merdeka Battery Materials": "#15803D"}

_cache = Cache(Config.CACHE_SECONDS)


# ---------------------------------------------------------------- umum

def _query(dax):
    return query(DATASET, dax)


def dax_date(d):
    return f"DATE({d.year}, {d.month}, {d.day})"


def dax_str(value):
    return '"' + str(value).replace('"', '""') + '"'


def to_date(value):
    return date.fromisoformat(str(value)[:10]) if value else None


def parse_date(value, default):
    try:
        return date.fromisoformat(str(value)) if value else default
    except ValueError:
        return default


def now_wib():
    return datetime.now(WIB)


def stamp_info(ts):
    dt = datetime.fromtimestamp(ts, WIB)
    return {"date": dt.strftime("%d/%m/%Y"), "time": dt.strftime("%H:%M WIB")}


def _num(value):
    return float(value) if value is not None else None


def achievement(actual, target):
    return actual / target * 100 if actual is not None and target else None


def pct_var(actual, plan):
    return (actual - plan) / plan * 100 if actual is not None and plan else None


def _fix_url(url):
    # i.ibb.co diblokir di beberapa jaringan; domain .co.com melayani file yang sama (sama seperti Material Readiness)
    return (url or "").replace("https://i.ibb.co/", "https://i.ibb.co.com/")


def companies():
    """Company Code Alias / Company Code -> {name, logo: [logo group, logo company, warna]} untuk header."""
    def load():
        rows = _query(f"""EVALUATE SUMMARIZECOLUMNS({MC}[Company Code], {MC}[Company Code Alias], {MC}[Company Name],
            {MC}[Company Group Icon], {MC}[Company Code Icon], {MC}[Holding Company Name])""")
        result = {}
        for r in rows:
            info = {"name": r["Company Name"],
                    "logo": [_fix_url(r["Company Group Icon"]), _fix_url(r["Company Code Icon"]),
                             HOLDING_COLOR.get(r["Holding Company Name"], "")]}
            for key in (r["Company Code"], r["Company Code Alias"]):
                if key:
                    result.setdefault(key, info)
        return result
    return _cache.get("companies", load)[0]


def header_company(code):
    """Nama company + peta logo untuk Dash.setHeaderCompany (logika header sama dengan Material Readiness)."""
    info = companies().get(code) or {"name": code, "logo": ["", "", ""]}
    return info["name"], {info["name"]: info["logo"]}


def model_refresh():
    """Waktu refresh terakhir semantic model (tabel LastRefresh)."""
    def load():
        rows = _query("EVALUATE ROW(\"t\", MAX('LastRefresh'[LastRefresh]))")
        return rows[0]["t"] if rows else None
    value = _cache.get("refresh", load)[0]
    return datetime.fromisoformat(value[:19]).strftime("%d/%m %H:%M") if value else None


# ---------------------------------------------------------------- Processing

# Label & keterangan "Top 5 Negative Variance Drivers" seperti di report
DRIVER_LABEL = {"total_crushed_ore": "Throughput (Crushed Ore)", "opp_availability": "Availability (OPP)",
                "cr72_availability": "Availability (CR72)"}
GRADE_ORDER = ["gold_grade_crushed", "silver_grade_crushed", "feed_gold_grade", "feed_silver_grade"]
SNAPSHOT = [("total_gold_produced_ads", "Gold Produced (Ads)"), ("total_silver_produced_ads", "Silver Produced (Ads)")]
CHART_CODE = "total_crushed_ore"  # "Actual vs Forecast Production (Ton Dry)"


def driver_note(code):
    if "grade" in code:
        return "Lower grade feed impacts metal production."
    if "leached" in code:
        return "Leach output trailing plan."
    if "crushed" in code:
        return "Lower throughput against target capacity."
    if "availability" in code:
        return "Available operating time below target."
    if "uoa" in code:
        return "Utilisation of available time below target."
    if "efficiency" in code:
        return "Recovery efficiency below target."
    return "Below target."


def metrics():
    """code -> definisi metrik dari v_bq_pani_se_dim_metric (urutan sesuai tabel)."""
    def load():
        rows = _query(f"""EVALUATE SELECTCOLUMNS({DIM}, "code", [code], "label", [metric_label], "section", [section_label],
            "group", [metric_group], "stage", [stage_label], "stage_order", [stage_order], "unit", [unit],
            "decimals", [decimal_places], "driver", [is_driver_candidate])""")
        return {r["code"]: {**r, "decimals": int(r["decimals"] or 0), "driver": bool(r["driver"])} for r in rows}
    return _cache.get("metrics", load)[0]


def processing_bounds():
    """Tanggal awal/akhir data Processing dan tanggal terakhir yang sudah ada actual harian."""
    def load():
        r = _query(f"""EVALUATE ROW("min", MIN({P}[date_key]), "max", MAX({P}[date_key]),
            "last", CALCULATE(MAX({P}[date_key]), {P}[period_type] = "DAILY", {P}[code] = "{CHART_CODE}",
                              NOT ISBLANK({P}[actual_value])))""")[0]
        return {"min": to_date(r["min"]), "max": to_date(r["max"]), "last": to_date(r["last"] or r["max"])}
    return _cache.get("proc_bounds", load)[0]


def _metric_row(code, row, defs):
    d = defs.get(code, {})
    actual, target = (_num(row.get("actual")), _num(row.get("target"))) if row else (None, None)
    return {"code": code, "label": d.get("label", code), "unit": d.get("unit") or "", "decimals": d.get("decimals", 2),
            "actual": actual, "target": target, "var": _num(row.get("var")) if row else None,
            "achv": achievement(actual, target), "provisional": bool(row and row.get("prov"))}


def processing(start, end):
    """Semua isi halaman Processing untuk rentang start..end (angka YTD/MTD/Daily diambil pada tanggal end)."""
    def load():
        defs = metrics()
        at_end = _query(f"""EVALUATE SELECTCOLUMNS(FILTER({P}, [date_key] = {dax_date(end)}), "period", [period_type],
            "code", [code], "actual", [actual_value], "target", [target_value], "var", [variance_pct], "prov", [is_provisional])""")
        by = defaultdict(dict)
        for r in at_end:
            by[r["period"]][r["code"]] = r
        ytd, mtd, daily = by["YTD"], by["MTD"], by["DAILY"]

        drivers = sorted((_metric_row(c, ytd.get(c), defs) for c, d in defs.items() if d["driver"]),
                         key=lambda m: m["var"] if m["var"] is not None else 0)
        drivers = [m for m in drivers if m["var"] is not None and m["var"] < 0][:5]
        series_codes = {CHART_CODE, "total_gold_produced_ads", "total_silver_produced_ads"} | {m["code"] for m in drivers}
        series_rows = _query(f"""EVALUATE SELECTCOLUMNS(FILTER({P}, [period_type] = "DAILY" && [date_key] >= {dax_date(start)}
            && [date_key] <= {dax_date(end)} && [code] IN {{{", ".join(dax_str(c) for c in sorted(series_codes))}}}),
            "date", [date_key], "code", [code], "actual", [actual_value], "target", [target_value], "var", [variance_pct])""")
        series = defaultdict(dict)
        for r in series_rows:
            series[r["code"]][str(r["date"])[:10]] = r
        days = sorted({d for s in series.values() for d in s})

        def spark(code, field):
            return [_num(series[code].get(d, {}).get(field)) for d in days]

        gold, silver = _metric_row("total_gold_produced_ads", ytd.get("total_gold_produced_ads"), defs), \
            _metric_row("total_silver_produced_ads", ytd.get("total_silver_produced_ads"), defs)
        overall_actual = (gold["actual"] or 0) + (silver["actual"] or 0)
        overall_target = (gold["target"] or 0) + (silver["target"] or 0)
        stages = sorted((d for d in defs.values() if d["group"] == "STAGE"), key=lambda d: d["stage_order"] or 99)

        chart = [{"date": d, "actual": _num(series[CHART_CODE].get(d, {}).get("actual")),
                  "target": _num(series[CHART_CODE].get(d, {}).get("target"))} for d in reversed(days)]
        for point in chart:
            point["achv"] = achievement(point["actual"], point["target"])
        return {
            "company": "BSI",
            "start": start.isoformat(), "end": end.isoformat(),
            "gold": {**gold, "spark": spark("total_gold_produced_ads", "actual")},
            "silver": {**silver, "spark": spark("total_silver_produced_ads", "actual")},
            "gold_variance": {"var": gold["var"], "actual": gold["actual"], "target": gold["target"],
                              "spark": spark("total_gold_produced_ads", "var")},
            "overall": {"actual": overall_actual, "target": overall_target,
                        "achv": achievement(overall_actual, overall_target),
                        "var": pct_var(overall_actual, overall_target)},
            "stages": [{**_metric_row(d["code"], ytd.get(d["code"]), defs), "stage": d["stage"]} for d in stages],
            "metallurgy": [_metric_row(c, ytd.get(c), defs) for c, d in defs.items() if d["group"] == "METALLURGY"],
            "grades": [_metric_row(c, ytd.get(c), defs) for c in GRADE_ORDER],
            "snapshot": [{"label": label, "unit": defs.get(code, {}).get("unit", ""),
                          "daily": _metric_row(code, daily.get(code), defs), "mtd": _metric_row(code, mtd.get(code), defs),
                          "ytd": _metric_row(code, ytd.get(code), defs)} for code, label in SNAPSHOT],
            "drivers": [{**m, "label": DRIVER_LABEL.get(m["code"], m["label"]), "note": driver_note(m["code"]),
                         "spark": spark(m["code"], "var")} for m in drivers],
            "chart": chart,
            "provisional": any(r.get("prov") for r in at_end),
        }
    return _cache.get(("processing", start, end), load)


def processing_metric(code, period, at):
    """Satu baris metrik Processing (untuk AI agent)."""
    rows = _query(f"""EVALUATE SELECTCOLUMNS(FILTER({P}, [date_key] = {dax_date(at)} && [period_type] = {dax_str(period)}),
        "code", [code], "actual", [actual_value], "target", [target_value], "var", [variance_pct], "prov", [is_provisional])""")
    defs = metrics()
    by_code = {r["code"]: r for r in rows}
    codes = [code] if code else list(defs)
    return [_metric_row(c, by_code.get(c), defs) for c in codes]


def processing_trend(code, start, end):
    rows = _query(f"""EVALUATE SELECTCOLUMNS(FILTER({P}, [period_type] = "DAILY" && [code] = {dax_str(code)}
        && [date_key] >= {dax_date(start)} && [date_key] <= {dax_date(end)}),
        "date", [date_key], "actual", [actual_value], "target", [target_value], "var", [variance_pct])""")
    return sorted(({"date": str(r["date"])[:10], "actual": _num(r["actual"]), "target": _num(r["target"]),
                    "var": _num(r["var"])} for r in rows), key=lambda r: r["date"])


# ---------------------------------------------------------------- Equipment

def equipment_bounds():
    def load():
        r = _query(f'EVALUATE ROW("min", MIN({EQ}[machine_date]), "max", MAX({EQ}[machine_date]))')[0]
        return {"min": to_date(r["min"]), "max": to_date(r["max"])}
    return _cache.get("eq_bounds", load)[0]


def _equipment_units(start, end):
    return _query(f"""EVALUATE SUMMARIZECOLUMNS({EQ}[unit], {EQ}[model],
        FILTER(ALL({EQ}[machine_date]), [machine_date] >= {dax_date(start)} && [machine_date] <= {dax_date(end)}),
        "dur", SUM({EQ}[duration_sum]), "bd", SUM({EQ}[bd_duration_sum]), "pa", AVERAGE({EQ}[pa_avg]),
        "ua", AVERAGE({EQ}[ua_avg]), "active_days", CALCULATE(COUNTROWS({EQ}), {EQ}[status] = "active"),
        "days", COUNTROWS({EQ}))""")


def _avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def equipment(start, end, status=""):
    """Halaman Equipment Performance. status = '' (semua) / 'active' / 'inactive' untuk Top 5 Duration Breakdown."""
    def load():
        units = [{"unit": r["unit"], "model": r["model"], "dur": _num(r["dur"]) or 0, "bd": _num(r["bd"]) or 0,
                  "pa": _num(r["pa"]) or 0, "ua": _num(r["ua"]) or 0, "active": bool(r["active_days"]),
                  "days": int(r["days"] or 0)} for r in _equipment_units(start, end)]
        # Rata-rata PA/UA dihitung dari SEMUA baris (unit nonaktif bernilai 0), sama seperti report
        weight = sum(u["days"] for u in units)
        avg_pa = sum(u["pa"] * u["days"] for u in units) / weight if weight else None
        avg_ua = sum(u["ua"] * u["days"] for u in units) / weight if weight else None
        span = (end - start).days + 1
        prev = _equipment_units(start - timedelta(days=span), start - timedelta(days=1))
        prev_w = sum(int(r["days"] or 0) for r in prev)
        prev_pa = sum((_num(r["pa"]) or 0) * int(r["days"] or 0) for r in prev) / prev_w if prev_w else None
        prev_ua = sum((_num(r["ua"]) or 0) * int(r["days"] or 0) for r in prev) / prev_w if prev_w else None

        gainloss = _query(f"""EVALUATE SUMMARIZECOLUMNS({GL}[code], {GL}[name],
            FILTER(ALL({GL}[machine_date]), [machine_date] >= {dax_date(start)} && [machine_date] <= {dax_date(end)}),
            "dur", SUM({GL}[duration]))""")
        gainloss = sorted(({"code": r["code"], "name": r["name"], "dur": _num(r["dur"]) or 0} for r in gainloss),
                          key=lambda r: str(r["code"]))

        models = defaultdict(list)
        for u in units:
            models[u["model"]].append(u)
        cards = []
        for model, items in models.items():
            items.sort(key=lambda u: u["unit"])
            pa, ua = _avg([u["pa"] for u in items]), _avg([u["ua"] for u in items])
            ok = all(u["pa"] >= PA_TARGET and u["ua"] >= UA_TARGET for u in items)
            cards.append({"model": model, "units": items, "pa": pa, "ua": ua, "ok": ok,
                          "active": any(u["active"] for u in items), "first": items[0]["unit"]})
        # Seperti report: model yang punya unit aktif dulu, urut kode unit terkecil
        cards.sort(key=lambda c: (not c["active"], c["first"]))
        active = sum(u["active"] for u in units)
        return {"company": "MMI", "start": start.isoformat(), "end": end.isoformat(), "units": units,
                "total": len(units), "active": active, "inactive": len(units) - active,
                "avg_pa": avg_pa, "avg_ua": avg_ua,
                "delta_pa": avg_pa - prev_pa if avg_pa is not None and prev_pa is not None else None,
                "delta_ua": avg_ua - prev_ua if avg_ua is not None and prev_ua is not None else None,
                "gainloss": gainloss, "net_gainloss": sum(r["dur"] for r in gainloss), "models": cards,
                "pa_target": PA_TARGET, "ua_target": UA_TARGET}
    data, fetched = _cache.get(("equipment", start, end), load)
    pool = [u for u in data["units"] if not status or u["active"] == (status == "active")]
    top = sorted(pool, key=lambda u: -u["dur"])[:5]
    return {**data, "status": status, "top": sorted(top, key=lambda u: u["dur"]),
            "top_avg_pa": _avg([u["pa"] for u in top])}, fetched


# ---------------------------------------------------------------- Mining Production

# Rumus yang cocok dengan report (unit ton): actual & plan (lomp) per baris tabel Performance Summary
MINING_ROWS = [
    ("ore", "Total Ore Mined", ("hl_ore_rom", "hl_ore_stockpile"), ("hl_ore_rom", "hl_ore_stockpile", "cil_ore_stockpile")),
    ("waste", "Total Waste Mined", ("waste",), ("waste", "mw")),
    ("mined", "Total Mined", None, None),            # ore + waste
    ("outpit", "Total Out-Pit Movement", ("total_outpit_movement",), ()),
    ("movement", "Total Mining Movement", None, None),  # mined + out-pit
]


def mining_bounds():
    def load():
        r = _query(f"""EVALUATE ROW("min", MIN({MN}[report_date]), "max", MAX({MN}[report_date]),
            "last", CALCULATE(MAX({MN}[report_date]), NOT ISBLANK({MN}[actual])))""")[0]
        return {"min": to_date(r["min"]), "max": to_date(r["max"]), "last": to_date(r["last"] or r["max"])}
    return _cache.get("mn_bounds", load)[0]


def _mining_period(daily, first, last):
    """Jumlahkan per baris tabel untuk rentang tanggal [first, last]."""
    def total(keys, field):
        values = [daily[d][k][field] for d in daily if first <= d <= last for k in keys
                  if daily[d].get(k, {}).get(field) is not None]
        return sum(values) if values else None
    out = {}
    for key, label, act_keys, plan_keys in MINING_ROWS:
        if key == "mined":
            act = (out["ore"]["actual"] or 0) + (out["waste"]["actual"] or 0)
            plan = (out["ore"]["plan"] or 0) + (out["waste"]["plan"] or 0)
        elif key == "movement":
            act = out["mined"]["actual"] + (out["outpit"]["actual"] or 0)
            plan = out["mined"]["plan"] + (out["outpit"]["plan"] or 0)
        else:
            act, plan = total(act_keys, "actual"), (total(plan_keys, "plan") if plan_keys else 0.0)
        out[key] = {"label": label, "actual": act, "plan": plan,
                    "var": (act or 0) - (plan or 0), "pct": pct_var(act, plan)}
    return out


def mining(start, end):
    def load():
        year_start = date(end.year, 1, 1)
        rows = _query(f"""EVALUATE SUMMARIZECOLUMNS({MN}[report_date], {MN}[leaf_key], FILTER(ALL({MN}[unit]), [unit] = "ton"),
            FILTER(ALL({MN}[report_date]), [report_date] >= {dax_date(min(start, year_start))} && [report_date] <= {dax_date(end)}),
            "actual", SUM({MN}[actual]), "plan", SUM({MN}[lomp]))""")
        daily = defaultdict(dict)
        for r in rows:
            daily[to_date(r["report_date"])][r["leaf_key"]] = {"actual": _num(r["actual"]), "plan": _num(r["plan"])}
        month_start = date(end.year, end.month, 1)
        periods = {"daily": _mining_period(daily, start, end), "mtd": _mining_period(daily, month_start, end),
                   "ytd": _mining_period(daily, year_start, end)}
        mtd = periods["mtd"]
        # Grafik MTD: harian + kumulatif untuk Total Mined dan Total Movement
        days = [month_start + timedelta(days=i) for i in range((end - month_start).days + 1)]
        charts = {}
        for key in ("mined", "movement"):
            points, cum_a, cum_p = [], 0.0, 0.0
            for d in days:
                p = _mining_period(daily, d, d)[key]
                cum_a += p["actual"] or 0
                cum_p += p["plan"] or 0
                points.append({"date": d.isoformat(), "actual": p["actual"], "plan": p["plan"],
                               "cum_actual": cum_a, "cum_plan": cum_p})
            charts[key] = {"points": points, "achv": achievement(mtd[key]["actual"], mtd[key]["plan"]),
                           "actual": mtd[key]["actual"], "plan": mtd[key]["plan"]}
        donut_total = (mtd["waste"]["actual"] or 0) + (mtd["ore"]["actual"] or 0) + (mtd["outpit"]["actual"] or 0)
        donut = [{"label": "Waste Mined", "value": mtd["waste"]["actual"] or 0, "color": "#14b8a6"},
                 {"label": "Ore Mined", "value": mtd["ore"]["actual"] or 0, "color": "#3b82f6"},
                 {"label": "Out-Pit Movement", "value": mtd["outpit"]["actual"] or 0, "color": "#f97316"}]
        for part in donut:
            part["pct"] = part["value"] / donut_total * 100 if donut_total else 0
        return {"company": "MMI", "start": start.isoformat(), "end": end.isoformat(),
                "month_start": month_start.isoformat(), "year_start": year_start.isoformat(),
                "periods": periods, "charts": charts, "donut": donut, "donut_total": donut_total}
    return _cache.get(("mining", start, end), load)


# ---------------------------------------------------------------- Production (stockpile)

def production_bounds():
    def load():
        r = _query(f'EVALUATE ROW("min", MIN({SP}[ritase_date]), "max", MAX({SP}[ritase_date]))')[0]
        return {"min": to_date(r["min"]), "max": to_date(r["max"])}
    return _cache.get("sp_bounds", load)[0]


def flow_stage(location):
    """Tahap alur input berdasarkan nama lokasi (Crushing / Screening / Stockpile)."""
    name = location.lower()
    if "crusher" in name or "crushing" in name:
        return "Crushing"
    if "screen" in name:
        return "Screening"
    if "stockpile" in name:
        return "Stockpile"
    return None


def production(start, end):
    def load():
        rows = _query(f"""EVALUATE SUMMARIZECOLUMNS({SP}[ritase_date], {SP}[dump_location],
            FILTER(ALL({SP}[ritase_date]), [ritase_date] >= {dax_date(start)} && [ritase_date] <= {dax_date(end)}),
            "input", SUM({SP}[tonnes_addition]), "output", SUM({SP}[tonnes_depletion]))""")
        loc = defaultdict(lambda: {"input": 0.0, "output": 0.0})
        by_day = defaultdict(lambda: {"input": 0.0, "output": 0.0})
        for r in rows:
            i, o = _num(r["input"]) or 0, _num(r["output"]) or 0
            loc[r["dump_location"]]["input"] += i
            loc[r["dump_location"]]["output"] += o
            by_day[to_date(r["ritase_date"])]["input"] += i
            by_day[to_date(r["ritase_date"])]["output"] += o
        total_in = sum(v["input"] for v in loc.values())
        total_out = sum(v["output"] for v in loc.values())
        locations = sorted(({"name": k, **v, "in_pct": v["input"] / total_in * 100 if total_in else 0,
                             "out_pct": v["output"] / total_out * 100 if total_out else 0} for k, v in loc.items()),
                           key=lambda x: (-x["input"], -x["output"]))
        stages = {s: sum(v["input"] for k, v in loc.items() if flow_stage(k) == s)
                  for s in ("Crushing", "Screening", "Stockpile")}

        def trend(key_fn, label_fn):
            groups = defaultdict(lambda: {"input": 0.0, "output": 0.0})
            for d, v in by_day.items():
                g = groups[key_fn(d)]
                g["input"] += v["input"]
                g["output"] += v["output"]
            return [{"label": label_fn(k), "input": v["input"], "output": v["output"],
                     "net": v["output"] - v["input"]} for k, v in sorted(groups.items(), reverse=True)]
        top_in = [x for x in locations if x["input"] > 0]
        top_out = sorted((x for x in locations if x["output"] > 0), key=lambda x: -x["output"])
        return {"company": "MMI", "start": start.isoformat(), "end": end.isoformat(),
                "input": total_in, "output": total_out, "net": total_out - total_in, "grand": total_in + total_out,
                "output_pct": total_out / total_in * 100 if total_in else None,
                "net_pct": (total_out - total_in) / total_in * 100 if total_in else None,
                "stages": stages, "locations": locations, "top_input": top_in, "top_output": top_out,
                # Lokasi stockpile dengan input terbesar, untuk kartu Rekomendasi
                "stock_input": ([x for x in top_in if "stockpile" in x["name"].lower()] or top_in)[:2],
                "trend": {"daily": trend(lambda d: d, lambda d: d.strftime("%d %b")),
                          "weekly": trend(lambda d: d.isocalendar()[:2], lambda k: f"W{k[1]:02d} {k[0]}"),
                          "mtd": trend(lambda d: (d.year, d.month), lambda k: date(k[0], k[1], 1).strftime("%b %Y"))}}
    return _cache.get(("production", start, end), load)

