"""Bandingkan angka dashboard PANI di MANTRA dengan measure HTML report Power BI aslinya.

Measure report (mis. html_gold_produced_ads_ytd) dijalankan lewat executeQueries dengan filter tanggal yang sama,
teksnya dibaca, lalu dibandingkan dengan angka MANTRA dalam format tampilan yang sama (mis. 49,077.26 / -4.8%).

Pemakaian:
    python scripts/compare_pani_report.py              semua halaman & skenario
    python scripts/compare_pani_report.py processing   hanya halaman tertentu (processing/equipment/mining/production)

Selisih yang memang disengaja (bug di report aslinya) ditandai "BEDA*" dan tidak dihitung gagal; lihat KNOWN.
"""
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mantra.core import powerbi  # noqa: E402
from mantra.dashboards.pani_processing import queries as q  # noqa: E402

failed = 0
counts = {"ok": 0, "known": 0, "bad": 0}


def text(html):
    t = re.sub(r"<style.*?</style>|<script.*?</script>|<title>.*?</title>", " ", html or "", flags=re.S)
    t = re.sub(r"""title=(['"]).*?\1""", "", t)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).strip()


def measures(table, column, names, start=None, end=None):
    filt = (f"FILTER(ALL({table}[{column}]), [{column}] >= {q.dax_date(start)} && [{column}] <= {q.dax_date(end)})"
            if start else None)
    cols = ", ".join(f'"{n}", ' + (f"CALCULATE([{n}], {filt})" if filt else f"[{n}]") for n in names)
    row = powerbi.query(q.DATASET, f"EVALUATE ROW({cols})")[0]
    return {n: text(row.get(n)) for n in names}


def n2(v):
    return q.fmt_num(v, 2)  # format yang sama dengan tampilan MANTRA


def n0(v):
    return q.fmt_num(v, 0)


def p1(v):
    return "-" if v is None else q.fmt_num(v, 1, sign=True) + "%" if q.fmt_num(abs(v), 1) != "0.0" else "0.0%"


def check(label, report, mine, known=None):
    global failed
    same = report == mine
    if same:
        counts["ok"] += 1
        mark = "OK   "
    elif known:
        counts["known"] += 1
        mark = "BEDA*"
    else:
        counts["bad"] += 1
        failed += 1
        mark = "BEDA "
    print(f"  {mark} {label:58s} report={report!s:>22}  mantra={mine!s:>22}" + (f"   ({known})" if known and not same else ""))


def find(pattern, txt, group=1):
    m = re.search(pattern, txt)
    return m.group(group) if m else None


# ------------------------------------------------------------------ Processing

