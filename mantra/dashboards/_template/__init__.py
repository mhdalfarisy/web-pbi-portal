"""Dashboard __TITLE__ (dibuat dari dashboards/_template oleh scripts/new_dashboard.py).

Langkah berikutnya:
1. Isi workspace_id & dataset_id di queries.py, lalu cek: python scripts\\check_setup.py
2. Setelah Flask start, dashboard otomatis masuk katalog; beri akses user di Admin > Users.
3. Ganti query contoh di queries.py, halaman di templates/, tools agent di tools.py, dan prompt di prompts/.
4. Ubah ready=True di bawah, restart Flask.
"""
from pathlib import Path

from ...core.registry import ChatSpec, Dashboard
from . import queries, tools
from .routes import bp

DASHBOARD = Dashboard(
    slug="__SLUG__",
    title="__TITLE__",
    description="TODO: satu kalimat untuk kartu di halaman Reports.",
    category="Others",
    icon="chart",
    color="slate",
    role="__ROLE__",
    dataset=queries.DATASET,
    blueprint=bp,
    pages=[("Overview", "__NAME__.overview")],
    chat=ChatSpec(
        tools=tools.TOOLS,
        prompt_dir=Path(__file__).resolve().parent / "prompts",
        suggestions=tools.SUGGESTIONS,
    ),
    ready=False,  # True setelah halaman & agent selesai; selama False kartunya tampil "Coming soon"
)
