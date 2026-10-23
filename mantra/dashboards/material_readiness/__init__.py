"""Dashboard Material Readiness: kesiapan material PO/SO per work order.

Semantic model: "All Site - AMNT - Material Readiness" (lihat queries.DATASET). Hanya branch FP & ME.
"""
from pathlib import Path

from ...core.registry import ChatSpec, Dashboard
from . import queries, tools
from .routes import bp

DASHBOARD = Dashboard(
    slug="material-readiness",
    title="Material Readiness",
    description="Monitor material availability, stock, and readiness status across all sites and categories.",
    category="Operations",
    icon="chart",
    color="blue",
    role="Report.MaterialReadiness",
    dataset=queries.DATASET,
    blueprint=bp,
    pages=[("Summary", "material_readiness.summary"), ("Detail", "material_readiness.detail")],
    chat=ChatSpec(
        tools=tools.TOOLS,
        prompt_dir=Path(__file__).resolve().parent / "prompts",
        suggestions=tools.SUGGESTIONS,
        clean_args=tools.clean_args,
        parse_dash=tools.parse_dash,
        placeholders=("branches", "companies"),
        prompt_values=tools.prompt_values,
    ),
    order=10,
)