def processing(start, end, label):
    b = q.processing_bounds()
    s, e = (start or b["min"]), (end or b["max"])
    print(f"\n== Processing · {label} ({s} s/d {e})")
    names = ["html_gold_produced_ads_ytd", "html_silver_produced_ads_ytd", "html_overall_achievement",
             "html_production_summary_by_stage", "html_metallurgical_performance", "html_grade_overview",
             "html_daily_mtd_ytd_snapshot", "html_top5_negative_variance_drivers"]
    r = measures(q.P, "date_key", names, start, end)
    d, _ = q.processing(s, e)
    for key, m in (("gold", "html_gold_produced_ads_ytd"), ("silver", "html_silver_produced_ads_ytd")):
        t = r[m]
        check(f"{key} actual", find(r"Actual (?:YTD|Selected Period): ([\d,.]+)", t), n2(d[key]["actual"]))
        check(f"{key} target", find(r"Target (?:YTD|Selected Period): ([\d,.]+)", t), n2(d[key]["target"]))
        check(f"{key} variance", find(r"Variance: ([-+\d.]+%)", t), p1(d[key]["var"]))
    t = r["html_overall_achievement"]
    check("overall total actual", find(r"Total Actual: ([\d,.]+)", t), n2(d["overall"]["actual"]))
    check("overall total target", find(r"Total Target: ([\d,.]+)", t), n2(d["overall"]["target"]))
    check("overall %", find(r"Overall: (\d+)%", t), n0(d["overall"]["achv"]))
    t = r["html_production_summary_by_stage"]
    for s_ in d["stages"]:
        m = re.search(re.escape(s_["stage"]) + r" ([\d,.]+) \S+ ([-+\d.]+%) (\d+%|N/A)", t)
        check(f"stage {s_['stage']} actual", m and m.group(1), n2(s_["actual"]))
        check(f"stage {s_['stage']} vs target", m and m.group(2), p1(s_["var"]))
    t = r["html_metallurgical_performance"]
    for m_ in d["metallurgy"]:
        m = re.search(re.escape(m_["label"]) + r" \(%\) ([\d.]+)% ([-+\d.]+%) vs Target", t)
        check(f"{m_['label']}", m and m.group(1), q.fmt_num(m_['actual'], 1) if m_["actual"] is not None else "-")
        check(f"{m_['label']} vs target", m and m.group(2), p1(m_["var"]))
    t = r["html_grade_overview"]
    for g in d["grades"]:
        m = re.search(re.escape(g["label"]) + r" \(ppm\) ([\d.]+) ([\d.]+) ([-+\d.]+%)", t)
        check(f"{g['label']} actual/target", m and f"{m.group(1)}/{m.group(2)}", q.fmt_num(g['actual'] or 0, 2) + "/" + q.fmt_num(g['target'] or 0, 2))
    t = r["html_daily_mtd_ytd_snapshot"]
    for s_ in d["snapshot"]:
        m = re.search(re.escape(s_["label"]) + r" \(Oz\) " + r" ".join([r"([\d,.]+) ([\d,.]+) ([-+\d.]+%)"] * 3), t)
        mine = []
        for p in (s_["daily"], s_["mtd"], s_["ytd"]):
            mine += [n2(p["actual"] or 0), n2(p["target"]), p1(p["var"]) if p["actual"] is not None else "0.0%"]
        check(f"snapshot {s_['label']}", m and " ".join(m.groups()), " ".join(mine))
    t = r["html_top5_negative_variance_drivers"]
    rep = re.findall(r"\d (.+?) ([-+]?\d+\.\d)% vs Target", re.sub(r"^.*?\((?:YTD|DAILY)\) ", "", t))
    check("drivers (label & variance)", "; ".join(f"{a} {b}" for a, b in rep) or "none",
          "; ".join(f"{m['label']} {q.fmt_num(m['var'], 1)}" for m in d["drivers"]) or "none")


# ------------------------------------------------------------------ Equipment

def equipment(start, end, label):
    b = q.equipment_bounds()
    s, e = (start or b["min"]), (end or b["max"])
    print(f"\n== Equipment · {label} ({s} s/d {e})")
    r = measures(q.EQ, "machine_date", ["Card_ActiveUnit_HTML", "Card_InactiveUnit_HTML", "Card_AvgPA_HTML", "Card_AvgUA_HTML",
                                        "Top_5_Inactive_HTML", "Card_PerformanceByModel_HTML"], start, end)
    g = measures(q.GL, "machine_date", ["Card_GainLoss_HTML"], start, end)
    d, _ = q.equipment(s, e)
    check("total active unit", find(r"Total Active Unit ([\d,]+)", r["Card_ActiveUnit_HTML"]), n0(d["active"]))
    check("% active", find(r"([\d.]+)% dari total unit", r["Card_ActiveUnit_HTML"]), q.fmt_num(d['active'] / d['total'] * 100, 2))
    check("total inactive unit", find(r"Total Inactive Unit ([\d,]+)", r["Card_InactiveUnit_HTML"]), n0(d["inactive"]))
    for key, m in (("pa", "Card_AvgPA_HTML"), ("ua", "Card_AvgUA_HTML")):
        check(f"average {key.upper()}%", find(r"Average \w+% ([\d.]+)%", r[m]), q.fmt_num(d['avg_' + key], 2))
        delta = d["delta_" + key]
        check(f"{key.upper()} vs yesterday", find(r"vs yesterday (?:[▲▼] )?([-+\d.]+%|-)", r[m]),
              "-" if delta is None else q.fmt_num(delta, 2, sign=True) + "%")
    t = r["Top_5_Inactive_HTML"]
    check("top 5 average PA%", find(r"Average PA%: ([\d.]+)%", t), q.fmt_num(d['top_avg_pa'], 2))
    table = t.split("Duration PA%", 1)[-1]
    rep_pa = sorted(re.findall(r"([\d.]+)%", table))
    check("top 5 unit ada di report & PA% sama",
          f"{len(rep_pa)} unit, PA {' '.join(rep_pa)}",
          f"{len(d['top'])} unit, PA {' '.join(sorted(f'{q.fmt_num(u['pa'], 2)}' for u in d['top']))}"
          if all(u["unit"] in table for u in d["top"]) else "unit berbeda")
    t = r["Card_PerformanceByModel_HTML"]
    chunks = re.split(r"(?:⚠ Needs Attention Some units are below the target\.|✓ Excellent All units meet the performance targets\.)", t)
    rep = {}
    for chunk in chunks:
        m = re.match(r"\s*(.*?) ?(\d+) units? PA ([\d.]+)% Target PA ≥ \d+% UA ([\d.]+)%", chunk)
        if m:
            rep[m.group(1).strip()] = (m.group(3), m.group(4), m.group(2))
    mine = {c["model"]: (q.fmt_num(c["pa"], 2), q.fmt_num(c["ua"], 2), str(len(c["units"]))) for c in d["models"]}
    bad = [f"{k}: report {v} vs mantra {mine.get(k)}" for k, v in rep.items() if mine.get(k) != v]
    check(f"kartu model PA/UA/jumlah unit ({len(rep)} model)", "sama" if not bad else "; ".join(bad[:3]), "sama" if not bad else "")
    check("gain & loss net (h)", find(r"Net: ([-\d.]+) h", g["Card_GainLoss_HTML"]), f"{d['net_gainloss']:.1f}")


