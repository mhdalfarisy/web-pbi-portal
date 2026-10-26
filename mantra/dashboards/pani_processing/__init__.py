"""Dashboard PANI: 4 report dari semantic model "PANI - PRCS - Processing" (workspace PANI-MCG).

Halaman: Processing, Equipment Performance, Mining Production, Production (stockpile). Angka direkonstruksi dari tabel
model (rumus DAX measure report tidak bisa dibaca service principal) dan divalidasi terhadap screenshot report.
"""
from pathlib import Path

from ...core.registry import ChatSpec, Dashboard
from . import queries, tools
from .routes import bp

DATASET = queries.DATASET

DASHBOARD = Dashboard(
    slug="pani-processing",
    title="PANI Processing",
    description="Processing, equipment, mining, and stockpile production performance for PANI Gold Project.",
    category="Operations",
    icon="factory",
    color="teal",
    dataset=DATASET,
    blueprint=bp,
    pages=[("Processing", "pani_processing.processing"), ("Equipment", "pani_processing.equipment"),
           ("Mining", "pani_processing.mining"), ("Production", "pani_processing.production")],
    chat=ChatSpec(
        tools=tools.TOOLS,
        prompt_dir=Path(__file__).resolve().parent / "prompts",
        suggestions=tools.SUGGESTIONS,
        clean_args=tools.clean_args,
        parse_dash=tools.parse_dash,
    ),
    order=20,
)
