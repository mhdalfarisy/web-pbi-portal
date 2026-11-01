"""Tools AI agent Picking Slip. Setiap tool memakai data yang sama dengan halaman (queries.summary_records /
detail_records), jadi angka yang dijawab AI sama dengan kartu & tabel di halaman.

Filter company / status / tanggal yang tidak disebut user berarti semua data (sama dengan halaman tanpa filter).
"""
from collections import defaultdict
from datetime import date

from ...core.chat.guards import ToolArgError, resolve
from ...core.registry import Tool
from . import queries

FILTER_PROPS = {
    "company": {"type": "string", "description": "Kode atau nama company, mis. BTR / PT Batutua Tembaga Raya. Kosongkan untuk semua."},
    "status": {"type": "string", "description": "Status category, mis. Backorder / Picking Slip printed. Kosongkan untuk semua."},
    "start": {"type": "string", "description": "Tanggal awal YYYY-MM-DD (tanggal update picking slip). Kosongkan untuk semua."},
    "end": {"type": "string", "description": "Tanggal akhir YYYY-MM-DD. Kosongkan untuk semua."},
}
MAX_LIMIT = 50


def _filtered(args):
    rows, _ = queries.summary_records()
    start, end = args.get("start"), args.get("end")
    return [r for r in rows
            if (not args.get("company") or r["company"] == args["company"])
            and (not args.get("status") or r["status"] == args["status"])
            and (not args.get("warehouse") or r["warehouse"] == args["warehouse"])
            and (not start or (r["date"] or "") >= start) and (not end or (r["date"] or "") <= end)]


def _filters_used(args):
    return {k: args[k] for k in ("company", "status", "warehouse", "start", "end") if args.get(k)} or "none (all data)"


def tool_status_summary(args, dash):
    rows = _filtered(args)
    by_status, by_group, by_company = defaultdict(lambda: [set(), 0, 0.0]), defaultdict(lambda: [set(), 0.0]), defaultdict(lambda: [set(), 0.0])
    for r in rows:
        ps = (r["company"], r["ps_number"])
        s = by_status[r["status"] or "-"]
        s[0].add(ps); s[1] += r["lines"]; s[2] += r["amount"]
        g = by_group[r["status_group"]]
        g[0].add(ps); g[1] += r["amount"]
        c = by_company[r["company"]]
        c[0].add(ps); c[1] += r["amount"]
    dates = [r["date"] for r in rows if r["date"]]
    return {
        "filters": _filters_used(args),
        "data_range": {"first": min(dates, default=None), "last": max(dates, default=None)},
        "total": {"picking_slips": len({(r["company"], r["ps_number"]) for r in rows}), "lines": sum(r["lines"] for r in rows),
                  "amount": round(sum(r["amount"] for r in rows), 2)},
        "kpi_cards": [{"card": g, "picking_slips": len(v[0]), "amount": round(v[1], 2)}
                      for g, v in sorted(by_group.items(), key=lambda kv: -kv[1][1])],
        "by_status_category": [{"status": s, "picking_slips": len(v[0]), "lines": v[1], "amount": round(v[2], 2)}
                               for s, v in sorted(by_status.items(), key=lambda kv: -kv[1][2])],
        "by_company": [{"company": c, "company_name": queries.companies().get(c, c), "picking_slips": len(v[0]),
                        "amount": round(v[1], 2)} for c, v in sorted(by_company.items(), key=lambda kv: -kv[1][1])],
    }


def tool_top_items(args, dash):
    rows = _filtered(args)
    names = queries.item_names()
    items = defaultdict(lambda: [0.0, 0, set()])
    for r in rows:
        it = items[r["item"]]
        it[0] += r["amount"]; it[1] += r["lines"]; it[2].add((r["company"], r["ps_number"]))
    top = sorted(items.items(), key=lambda kv: -kv[1][0])[:args.get("limit") or 5]
    return {"filters": _filters_used(args), "items": [
        {"item": k, "description": names.get(k, ""), "amount": round(v[0], 2), "lines": v[1], "picking_slips": len(v[2])}
        for k, v in top]}


def tool_find_picking_slips(args, dash):
    rows = _filtered(args)
    slips = {}
    for r in rows:
        key = (r["company"], r["ps_number"])
        s = slips.setdefault(key, {"company": r["company"], "ps_number": r["ps_number"], "status": r["status"],
                                   "warehouse": r["warehouse"], "department": r["department"], "date": r["date"],
                                   "wo_number": r["wo"][0], "wo_description": r["wo"][1], "amount": 0.0, "lines": 0})
        s["amount"] += r["amount"]; s["lines"] += r["lines"]
        s["date"] = max(filter(None, (s["date"], r["date"])), default=None)
    order = sorted(slips.values(), key=lambda s: (-s["amount"], s["ps_number"]) if args.get("sort") == "amount"
                   else (s["date"] or "", s["amount"]), reverse=args.get("sort") != "amount")
    limit = args.get("limit") or 20
    for s in order:
        s["amount"] = round(s["amount"], 2)
    return {"filters": _filters_used(args), "sort": args.get("sort") or "latest", "found": len(order),
            "shown": min(limit, len(order)), "picking_slips": order[:limit]}