# ------------------------------------------------------------------ Mining

def mining(start, end, label):
    print(f"\n== Mining · {label} ({start} s/d {end})")
    r = measures(q.MN, "report_date", ["Card_TotalMined_HTML", "Card_TotalMovement_HTML", "Card_TotalWasteMined_HTML",
                                       "Card_TotalOutPit_HTML", "Table_PerformanceSummary_HTML", "HTML_Donut_3Category_v2",
                                       "All_In_One_TotalMined_Card_RealChart", "All_In_One_TotalMovement_Card_RealChart",
                                       "Card_KeyHighlights_HTML"], start, end)
    d, _ = q.mining(start, end)
    mtd = d["periods"]["daily"]  # kartu "(MTD)" di report memakai rentang filter
    hl = re.search(r"MTD Production is (?:below|above) plan by ([-+\d,]+) t \(([-+\d]+)%\)", r["Card_KeyHighlights_HTML"])
    check("key highlight MTD Production", hl and f"{hl.group(1)} ({hl.group(2)}%)",
          f"{mtd['mined']['var']:+,.0f} ({mtd['mined']['pct']:+.0f}%)".replace("+", "") if mtd["mined"]["var"] < 0
          else f"{mtd['mined']['var']:+,.0f} ({mtd['mined']['pct']:+.0f}%)")
    for key, m in (("mined", "Card_TotalMined_HTML"), ("movement", "Card_TotalMovement_HTML"),
                   ("waste", "Card_TotalWasteMined_HTML"), ("outpit", "Card_TotalOutPit_HTML")):
        t = r[m]
        check(f"kartu {key} actual", find(r"\(MTD\) ([\d,]+)", t), n0(mtd[key]["actual"]))
        check(f"kartu {key} plan", find(r"vs Plan ([\d,]+)", t), n0(mtd[key]["plan"]))
    t = r["Table_PerformanceSummary_HTML"]
    names = {"ore": "Total Ore Mined", "waste": "Total Waste Mined", "mined": "Total Mined", "outpit": "Total Out-Pit Movement",
             "movement": "Total Mining Movement"}
    for key, name in names.items():
        m = re.search(re.escape(name) + r" \(t\) " + " ".join([r"([-+\d,]+) ([-+\d,]+) ([-+\d,]+) ([-+\d]+%)"] * 3), t)
        mine = []
        for p in ("daily", "mtd", "ytd"):
            x = d["periods"][p][key]
            mine += [n0(x["actual"] or 0), n0(x["plan"]), f"{x['var']:+,.0f}".replace("+0", "0") if round(x["var"]) else "0",
                     (f"{x['pct']:+.0f}%" if x["plan"] and round(x["pct"]) else "0%")]
        known = ("report menjumlahkan out-pit ton + bcm" if key in ("outpit", "movement")
                 else "pembulatan plan 1 t di report" if key == "mined" else None)
        check(f"tabel {name} (daily/mtd/ytd)", m and " ".join(m.groups()), " ".join(mine), known)
    t = r["HTML_Donut_3Category_v2"]
    check("donut total", find(r"Total Movement Overview ([\d,]+) t", t), n0(d["donut_total"]))
    check("donut %", " ".join(re.findall(r"\(([\d.]+)%\)", t)),
          " ".join(q.fmt_num(p['pct'], 1) for p in sorted(d["donut"], key=lambda p: ["Waste Mined", "Ore Mined", "Out-Pit Movement"].index(p["label"]))))
    for key, m in (("mined", "All_In_One_TotalMined_Card_RealChart"), ("movement", "All_In_One_TotalMovement_Card_RealChart")):
        check(f"achievement {key}", find(r"Achievement (\d+)%", r[m]), n0(d["charts"][key]["achv"]) if d["charts"][key]["achv"] else None)
    check("weather loss MTD (hrs)", find(r"Weather Loss reached ([\d.]+) hrs", r["Card_KeyHighlights_HTML"]), q.fmt_num(d['weather_loss'], 1))


