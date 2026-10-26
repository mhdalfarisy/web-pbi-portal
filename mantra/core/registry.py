"""Daftar dashboard di portal.

Setiap folder di mantra/dashboards/ (kecuali yang diawali "_") yang punya variabel DASHBOARD otomatis terdaftar:
kartunya muncul di halaman Reports, halamannya dipasang di /d/<slug>/, dan AI agent-nya di /d/<slug>/api/chat.
"""
import importlib
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from . import accounts, auth, db


@dataclass
class Tool:
    """Satu tool AI agent. parameters = JSON schema; fn(args, dash) -> dict hasil yang dikirim ke AI."""
    name: str
    label: str
    description: str
    parameters: dict
    fn: Callable


@dataclass
class ChatSpec:
    """AI agent milik satu dashboard."""
    tools: list
    prompt_dir: Path
    suggestions: list = field(default_factory=list)
    clean_args: Callable | None = None     # normalkan parameter dari AI sebelum tool dijalankan
    parse_dash: Callable | None = None     # ubah filter dashboard dari browser jadi dict untuk tool
    placeholders: tuple = ()               # placeholder tambahan di prompt, nilainya dari prompt_values()
    prompt_values: Callable | None = None
    template: str = ""                     # diisi saat start oleh core.chat.prompt.load()

    @property
    def tool_map(self):
        return {t.name: t for t in self.tools}


@dataclass
class Dashboard:
    slug: str                    # URL: /d/<slug>/
    title: str
    description: str
    category: str                # kategori di halaman Reports, mis. Operations
    icon: str                    # nama ikon di templates/portal/_ui.html
    color: str                   # warna kartu: blue, green, orange, purple, teal, red, indigo, cyan, slate
    role: str                    # label lama (app role Entra). Hak akses sekarang dari database: Admin > Users
    dataset: object = None       # core.powerbi.Dataset
    blueprint: Blueprint | None = None
    pages: list = field(default_factory=list)   # [(label, endpoint)] menu di header dashboard
    chat: ChatSpec | None = None
    ready: bool = True           # False = kartu tampil sebagai "Coming soon"
    order: int = 100             # urutan kartu

    @property
    def url(self):
        return url_for(self.pages[0][1]) if self.ready and self.pages else None


_DASHBOARDS = {}
_BY_BLUEPRINT = {}


def all_dashboards():
    return sorted(_DASHBOARDS.values(), key=lambda d: (d.order, d.title))


def get(slug):
    return _DASHBOARDS.get(slug)


def current():
    """Dashboard milik request yang sedang berjalan (dipakai template dashboard)."""
    return _BY_BLUEPRINT.get(request.blueprint)


def visible_for(user):
    return [d for d in all_dashboards() if auth.can_open(user, d)]


def _guard(dashboard):
    """Pasang login + cek hak akses (database) di SETIAP route dashboard: halaman, API data, dan file static.
    Dashboard yang tidak diizinkan ditolak 403 walaupun URL-nya dibuka langsung. Halaman yang dibuka dicatat ke History."""
    page_endpoints = {endpoint: label for label, endpoint in dashboard.pages}

    def check():
        is_api = "/api/" in request.path
        user = auth.current_user()
        if user is None:
            if is_api:
                return jsonify(error="Sesi login habis, silakan muat ulang halaman."), 401
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        if not auth.can_open(user, dashboard):
            accounts.audit("access_denied", "dashboard", dashboard.slug, actor=user, path=request.path)
            if is_api:
                return jsonify(error="Tidak punya akses ke dashboard ini."), 403
            return render_template("portal/denied.html", dashboard=dashboard), 403
        if request.method == "GET" and request.endpoint in page_endpoints:
            db.add_history(user["id"], dashboard.slug, f"{dashboard.title} · {page_endpoints[request.endpoint]}",
                           request.full_path.rstrip("?"))
        return None
    return check


def _load(app, module_name):
    from .chat import prompt  # import di sini supaya registry tidak bergantung pada mesin chat saat diimport

    module = importlib.import_module(module_name)
    dashboard = getattr(module, "DASHBOARD", None)
    if not isinstance(dashboard, Dashboard):
        raise RuntimeError(f"{module_name} tidak punya variabel DASHBOARD = Dashboard(...)")
    if dashboard.slug in _DASHBOARDS:
        raise RuntimeError(f"Slug dashboard dobel: {dashboard.slug}")
    if dashboard.ready and not (dashboard.blueprint and dashboard.pages):
        raise RuntimeError(f"Dashboard {dashboard.slug} ready=True tapi belum punya blueprint/pages")
    if dashboard.chat:
        prompt.load(dashboard)  # gagal di sini kalau file prompt rusak (placeholder / nama tool salah)
    if dashboard.blueprint is not None:
        dashboard.blueprint.before_request(_guard(dashboard))
        app.register_blueprint(dashboard.blueprint)
        _BY_BLUEPRINT[dashboard.blueprint.name] = dashboard
    _DASHBOARDS[dashboard.slug] = dashboard


def module_names():
    """Nama modul semua folder dashboard (kecuali yang diawali "_")."""
    from .. import dashboards

    return [f"{dashboards.__name__}.{info.name}" for info in pkgutil.iter_modules(dashboards.__path__)
            if info.ispkg and not info.name.startswith("_")]


def manifests():
    """Semua DASHBOARD tanpa memasangnya ke Flask (dipakai script di folder scripts/)."""
    return [importlib.import_module(name).DASHBOARD for name in module_names()]


def init_app(app):
    for name in module_names():
        try:
            _load(app, name)
        except Exception:
            if app.config["DASHBOARD_STRICT"]:
                raise
            app.logger.exception("Dashboard %s gagal dimuat dan disembunyikan", name)
