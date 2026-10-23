"""Dashboard PANI - PRCS - Processing (dalam pengembangan).

Semantic model sudah ditentukan di bawah. Halaman dan AI agent dibuat setelah service principal mantra-powerbi punya
akses ke workspace ini (cek dengan: python scripts\\check_setup.py) dan struktur model sudah dibaca.
"""
from ...core.powerbi import Dataset
from ...core.registry import Dashboard

# ID bisa ditimpa lewat .env: PANI_PROCESSING_WORKSPACE_ID / PANI_PROCESSING_DATASET_ID
DATASET = Dataset("PANI_PROCESSING", workspace_id="f8e25e4f-1d9b-44c5-94b2-069053b7b914",
                  dataset_id="2a7f8bdf-8f64-4fb1-9ba3-c49eb680c9ac")

DASHBOARD = Dashboard(
    slug="pani-processing",
    title="PANI Processing",
    description="Monitor PANI processing (PRCS) performance and operational metrics.",
    category="Operations",
    icon="factory",
    color="teal",
    role="Report.PaniProcessing",
    dataset=DATASET,
    ready=False,
    order=20,
)