# ------------------------------------------------------------------ Production

def production(start, end, label):
    b = q.production_bounds()
    s, e = (start or b["min"]), (end or b["max"])
    print(f"\n== Production · {label} ({s} s/d {e})")
    r = measures(q.SP, "ritase_date", ["Card_TotalInput_HTML", "Card_TotalOutput_HTML", "Card_NetMovement_HTML", "Card_GrandTotal_HTML",
                                       "Flow_Dashboard_HTML", "Table_TopInputOutput_HTML"], start, end)
    d, _ = q.production(s, e)
    for key, m in (("input", "Card_TotalInput_HTML"), ("output", "Card_TotalOutput_HTML"), ("net", "Card_NetMovement_HTML"),
                   ("grand", "Card_GrandTotal_HTML")):
        check(f"kartu {key} (BCM)", find(r"\(BCM\) ([-\d,.]+)", r[m]), n2(d[key]))
    t = r["Flow_Dashboard_HTML"]
    check("alur input tonnes", find(r"Input [\d,.]+ BCM ([\d,.]+) Tonnes", t), n2(d["input_t"]))
    check("alur output tonnes", find(r"Output [\d,.]+ BCM ([\d,.]+) Tonnes", t), n2(d["output_t"]))
    for stage in ("Crushing", "Screening", "Stockpile"):
        check(f"alur {stage}", find(stage + r" ([\d,.]+) BCM", t), n2(d["stages"][stage]))
    check("output % dari input", find(r"→ ([\d.]+)% Output", t), q.fmt_num(d['output_pct'], 2) if d["output_pct"] is not None else "-")
    t = r["Table_TopInputOutput_HTML"]
    for side, key, pct in (("INPUT", "top_input", "in_pct"), ("OUTPUT", "top_output", "out_pct")):
        seg = t.split(f"TOP {side} (BCM)", 1)[-1].split("BCM %", 1)[-1].split(f"Total {side.title()}", 1)[0]
        rep = re.findall(r"([A-Za-z][\w ]*?) ([\d,.]+) ([\d.]+)%", seg)
        check(f"top {side.lower()} (lokasi & %)", "; ".join(f"{a.strip()} {c}" for a, _, c in rep),
              "; ".join(f"{l['name']} {q.fmt_num(l[pct], 2)}" for l in d[key]))


SCENARIOS = {
    "processing": [(None, None, "default (tanpa filter)"), (date(2026, 1, 1), date(2026, 10, 14), "filter screenshot"),
                   (date(2026, 10, 1), date(2026, 10, 14), "1-14 Okt"), (date(2026, 3, 5), date(2026, 6, 20), "5 Mar-20 Jun"),
                   (date(2026, 8, 15), date(2026, 8, 15), "1 hari")],
    "equipment": [(date(2026, 8, 1), date(2026, 8, 1), "filter screenshot"), (None, None, "default (tanpa filter)"),
                  (date(2026, 9, 1), date(2026, 9, 7), "1-7 Sep")],
    "mining": [(date(2026, 8, 1), date(2026, 8, 3), "filter screenshot"), (date(2026, 10, 1), date(2026, 10, 22), "1-22 Okt"),
               (date(2026, 9, 15), date(2026, 10, 10), "15 Sep-10 Okt")],
    "production": [(date(2026, 4, 1), date(2026, 8, 1), "filter screenshot"), (None, None, "default (tanpa filter)"),
                   (date(2026, 10, 1), date(2026, 10, 22), "1-22 Okt")],
}


def main():
    pages = [a for a in sys.argv[1:] if a in SCENARIOS] or list(SCENARIOS)
    for page in pages:
        for start, end, label in SCENARIOS[page]:
            globals()[page](start, end, label)
    print(f"\nHASIL: {counts['ok']} sama, {counts['known']} beda karena bug report (disengaja), {counts['bad']} beda")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