def tool_picking_slip_detail(args, dash):
    lines, _ = queries.detail_records()
    number = str(args["ps_number"]).strip().upper()
    match = [r for r in lines if r["ps_number"].upper() == number and (not args.get("company") or r["company"] == args["company"])]
    if not match:
        in_summary = [r for r in _filtered({"company": args.get("company")}) if r["ps_number"].upper() == number]
        return {"ps_number": number, "found": False,
                "note": ("This picking slip exists but has no stocked (SN) lines in the Detail page."
                         if in_summary else "Picking slip number not found. Ask the user to check the number / company.")}
    companies = sorted({r["company"] for r in match})
    if len(companies) > 1:
        return {"ps_number": number, "found": False, "error": "Same PS number in several companies; ask which one.",
                "valid_options": companies}
    head = match[0]
    keep = ("sequence", "type", "item", "item_description", "unit", "ordered_qty", "shipped_qty", "backorder_qty",
            "qty_on_hand", "qty_on_order", "wo_number", "wo_status", "wo_description")
    return {"ps_number": number, "found": True, "company": head["company"], "company_name": head["company_name"],
            "status": head["status"], "warehouse": head["warehouse"], "department": head["department"],
            "order_date": head["order_date"], "required_date": head["required_date"], "update_date": head["update_date"],
            "lines": [{k: r[k] for k in keep} for r in sorted(match, key=lambda r: int(r["sequence"] or 0))]}


TOOLS = [
    Tool("get_status_summary", "Picking slip status summary",
         "Jumlah picking slip, baris, dan amount per kartu KPI (Ready for Picking / In Progress / Finished / Backorder), per "
         "status category, dan per company. Sama dengan kartu & breakdown di halaman Summary.",
         {"type": "object", "properties": FILTER_PROPS, "required": []}, tool_status_summary),
    Tool("get_top_items", "Top picking slip items",
         "Item (stock code) dengan amount picking slip terbesar, sama dengan panel Top 5 Items.",
         {"type": "object", "properties": FILTER_PROPS | {
             "limit": {"type": "integer", "description": f"Jumlah item, default 5, maksimal {MAX_LIMIT}."}}, "required": []},
         tool_top_items),
    Tool("find_picking_slips", "Find picking slips",
         "Daftar picking slip (nomor, company, status, warehouse, tanggal, WO, amount, jumlah baris) sesuai filter.",
         {"type": "object", "properties": FILTER_PROPS | {
             "warehouse": {"type": "string", "description": "Kode warehouse, mis. MAIN. Kosongkan untuk semua."},
             "sort": {"type": "string", "enum": ["latest", "amount"], "description": "latest (default) atau amount terbesar."},
             "limit": {"type": "integer", "description": f"Jumlah baris, default 20, maksimal {MAX_LIMIT}."}}, "required": []},
         tool_find_picking_slips),
    Tool("get_picking_slip_detail", "Picking slip detail",
         "Header dan semua baris item (stocked, SN) satu picking slip: qty ordered/shipped/backorder, stok on hand, WO. "
         "Sama dengan tabel di halaman Detail.",
         {"type": "object", "properties": {
             "ps_number": {"type": "string", "description": "Nomor picking slip, mis. 26542 atau 170864A."},
             "company": FILTER_PROPS["company"]}, "required": ["ps_number"]},
         tool_picking_slip_detail),
]


def clean_args(args):
    """Normalkan company, status, warehouse, tanggal, dan limit dari AI ke nilai asli di data."""
    args = dict(args)
    if args.get("company"):
        names = queries.companies()
        by_name = {v: k for k, v in names.items() if v}
        value = resolve("company", str(args["company"]), set(names) | set(by_name), prefixes=("pt",))
        args["company"] = by_name.get(value, value)
    rows = None
    if args.get("status") or args.get("warehouse"):
        rows, _ = queries.summary_records()
    if args.get("status"):
        args["status"] = resolve("status", str(args["status"]), {r["status"] for r in rows if r["status"]}, prefixes=())
    if args.get("warehouse"):
        args["warehouse"] = resolve("warehouse", str(args["warehouse"]), {r["warehouse"] for r in rows if r["warehouse"]},
                                    prefixes=())
    for key in ("start", "end"):
        if args.get(key):
            try:
                args[key] = date.fromisoformat(str(args[key])[:10]).isoformat()
            except ValueError:
                raise ToolArgError(key, args[key], ["YYYY-MM-DD"]) from None
    if args.get("limit") is not None:
        args["limit"] = max(1, min(MAX_LIMIT, int(args["limit"])))
    return args


def parse_dash(raw):
    """Halaman aktif dari browser: {page} (Summary / Detail)."""
    raw = raw if isinstance(raw, dict) else {}
    return {"page": str(raw.get("page") or "")[:20]}


SUGGESTIONS = [
    "How many picking slips are in Backorder, and what is the amount?",
    "What are the top 5 items by picking slip amount?",
    "Which company has the most picking slips?",
    "Show the latest picking slips that are Ready for Picking.",
]
