"""Prompt agent = core/prompts/base.md + semua *.md di folder prompts dashboard (system.md lebih dulu).

Dibaca sekali saat aplikasi start, jadi restart Flask setelah mengubah file prompt. Salah ketik placeholder atau
nama tool membuat aplikasi gagal start, supaya ketahuan sebelum dipakai user.
"""
import re
from pathlib import Path

from ..powerbi import DATA_ERRORS

BASE_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "base.md"
CORE_PLACEHOLDERS = ("today", "year", "month", "month_name", "dashboard_title")
PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
MONTHS_ID = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
             "November", "Desember")  # dipakai chat_cases.py
MONTHS_EN = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
             "November", "December")


def _read(path):
    if not path.is_file():
        raise RuntimeError(f"File prompt tidak ditemukan: {path}")
    # Komentar HTML adalah catatan developer, tidak dikirim ke AI
    return COMMENT_RE.sub("", path.read_text(encoding="utf-8")).strip()


def load(dashboard):
    chat = dashboard.chat
    files = sorted(Path(chat.prompt_dir).glob("*.md"), key=lambda p: (p.name != "system.md", p.name))
    if not files:
        raise RuntimeError(f"Folder prompt {chat.prompt_dir} kosong")
    text = "\n\n".join([_read(BASE_PROMPT)] + [_read(p) for p in files])

    allowed = set(CORE_PLACEHOLDERS) | set(chat.placeholders)
    unknown = set(PLACEHOLDER_RE.findall(text)) - allowed
    if unknown:
        raise RuntimeError(f"[{dashboard.slug}] placeholder tidak dikenal di prompt: {', '.join(sorted(unknown))}. "
                           f"Yang tersedia: {', '.join(sorted(allowed))}")
    tools = set(chat.tool_map)
    named = set(re.findall(r"`(get_\w+|lookup\w*)`", text))
    if named - tools:
        raise RuntimeError(f"[{dashboard.slug}] tool tidak dikenal di prompt: {', '.join(sorted(named - tools))}")
    missing = {t for t in tools if f"`{t}`" not in text}
    if missing:
        raise RuntimeError(f"[{dashboard.slug}] tool belum dijelaskan di prompt: {', '.join(sorted(missing))}")
    chat.template = text


def values(dashboard, now):
    month_name = MONTHS_EN[now.month - 1]
    result = {"today": f"{now.day} {month_name} {now.year}", "year": str(now.year), "month": str(now.month),
              "month_name": month_name, "dashboard_title": dashboard.title}
    if dashboard.chat.prompt_values:
        try:
            result.update(dashboard.chat.prompt_values())
        except DATA_ERRORS:  # mis. daftar company gagal diambil: prompt tetap jalan tanpa daftar itu
            result.update({k: "-" for k in dashboard.chat.placeholders})
    return result


def render(dashboard, now):
    vals = values(dashboard, now)
    return PLACEHOLDER_RE.sub(lambda m: str(vals.get(m.group(1), "-")), dashboard.chat.template)
