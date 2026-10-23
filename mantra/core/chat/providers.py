"""Provider AI. Mesin agent hanya memanggil provider.chat(...), jadi mengganti Gemini ke OpenAI cukup menambah
class baru di sini dan mengubah AI_PROVIDER di .env. Dashboard dan tools tidak perlu diubah."""
import threading

import httpx
from flask import current_app
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from ...config import Config


class AIUnavailable(Exception):
    """Semua model sedang penuh, kena limit, atau tidak merespons."""


class AIError(Exception):
    """Provider menolak permintaan (mis. API key salah)."""

    def __init__(self, code):
        super().__init__(f"AI error {code}")
        self.code = code


class GeminiProvider:
    name = "gemini"

    def __init__(self):
        # Tanpa retry bawaan SDK (yang bisa menunggu lama saat 503): perpindahan ke model cadangan diatur _generate
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY, http_options=types.HttpOptions(
            timeout=20_000, retry_options=types.HttpRetryOptions(attempts=1)))
        self.models = [Config.GEMINI_MODEL] + [m for m in Config.GEMINI_FALLBACK_MODELS if m != Config.GEMINI_MODEL]

    def _generate(self, contents, config, models):
        """Kalau model penuh (503), kena limit (429) atau timeout, coba model berikutnya."""
        for model in models:
            try:
                return self.client.models.generate_content(model=model, contents=contents, config=config), model
            except genai_errors.APIError as exc:
                if exc.code not in (429, 500, 503, 504):
                    raise AIError(exc.code) from exc
                current_app.logger.warning("Gemini %s tidak tersedia (%s), coba model berikutnya", model, exc.code)
            except httpx.TransportError as exc:
                current_app.logger.warning("Gemini %s tidak merespons (%s), coba model berikutnya", model, exc)
        raise AIUnavailable()

    def chat(self, system, history, message, tools, call_tool, max_rounds):
        """history = [{"role": "user"|"model", "text": ...}]. call_tool(name, args) -> dict hasil tool."""
        contents = [types.Content(role="model" if h["role"] == "model" else "user", parts=[types.Part(text=h["text"])])
                    for h in history]
        contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(name=t.name, description=t.description, parameters_json_schema=t.parameters)
                for t in tools])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        models = list(self.models)
        for _ in range(max_rounds):
            response, model = self._generate(contents, config, models)
            models = [model] + [m for m in models if m != model]  # tetap di model yang berhasil
            calls = response.function_calls or []
            if not calls:
                return (response.text or "Maaf, saya tidak mendapatkan jawaban.").strip(), model
            contents.append(response.candidates[0].content)
            parts = [types.Part.from_function_response(name=c.name, response={"result": call_tool(c.name, dict(c.args or {}))})
                     for c in calls]
            contents.append(types.Content(role="user", parts=parts))
        return "Maaf, pertanyaan ini butuh terlalu banyak langkah. Coba dipersempit.", models[0]


PROVIDERS = {"gemini": (GeminiProvider, lambda: bool(Config.GEMINI_API_KEY))}

_provider = None
_provider_lock = threading.Lock()


def configured():
    entry = PROVIDERS.get(Config.AI_PROVIDER)
    return bool(entry and entry[1]())


def get():
    """Provider aktif, atau None kalau belum dikonfigurasi (tombol "Tanya AI" disembunyikan)."""
    global _provider
    if not configured():
        return None
    with _provider_lock:
        if _provider is None:
            _provider = PROVIDERS[Config.AI_PROVIDER][0]()
        return _provider
