"""Query dashboard Picking Slip ke semantic model "All Site - SCM - Picking Slip" (workspace ALLDATASET).

Halaman diambil dari measure HTML di model itu (lihat measure_html.py):
  Summary : dax_picking_slip_summary_v9        -> dax/summary.dax
  Detail  : dax_picking_slip_detail_header_v5  -> dax/detail.dax
Data setiap VAR CONCATENATEX dibaca sebagai tabel (batas executeQueries: 100.000 baris per query).
"""
from pathlib import Path

from ...config import Config
from ...core.cache import Cache
from ...core.common import now_wib, stamp_info  # noqa: F401  (stamp_info dipakai routes.py)
from ...core.powerbi import DATA_ERRORS, Dataset, query  # noqa: F401  (DATA_ERRORS dipakai routes.py)
from .measure_html import Measure, join_rows

# ID dari URL Power BI: app.powerbi.com/groups/<WORKSPACE_ID>/datasets/<DATASET_ID>/...
# Bisa ditimpa lewat .env: PICKING_SLIP_WORKSPACE_ID / PICKING_SLIP_DATASET_ID
DATASET = Dataset("PICKING_SLIP", workspace_id="3c13f5a0-78cb-4372-82eb-aa271bf8dc85",
                  dataset_id="30233aea-63d6-4d77-876f-5a3806305d02")

_DAX_DIR = Path(__file__).resolve().parent / "dax"
MEASURES = {"summary": Measure((_DAX_DIR / "summary.dax").read_text(encoding="utf-8")),
            "detail": Measure((_DAX_DIR / "detail.dax").read_text(encoding="utf-8"))}

_cache = Cache(Config.CACHE_SECONDS)


def page_html(page):
    """HTML lengkap halaman (Summary / Detail) dengan data terbaru. Mengembalikan (html, waktu diambil)."""
    measure = MEASURES[page]

    def load():
        values = {name: join_rows(query(DATASET, dax)) for name, dax in measure.queries().items()}
        values["totalMasterCompCount"] = str(int(query(DATASET, measure.scalar("totalMasterCompCount"))[0]["v"] or 0))
        values["hdLastUpdate"] = now_wib().strftime("%d/%m/%Y")   # di measure: FORMAT ( TODAY (), "dd/MM/yyyy" )
        values["jsPbiFilters"] = ""   # filter visual Power BI: tidak ada di MANTRA, filter dipilih di halaman
        return measure.render(values)
    return _cache.get(("page", page), load)
