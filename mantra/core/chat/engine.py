"""Menjalankan satu pertanyaan ke agent sebuah dashboard: prompt + tools dashboard, provider dari .env."""
from datetime import datetime

from flask import current_app

from ..common import WIB
from ..errors import log_data_error
from ..powerbi import DATA_ERRORS
from . import prompt, providers
from .guards import ToolArgError, add_hint

MAX_MESSAGE = 1000
MAX_HISTORY = 20
MAX_TOOL_ROUNDS = 6


def _clean_history(history):
    items = []
    for h in (history if isinstance(history, list) else [])[-MAX_HISTORY:]:
        if not isinstance(h, dict):
            continue
        text = str(h.get("text") or "")[:4000]
        if text:
            items.append({"role": "model" if h.get("role") == "model" else "user", "text": text})
    return items


def answer(dashboard, message, history, context, raw_filters):
    """Kembalikan (jawaban, tools yang dipakai, model). Lempar providers.AIUnavailable / AIError kalau AI gagal."""
    chat = dashboard.chat
    provider = providers.get()
    dash = chat.parse_dash(raw_filters) if chat.parse_dash else {}
    tool_map = chat.tool_map
    used = []

    def call_tool(name, args):
        tool = tool_map.get(name)
        if tool is None:
            return {"error": f"Unknown tool {name}"}
        try:
            if chat.clean_args:
                args = chat.clean_args(args)
            result = add_hint(tool.fn(args, dash))
        except ToolArgError as exc:
            result = exc.result()
        except DATA_ERRORS as exc:
            # Detail error (ID workspace/dataset, isi respons) hanya ke log, tidak dikirim ke AI
            result = {"error": f"Power BI data is temporarily unavailable (ref {log_data_error(exc)}). "
                               "Tell the user and do not guess any numbers."}
        except Exception:  # noqa: BLE001  satu tool rusak tidak boleh menggagalkan seluruh percakapan
            current_app.logger.exception("Tool %s gagal (args %s)", name, args)
            result = {"error": "This tool failed to run. Tell the user the data could not be retrieved; "
                               "do not guess any numbers."}
        used.append({"name": name, "label": tool.label, "args": args})
        return result

    system = prompt.render(dashboard, datetime.now(WIB))
    prefix = f"[Active dashboard filters: {context}]\n" if context else ""
    text, model = provider.chat(system, _clean_history(history), prefix + message, chat.tools, call_tool,
                                MAX_TOOL_ROUNDS)
    return text, used, model
