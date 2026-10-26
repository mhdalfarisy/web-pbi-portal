"""Buat dashboard baru dari mantra/dashboards/_template.

Pemakaian:
    python scripts/new_dashboard.py work-order "Work Order"

Hasilnya folder mantra/dashboards/work_order/ dengan halaman contoh, satu tool agent, prompt, dan pertanyaan acuan.
Dashboard baru tampil sebagai "Coming soon" sampai ready=True di __init__.py-nya.
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASHBOARDS = ROOT / "mantra" / "dashboards"
TEMPLATE = DASHBOARDS / "_template"
TEXT_SUFFIXES = {".py", ".md", ".html", ".js", ".css"}


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    slug, title = sys.argv[1].strip().lower(), sys.argv[2].strip()
    if not re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)*", slug):
        sys.exit("Slug harus huruf kecil dipisah tanda minus, mis. work-order")
    name = slug.replace("-", "_")
    target = DASHBOARDS / name
    if target.exists():
        sys.exit(f"Folder {target} sudah ada.")
    tokens = {
        "__SLUG__": slug,
        "__NAME__": name,
        "__TITLE__": title,
        "__ENV__": name.upper(),
        "__ROLE__": "Report." + "".join(part.capitalize() for part in slug.split("-")),
    }

    shutil.copytree(TEMPLATE, target, ignore=shutil.ignore_patterns("__pycache__"))
    for path in sorted(target.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8")
            for token, value in tokens.items():
                text = text.replace(token, value)
            path.write_text(text, encoding="utf-8")
        if "__NAME__" in path.name:
            path.rename(path.with_name(path.name.replace("__NAME__", name)))

    print(f"Dashboard dibuat: {target.relative_to(ROOT)}")
    print("Langkah berikutnya:")
    print(f"  1. Isi workspace_id & dataset_id di {target.relative_to(ROOT)}\\queries.py")
    print("  2. Start Flask: dashboard otomatis masuk katalog. Beri akses user di Admin > Users (Super Admin otomatis bisa)")
    print("  3. Beri mantra-powerbi akses ke workspace-nya, lalu: python scripts\\check_setup.py")
    print(f"  4. Restart Flask dan buka http://localhost:<PORT dari .env, default 5001>/d/{slug}/")


if __name__ == "__main__":
    main()
