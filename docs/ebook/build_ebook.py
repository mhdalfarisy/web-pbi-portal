"""Bangun ebook PDF dari dokumentasi di docs/ (panduan berurutan + development playbook + AUTH.md).

Pemakaian (dari root project):
    python docs/ebook/build_ebook.py

Butuh: pandoc 3.x (brew install pandoc) dan Google Chrome (untuk menggambar diagram mermaid & mencetak PDF).
Hasil: docs/ebook/MANTRA_Development_Ebook.pdf. File kerja sementara ada di docs/ebook/.build/ (boleh dihapus).

Urutan bab diatur di PARTS. Link antar dokumen menjadi link internal PDF; link ke file kode (mantra/, scripts/, ...)
menjadi teks path, karena file kode tidak ada di dalam ebook.
"""
import os
import re
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

EBOOK = Path(__file__).resolve().parent
DOCS = EBOOK.parent
ROOT = DOCS.parent
BUILD = EBOOK / ".build"
SRC = BUILD / "src"
OUT = EBOOK / "MANTRA_Development_Ebook.pdf"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"

PB = "development_playbook"
PD = "panduan_development"
PARTS = [
    ("Bagian I — Mulai di Sini", "Gambaran project, struktur folder, dan cara membaca buku ini.",
     [f"{PB}/00_START_HERE.md", f"{PB}/01_PROJECT_OVERVIEW.md", f"{PB}/02_PROJECT_STRUCTURE.md"]),
    ("Bagian II — Jalur Utama: Membangun dari Nol", "Urutan development lengkap dengan file yang dikerjakan di setiap langkah.",
     ["PANDUAN_DEVELOPMENT_BERURUTAN.md", f"{PB}/03_DEVELOPMENT_ROADMAP.md", f"{PB}/27_REBUILD_FROM_ZERO.md"]),
    ("Bagian III — Pendalaman: Konsep, Kode Inti, Logika Bisnis",
     "Penjelasan konsep tiap teknologi, kode inti baris per baris, dan asal setiap angka dashboard.",
     [f"{PD}/01_KONSEP_TEKNOLOGI.md", f"{PD}/02_KODE_INTI_FONDASI.md", f"{PD}/03_KODE_INTI_DATA_DAN_AI.md",
      f"{PD}/04_LOGIKA_BISNIS_DASHBOARD.md"]),
    ("Bagian IV — Setup & Menjalankan di macOS", "Environment, dependency, konfigurasi, dan menjalankan server lokal.",
     [f"{PB}/04_MACOS_VSCODE_SETUP.md", f"{PB}/05_PYTHON_ENVIRONMENT_AND_DEPENDENCIES.md",
      f"{PB}/06_CONFIGURATION_GUIDE.md", f"{PB}/22_LOCALHOST_RUNBOOK.md"]),
    ("Bagian V — Arsitektur", "Cara kerja Flask, frontend, backend, database, login, portal, registry, dan Power BI.",
     [f"{PB}/07_FLASK_STARTUP_AND_REQUEST_LIFECYCLE.md", f"{PB}/08_FRONTEND_ARCHITECTURE.md",
      f"{PB}/09_BACKEND_ARCHITECTURE.md", f"{PB}/10_FRONTEND_BACKEND_CONTRACT.md",
      f"{PB}/11_DATABASE_AND_MIGRATIONS.md", f"{PB}/12_AUTHENTICATION_AUTHORIZATION.md",
      f"{PB}/13_PORTAL_DEVELOPMENT.md", f"{PB}/14_DASHBOARD_REGISTRY.md", f"{PB}/15_POWERBI_INTEGRATION.md"]),
    ("Bagian VI — Workflow Development", "Langkah kerja untuk jenis perubahan yang paling sering.",
     [f"{PB}/26_DEVELOPMENT_DECISION_GUIDE.md", f"{PB}/16_DASHBOARD_PAGE_DEVELOPMENT.md",
      f"{PB}/17_NEW_DASHBOARD_DEVELOPMENT.md", f"{PB}/18_FRONTEND_ONLY_CHANGES.md",
      f"{PB}/19_BACKEND_AND_DATA_CONTRACT_CHANGES.md"]),
    ("Bagian VII — AI Agent", "Mesin AI agent, alur tool calling, prompt, pengujian, dan menambah agent baru.",
     [f"{PB}/20_AI_AGENT_DEVELOPMENT.md", f"{PB}/29_AI_CHAT_FLOW_AND_TOOL_CALLING.md",
      f"{PB}/30_AI_ROLES_AND_ACCESS_CONTROL.md", f"{PB}/31_PROMPT_ENGINEERING_AND_DATA_DICTIONARY.md",
      f"{PB}/32_AI_AGENT_TESTING_AND_GROUNDING.md", f"{PB}/33_ADD_AI_AGENT_TO_DASHBOARD.md"]),
    ("Bagian VIII — Kualitas & Operasional", "Testing, debugging, keamanan, rilis, dan serah terima.",
     [f"{PB}/21_TESTING_AND_REGRESSION.md", f"{PB}/23_DEBUGGING_PLAYBOOK.md", f"{PB}/24_SECURITY_AND_SECRETS.md",
      f"{PB}/25_RELEASE_AND_ROLLBACK.md", f"{PB}/28_PARITY_AND_HANDOVER.md"]),
    ("Lampiran", "Referensi login, role, skema database, migrasi, dan rollback.",
     ["AUTH.md"]),
]

