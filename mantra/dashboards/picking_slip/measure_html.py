"""Jalankan measure "HTML report" Power BI di MANTRA tanpa batas panjang teks DAX.

Measure seperti dax_picking_slip_summary_v9 berbentuk:
    VAR jsRaw = CONCATENATEX ( <tabel>, <teks satu baris>, SEP_R )   -- data, digabung jadi satu teks
    VAR icDoc = svgO & "<path .../>"                                    -- teks statis (ikon SVG, warna)
    RETURN "<html> ... var RAW_TXT = '" & jsRaw & "'; ... </html>"

Dijalankan utuh di Power BI, hasilnya gagal kalau teks gabungan > ~2,1 juta karakter (batas fungsi DAX). Di sini
setiap VAR CONCATENATEX dijalankan sebagai query tabel (satu baris hasil = satu baris data, memakai rumus <teks satu
baris> yang sama persis), lalu digabung di Python dengan pemisah yang sama. HTML, CSS, dan JS diambil apa adanya dari
RETURN measure. File .dax di folder dax/ adalah salinan persis kode measure: untuk update, tempel versi baru di sana.
"""
import re

SEP_R = ""   # UNICHAR(57345): pemisah baris di measure
_PREFIX = "DEFINE\nVAR SEP_F = UNICHAR ( 57344 )\nVAR SEP_R = UNICHAR ( 57345 )\n"


def _skip(text, i):
    """Kalau text[i] membuka string "..", identifier '..', kolom [..], atau komentar --, kembalikan index setelahnya."""
    ch = text[i]
    if ch == '"':
        j = i + 1
        while True:
            j = text.index('"', j)
            if text.startswith('""', j):
                j += 2
                continue
            return j + 1
    if ch == "'":
        return text.index("'", i + 1) + 1
    if ch == "[":
        return text.index("]", i) + 1
    if text.startswith("--", i):
        j = text.find("\n", i)
        return len(text) if j < 0 else j
    return None


def _depths(text):
    """{index: kedalaman kurung} untuk karakter kode (di luar string, identifier, dan komentar)."""
    depth, i, out = 0, 0, {}
    while i < len(text):
        j = _skip(text, i)
        if j is not None:
            i = j
            continue
        depth += text[i] == "("
        depth -= text[i] == ")"
        out[i] = depth
        i += 1
    return out


def _without_comments(text):
    out, i = [], 0
    while i < len(text):
        j = _skip(text, i)
        if j is None:
            out.append(text[i])
            i += 1
        else:
            if not text.startswith("--", i):
                out.append(text[i:j])
            i = j
    return "".join(out)


def _top_level(dax):
    """({nama VAR: ekspresi}, ekspresi RETURN) untuk VAR di luar kurung (bukan VAR di dalam CONCATENATEX)."""
    depth = _depths(dax)

    def outside(m):
        k = m.start() + len(m.group(0)) - len(m.group(0).lstrip())
        return depth.get(k) == 0

    heads = [m for m in re.finditer(r"(?m)^[ \t]*VAR (\w+)\s*=", dax) if outside(m)]
    ret = next(m for m in re.finditer(r"(?m)^[ \t]*RETURN\b", dax) if outside(m))
    heads = [m for m in heads if m.start() < ret.start()]
    found = {}
    for k, m in enumerate(heads):
        end = heads[k + 1].start() if k + 1 < len(heads) else ret.start()
        found[m.group(1)] = _without_comments(dax[m.end():end]).strip()
    return found, dax[ret.end():]


def _args(expr):
    """Argumen tingkat atas pemanggilan fungsi pertama di expr, mis. CONCATENATEX ( a, b, c ) -> [a, b, c]."""
    start = expr.index("(")
    args, depth, i, last = [], 0, start, start + 1
    while i < len(expr):
        j = _skip(expr, i)
        if j is not None:
            i = j
            continue
        if expr[i] == "(":
            depth += 1
        elif expr[i] == ")":
            depth -= 1
            if depth == 0:
                args.append(expr[last:i].strip())
                return args
        elif expr[i] == "," and depth == 1:
            args.append(expr[last:i].strip())
            last = i + 1
        i += 1
    raise ValueError("kurung tidak seimbang")


def _concat(expr, env):
    """Nilai rangkaian "teks" & VAR & "teks" (tanpa fungsi). Gagal (KeyError/ValueError) kalau ada yang lain."""
    parts, i = [], 0
    while i < len(expr):
        if expr[i].isspace() or expr[i] == "&":
            i += 1
        elif expr[i] == '"':
            j = _skip(expr, i)
            parts.append(expr[i + 1:j - 1].replace('""', '"'))
            i = j
        else:
            m = re.match(r"\w+", expr[i:])
            if not m:
                raise ValueError(f"bukan rangkaian teks: {expr[i:i + 30]!r}")
            parts.append(env[m.group(0)])
            i += m.end()
    return "".join(parts)


class Measure:
    """Measure HTML yang sudah diurai: data (query tabel), teks statis, dan RETURN (template HTML)."""

    def __init__(self, dax):
        found, self.html = _top_level(dax)
        self.static, self.data, self.other = {}, {}, {}
        for name, expr in found.items():
            if expr.startswith("CONCATENATEX"):
                table, row, *_ = _args(expr)
                self.data[name] = (table, row)
                continue
            try:
                self.static[name] = _concat(expr, self.static)
            except (KeyError, ValueError):
                self.other[name] = expr   # filter Power BI, tanggal, angka: diisi lewat render(values)

    def queries(self):
        """{nama VAR data: query DAX yang mengembalikan satu kolom "r" (satu baris teks per baris data)}."""
        out = {}
        for name, (table, row) in self.data.items():
            uses = [n for n in self.other if re.search(rf"\b{n}\b", table)]   # mis. tabel = VAR grp
            define = "".join(f"VAR {n} = {self.other[n]}\n" for n in uses)
            out[name] = f'{_PREFIX}{define}EVALUATE SELECTCOLUMNS ( {table}, "r", {row} )'
        return out

    def scalar(self, name):
        """Query DAX satu nilai untuk VAR lain, mis. totalMasterCompCount."""
        return f'{_PREFIX}EVALUATE ROW ( "v", {self.other[name]} )'

    def render(self, values):
        """HTML akhir. values: teks data (sudah digabung) + nilai VAR lain yang dipakai RETURN."""
        return _concat(self.html, {**self.static, **values})


def join_rows(rows):
    """Gabungkan hasil query tabel persis seperti CONCATENATEX ( ..., SEP_R ) di measure."""
    return SEP_R.join(r["r"] or "" for r in rows)
