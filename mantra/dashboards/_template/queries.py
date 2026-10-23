"""Query dashboard __TITLE__ ke semantic model Power BI, dengan cache di memori."""
from datetime import datetime, timedelta, timezone

from ...config import Config
from ...core.cache import Cache
from ...core.powerbi import DATA_ERRORS, Dataset, query  # noqa: F401  (DATA_ERRORS dipakai routes.py)

# ID dari URL Power BI: app.powerbi.com/groups/<WORKSPACE_ID>/datasets/<DATASET_ID>/...
# Bisa ditimpa lewat .env: __ENV___WORKSPACE_ID / __ENV___DATASET_ID
DATASET = Dataset("__ENV__", workspace_id="TODO-workspace-id", dataset_id="TODO-dataset-id")
WIB = timezone(timedelta(hours=7))

_cache = Cache(Config.CACHE_SECONDS)


def stamp_info(ts):
    dt = datetime.fromtimestamp(ts, WIB)
    return {"date": dt.strftime("%d/%m/%Y"), "time": dt.strftime("%H:%M WIB")}


def tables():
    """Contoh query: daftar tabel di semantic model. Ganti dengan query dashboard yang sebenarnya."""
    def load():
        return query(DATASET, 'EVALUATE SELECTCOLUMNS(FILTER(INFO.VIEW.TABLES(), NOT [IsHidden]), "table", [Name])')
    return _cache.get("tables", load)
