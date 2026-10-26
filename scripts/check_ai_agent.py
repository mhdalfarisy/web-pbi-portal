"""Tes regresi AI agent. Jalankan setelah mengubah prompt (core/prompts, dashboards/*/prompts) atau tools.py.

Pemakaian:
    python scripts/check_ai_agent.py --static                              cek statis semua agent (gratis)
    python scripts/check_ai_agent.py --dashboard material-readiness        cek statis + pertanyaan acuan
    python scripts/check_ai_agent.py --dashboard material-readiness lookup hanya kasus yang namanya mengandung "lookup"

Cek statis : prompt terbaca, placeholder & nama tool valid, pengaman parameter (status, company, week).
Kasus      : pertanyaan acuan di dashboards/<nama>/chat_cases.py. Jawaban acuan dihitung dari semantic model saat
             tes berjalan. Setiap kasus memakai kuota AI. Jawaban AI bisa sedikit berbeda tiap kali dijalankan:
             kalau satu kasus gagal, jalankan ulang kasus itu sebelum mengubah prompt.
"""
import argparse
import importlib
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mantra.core import registry  # noqa: E402
from mantra.core.chat import guards, prompt  # noqa: E402

failed = 0


def check(label, fn):
    global failed
    try:
        ok, detail = fn(), ""
    except Exception as exc:  # noqa: BLE001
        ok, detail = False, f"{type(exc).__name__}: {exc}"
    failed += ok is not True
    print(f"  {'OK   ' if ok is True else 'GAGAL'} {label}{'  -> ' + detail if detail else ''}")


def static_checks(dashboards):
    print("== Cek statis: pengaman parameter ==")
    po = {"FP Ready", "FP In Progress", "FP Approval", "FP Not Ready"}
    so = {"All Ready", "All Inprogress", "All Not Ready", "On Hold"}
    companies = {"PT Merdeka Mining Indonesia", "PT Bumi Suksesindo", "PT Batutua Tembaga Raya", "Unidentified"}
    for value, options, expected in (("not ready", po, "FP Not Ready"), ("ready", po, "FP Ready"),
                                     ("In Progress", po, "FP In Progress"), ("not ready", so, "All Not Ready"),
                                     ("in progress", so, "All Inprogress"), ("on hold", so, "On Hold"),
                                     ("merdeka mining", companies, "PT Merdeka Mining Indonesia")):
        check(f"'{value}' -> {expected}", lambda v=value, o=options, e=expected: guards.resolve("x", v, o) == e)

    def ambiguous():
        try:
            guards.resolve("company", "PT", companies)
        except guards.ToolArgError as exc:
            return bool(exc.result()["valid_options"])
        return False
    check("'PT' ambigu -> error + valid_options", ambiguous)
    weeks = {"44 - 2026", "1 - 2026"}
    for value, expected in (("week 44 2026", "44 - 2026"), ("2026 W44", "44 - 2026"), ("01-2026", "1 - 2026")):
        check(f"week '{value}' -> {expected}", lambda v=value, e=expected: guards.resolve_week(v, weeks) == e)

    for d in dashboards:
        if not d.chat:
            continue
        print(f"\n== Cek statis: prompt agent {d.slug} ==")
        check("prompt terbaca, placeholder & nama tool valid", lambda d=d: prompt.load(d) is None)
        check("komentar developer tidak ikut terkirim", lambda d=d: "<!--" not in d.chat.template)
        dummy = {k: f"<{k}>" for k in prompt.CORE_PLACEHOLDERS + tuple(d.chat.placeholders)}
        check("semua placeholder bisa diisi", lambda d=d, v=dummy: not prompt.PLACEHOLDER_RE.search(
            prompt.PLACEHOLDER_RE.sub(lambda m: v[m.group(1)], d.chat.template)))


def run_cases(slug, name_filter):
    from mantra import create_app
    from mantra.core.chat import engine

    app = create_app()
    dashboard = registry.get(slug)
    if dashboard is None or not dashboard.chat:
        sys.exit(f"Dashboard '{slug}' tidak ada atau tidak punya AI agent.")
    module_name = next(n for n in registry.module_names() if importlib.import_module(n).DASHBOARD.slug == slug)
    cases = importlib.import_module(f"{module_name}.chat_cases").CASES
    global failed
    with app.test_request_context("/"):
        vals = prompt.values(dashboard, datetime.now())
        check("prompt_values mengisi semua placeholder",
              lambda: set(prompt.CORE_PLACEHOLDERS + tuple(dashboard.chat.placeholders)) <= set(vals))
        for case_fn in cases:
            name = case_fn.__name__.removeprefix("case_")
            if name_filter and name_filter not in name:
                continue
            print(f"\n== {slug} / {name} ==")
            case = case_fn()
            if "skip" in case:
                print(f"  LEWAT {case['skip']}")
                continue
            print(f"  Q: {case['question']}")
            start = time.time()
            try:
                answer, used, model = engine.answer(dashboard, case["question"], [], case["context"], case["filters"])
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  GAGAL error {type(exc).__name__}: {exc}")
                continue
            print(f"  tools: {[(u['name'], u['args']) for u in used]}  | {model} | {time.time() - start:.1f}s")
            print("  A: " + answer.replace("\n", "\n     "))
            for label, ok in case["checks"](answer, used):
                failed += not ok
                print(f"  {'OK   ' if ok else 'GAGAL'} {label}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dashboard", help="slug dashboard yang pertanyaan acuannya dijalankan")
    parser.add_argument("--static", action="store_true", help="hanya cek statis")
    parser.add_argument("filter", nargs="?", default="", help="hanya kasus yang namanya mengandung teks ini")
    args = parser.parse_args()

    dashboards = registry.manifests()
    if args.dashboard:
        dashboards = [d for d in dashboards if d.slug == args.dashboard]
    static_checks(dashboards)
    if args.dashboard and not args.static:
        run_cases(args.dashboard, args.filter)
    print(f"\n{'SEMUA LULUS' if not failed else f'{failed} cek GAGAL'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
