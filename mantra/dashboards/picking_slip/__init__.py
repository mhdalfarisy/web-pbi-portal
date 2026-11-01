"""Dashboard Picking Slip: Summary & Detail dari measure HTML di semantic model "All Site - SCM - Picking Slip".

Summary dari dax_picking_slip_summary_v9, Detail dari dax_picking_slip_detail_header_v5: DAX di queries.py, tampilan di
templates/ + static/, AI agent di tools.py + prompts/.
"""
from pathlib import Path

from ...core.registry import ChatSpec, Dashboard
from . import queries, tools
from .routes import bp

DASHBOARD = Dashboard(
    slug="picking-slip",
    title="Picking Slip",
    description="Picking slip status, backorder, and line details across all sites.",
    category="Supply Chain",
    icon="truck",
    color="orange",
    dataset=queries.DATASET,
    blueprint=bp,
    pages=[("Summary", "picking_slip.summary"), ("Detail", "picking_slip.detail")],
    chat=ChatSpec(
        tools=tools.TOOLS,
        prompt_dir=Path(__file__).resolve().parent / "prompts",
        suggestions=tools.SUGGESTIONS,
        clean_args=tools.clean_args,
        parse_dash=tools.parse_dash,
    ),
    order=30,
)
