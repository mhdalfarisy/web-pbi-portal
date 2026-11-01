"""Dashboard Picking Slip: Summary & Detail dari measure HTML di semantic model "All Site - SCM - Picking Slip".

Summary dari dax_picking_slip_summary_v9, Detail dari dax_picking_slip_detail_header_v5: DAX di queries.py, tampilan di
templates/ + static/. Belum punya AI agent (chat=None).
"""
from ...core.registry import Dashboard
from . import queries
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
    chat=None,
    order=30,
)