LINK_RE = re.compile(r"(?<!!)\[((?:[^\[\]]|\\\[|\\\])*)\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def key(rel):
    """Nama file sumber di .build/src, juga dipakai pandoc --file-scope sebagai prefix id."""
    return Path(rel).stem.lower().replace("_", "-") + ".md"


def chapter_anchor(rel):
    return "CH-" + Path(rel).stem


def id_prefix(rel):
    """Prefix id yang dipasang pandoc --file-scope untuk heading file ini (nama file tanpa titik)."""
    return key(rel).replace(".", "")


# pandoc --file-scope menambahkan prefix file aktif ke SEMUA link "#...". Link lintas bab diberi penanda CH- (awal bab)
# atau XF- (heading di bab lain) lalu prefix tambahan itu dibuang lagi di fix_links().
CROSS_RE = re.compile(r'href="#[^"]*?__((?:CH|XF)-[^"]+)"')


TABLE_RE = re.compile(r"<table>.*?</table>", re.S)
WIDE_COLUMNS = 7  # tabel selebar ini dicetak di halaman landscape


def fix_links(html):
    return CROSS_RE.sub(lambda m: f'href="#{m.group(1)[3:] if m.group(1).startswith("XF-") else m.group(1)}"', html)


def mark_wide_tables(html):
    def wrap(m):
        head = m.group(0).split("</tr>", 1)[0]
        return f'<div class="wide-table">{m.group(0)}</div>' if head.count("<th") >= WIDE_COLUMNS else m.group(0)
    return TABLE_RE.sub(wrap, html)


def outside_fences(text, fn):
    """Terapkan fn ke baris di luar code block saja."""
    out, fence = [], None
    for line in text.split("\n"):
        m = FENCE_RE.match(line)
        if m:
            marker = m.group(1)
            fence = None if fence == marker else (fence or marker)
            out.append(line)
            continue
        out.append(line if fence else fn(line))
    return "\n".join(out)


def rewrite(rel, text, book):
    here = (DOCS / rel).parent

    def link(m):
        label, target = m.group(1), m.group(2)
        if target.startswith(("http://", "https://", "mailto:")):
            return m.group(0)
        path, _, frag = target.partition("#")
        if not path:  # link di file yang sama: pandoc --file-scope menyesuaikan sendiri
            return m.group(0)
        resolved = (here / path).resolve()
        rel_target = os.path.relpath(resolved, DOCS)
        if rel_target in book:
            anchor = f"#XF-{id_prefix(rel_target)}__{frag}" if frag else f"#{chapter_anchor(rel_target)}"
            return f"[{label}]({anchor})"
        # File di luar ebook (kode, README, scripts): tampilkan path relatif project
        shown = os.path.relpath(resolved, ROOT)
        line = re.fullmatch(r"L(\d+)(?:-L(\d+))?", frag or "")
        if line:
            shown += f":{line.group(1)}" + (f"-{line.group(2)}" if line.group(2) else "")
        plain = label.replace("\\_", "_").strip("`").split(":")[0].rstrip("/")
        file_shown = shown.split(":")[0]
        if plain in (shown, file_shown) or plain.endswith(Path(file_shown).name):
            return f"`{shown}`"
        return f"{label} (`{shown}`)"

    def line_fn(line):
        if line.startswith("#"):
            line = "#" + line  # bab = h2, bagian = h1
        return LINK_RE.sub(link, line)

    body = outside_fences(text, line_fn)
    return f'<a id="{chapter_anchor(rel)}"></a>\n\n{body}\n'


def front_matter(today):
    return f"""<section class="cover">
<div class="cover-kicker">Power BI Portal · MANTRA</div>
<div class="cover-title">Membangun Power BI Portal dari Nol sampai Jadi</div>
<div class="cover-sub">Panduan development berurutan, arsitektur, workflow, AI agent, dan operasional
untuk developer Flask + Power BI</div>
<div class="cover-meta">
<div><b>Muhammad Al-farisy</b></div>
<div>Edisi macOS · {today}</div>
<div>Disusun dari source code <code>web-pbi-portal</code> dan folder <code>docs/</code></div>
</div>
</section>

<section class="about">

<h1>Tentang Buku Ini</h1>

<p>Buku ini menggabungkan seluruh dokumentasi project <b>web-pbi-portal (MANTRA)</b>: panduan development berurutan,
development playbook bab 00–33, dan referensi login &amp; database. Isinya ditulis dari pembacaan source code
aktual, bukan rencana.</p>

<h3>Cara membaca</h3>
<ul>
<li><b>Developer baru:</b> Bagian I → Bagian II (bab "Panduan Development Berurutan") → Bagian IV.</li>
<li><b>Mau membangun ulang dari nol:</b> Bagian II, ikuti fase demi fase; jangan lanjut sebelum "Cek" lulus. Setiap fase
menunjuk bab pendalaman di Bagian III (konsep, kode inti, logika bisnis).</li>
<li><b>Sedang mengerjakan perubahan:</b> Bagian VI (pilih workflow lewat bab 26).</li>
<li><b>Ada error:</b> bab 23 (Debugging) dan bab 26 (Decision Guide).</li>
</ul>

<h3>Konvensi</h3>
<ul>
<li>Semua perintah untuk <b>macOS (zsh)</b>, dijalankan dari root project dengan <code>.venv</code> aktif.
Padanan Windows ada di bab 04 §Q.</li>
<li>Path seperti <code>mantra/core/registry.py:110</code> menunjuk file (dan baris) di repository.</li>
<li>Referensi "dok 05" / "dok 27" berarti bab bernomor sama di buku ini.</li>
</ul>

<h3>Status klaim di playbook</h3>
<table>
<tr><th>Status</th><th>Arti</th></tr>
<tr><td><code>Verified</code></td><td>Kode sudah dibaca dan perilakunya dipastikan dari kode</td></tr>
<tr><td><code>Existing</code></td><td>File/komponen ada, perilaku tertentu belum diperiksa rinci</td></tr>
<tr><td><code>Tested</code></td><td>Perilaku diuji (pytest / script / request ke localhost) dan hasilnya tercatat</td></tr>
<tr><td><code>Pending</code></td><td>Masih perlu diperiksa</td></tr>
<tr><td><code>Not Found</code></td><td>Sudah dicari di cakupan yang jelas dan tidak ada</td></tr>
<tr><td><code>Proposed</code></td><td>Rekomendasi, belum diimplementasikan</td></tr>
<tr><td><code>Not Applicable</code></td><td>Tidak relevan untuk implementasi ini</td></tr>
</table>

<p class="small">Dibangun ulang dengan <code>python docs/ebook/build_ebook.py</code> setiap kali dokumentasi berubah.</p>
</section>
"""


def mermaid_js():
    cached = BUILD / "mermaid.min.js"
    if not cached.exists():
        print("Mengunduh mermaid.js ...")
        urllib.request.urlretrieve(MERMAID_URL, cached)
    return cached


def main():
    for tool, hint in (("pandoc", "brew install pandoc"),):
        if subprocess.run(["which", tool], capture_output=True).returncode:
            sys.exit(f"{tool} tidak ditemukan. Install: {hint}")
    if not Path(CHROME).exists():
        sys.exit(f"Google Chrome tidak ditemukan di {CHROME}")

    SRC.mkdir(parents=True, exist_ok=True)
    for old in SRC.glob("*.md"):
        old.unlink()
    book = {rel for _, _, files in PARTS for rel in files}
    missing = [rel for rel in sorted(book) if not (DOCS / rel).exists()]
    if missing:
        sys.exit(f"Dokumen tidak ditemukan: {', '.join(missing)}")
    unused = sorted(os.path.relpath(p, DOCS) for p in DOCS.rglob("*.md")
                    if ".build" not in p.parts and p.parent != EBOOK)
    unused = [u for u in unused if u not in book and u != f"{PB}/README.md"]
    if unused:
        print("Peringatan: dokumen ini belum masuk PARTS:", ", ".join(unused))

    months = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
              "November", "Desember"]
    today = date.today()
    order = []
    front = BUILD / "front.html"
    front.write_text(front_matter(f"{months[today.month - 1]} {today.year}"), encoding="utf-8")
    for i, (title, intro, files) in enumerate(PARTS, 1):
        name = f"part-{i}.md"
        (SRC / name).write_text(f'# {title} {{.part}}\n\n<p class="part-intro">{intro}</p>\n', encoding="utf-8")
        order.append(name)
        for rel in files:
            text = (DOCS / rel).read_text(encoding="utf-8")
            (SRC / key(rel)).write_text(rewrite(rel, text, book), encoding="utf-8")
            order.append(key(rel))

    html = BUILD / "ebook.html"
    template = EBOOK / "template.html"
    subprocess.run(
        ["pandoc", "--file-scope", "-f", "gfm+attributes", "-t", "html5", "--standalone", "--toc", "--toc-depth=2",
         "--template", str(template), "--css", str(EBOOK / "ebook.css"), "--include-before-body", str(front),
         "--metadata", "title=Membangun Power BI Portal dari Nol sampai Jadi", "--metadata", "lang=id",
         "--metadata", "toc-title=Daftar Isi", "--variable", f"mermaid={mermaid_js()}",
         "--syntax-highlighting=pygments", "-o", str(html), *order],
        cwd=SRC, check=True)
    html.write_text(mark_wide_tables(fix_links(html.read_text(encoding="utf-8"))), encoding="utf-8")

    print("Mencetak PDF dengan Chrome ...")
    subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer", "--generate-pdf-document-outline",
         "--virtual-time-budget=60000", "--run-all-compositor-stages-before-draw", f"--print-to-pdf={OUT}",
         html.as_uri()],
        check=True, capture_output=True)
    print(f"Selesai: {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
