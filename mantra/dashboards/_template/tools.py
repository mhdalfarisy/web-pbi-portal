"""Tools AI agent __TITLE__. Setiap tool: fn(args, dash) -> dict yang dikirim ke AI. Jelaskan setiap tool di
prompts/system.md (nama tool di antara backtick), karena itu dicek saat aplikasi start."""
from ...core.registry import Tool
from . import queries


def tool_tables(args, dash):
    rows, _ = queries.tables()
    return {"tables": [r["table"] for r in rows]}


TOOLS = [
    Tool("get_tables", "Daftar tabel", "Daftar tabel di semantic model dashboard ini.",
         {"type": "object", "properties": {}, "required": []}, tool_tables),
]

SUGGESTIONS = ["Tabel apa saja yang ada di semantic model ini?"]
