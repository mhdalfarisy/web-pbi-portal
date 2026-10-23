"""Akses semantic model Power BI lewat service principal "mantra-powerbi" (MSAL client credentials).

Satu token dan satu koneksi HTTP dipakai bersama oleh semua dashboard. Setiap dashboard menunjuk semantic model-nya
sendiri lewat Dataset(...). Batas query per menit juga berlaku bersama, karena kuota Power BI dihitung per service
principal, bukan per dashboard.
"""
import os
import re
import threading
import time
from collections import deque
from dataclasses import dataclass

import msal
import requests

from ..config import Config

API = "https://api.powerbi.com/v1.0/myorg"
SCOPE = ["https://analysis.windows.net/powerbi/api/.default"]


class PowerBIError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


# Error yang ditangkap route & agent untuk ditampilkan sebagai "gagal mengambil data"
DATA_ERRORS = (PowerBIError, requests.RequestException)


@dataclass(frozen=True)
class Dataset:
    """Semantic model milik satu dashboard.

    ID bisa ditimpa lewat .env (<env_prefix>_WORKSPACE_ID / <env_prefix>_DATASET_ID), mis. untuk dataset dev vs prod.
    """
    env_prefix: str
    workspace_id: str
    dataset_id: str

    @property
    def ids(self):
        return (os.environ.get(f"{self.env_prefix}_WORKSPACE_ID") or self.workspace_id,
                os.environ.get(f"{self.env_prefix}_DATASET_ID") or self.dataset_id)

    @property
    def path(self):
        workspace_id, dataset_id = self.ids
        return f"/groups/{workspace_id}/datasets/{dataset_id}"


def _clean_column(name):
    """'Material'[Plant] -> Plant, [Readiness %] -> Readiness %"""
    match = re.search(r"\[([^\]]+)\]$", name)
    return match.group(1) if match else name


class _RateLimiter:
    """Maksimal N query per 60 detik untuk semua dashboard. Query berikutnya menunggu giliran."""

    def __init__(self, per_minute):
        self.per_minute = per_minute
        self.calls = deque()
        self.lock = threading.Lock()

    def wait(self):
        while True:
            with self.lock:
                now = time.monotonic()
                while self.calls and now - self.calls[0] >= 60:
                    self.calls.popleft()
                if len(self.calls) < self.per_minute:
                    self.calls.append(now)
                    return
                delay = 60 - (now - self.calls[0])
            time.sleep(min(max(delay, 0.05), 5))


class PowerBI:
    def __init__(self):
        missing = [k for k in ("PBI_TENANT_ID", "PBI_CLIENT_ID", "PBI_CLIENT_SECRET") if not getattr(Config, k)]
        if missing:
            raise PowerBIError(f"Belum diisi di .env: {', '.join(missing)}")
        self._http = requests.Session()  # koneksi dipakai ulang supaya tiap query lebih cepat
        self._msal = msal.ConfidentialClientApplication(
            Config.PBI_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{Config.PBI_TENANT_ID}",
            client_credential=Config.PBI_CLIENT_SECRET,
        )
        self._limiter = _RateLimiter(Config.PBI_MAX_QUERIES_PER_MINUTE)

    def token(self):
        # MSAL menyimpan token di cache memori dan otomatis mengambil yang baru kalau kedaluwarsa
        result = self._msal.acquire_token_for_client(scopes=SCOPE)
        if "access_token" not in result:
            raise PowerBIError(f"Gagal ambil token: {result.get('error')}: {result.get('error_description')}")
        return result["access_token"]

    def request(self, method, path, **kwargs):
        resp = self._http.request(method, f"{API}{path}", headers={"Authorization": f"Bearer {self.token()}"},
                                  timeout=300, **kwargs)
        if not resp.ok:
            raise PowerBIError(f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:1000]}", resp.status_code)
        return resp.json() if resp.content else None

    def execute_query(self, dataset, dax):
        """Jalankan DAX, kembalikan list of dict. Batas API: 100.000 baris / 1 juta nilai per query."""
        self._limiter.wait()
        body = {"queries": [{"query": dax}], "serializerSettings": {"includeNulls": True}}
        result = self.request("POST", f"{dataset.path}/executeQueries", json=body)["results"][0]
        if "error" in result:
            raise PowerBIError(f"DAX error: {result['error']}")
        rows = result["tables"][0].get("rows") or []
        if not rows:
            return []
        keys = list(rows[0])
        cleaned = [_clean_column(k) for k in keys]
        # Kalau nama pendek bentrok (kolom sama dari 2 tabel), pakai nama asli
        names = dict(zip(keys, cleaned if len(set(cleaned)) == len(cleaned) else keys))
        return [{names.get(k, k): v for k, v in row.items()} for row in rows]

    def dataset_info(self, dataset):
        return self.request("GET", dataset.path)

    def list_workspaces(self):
        return self.request("GET", "/groups")["value"]


_client = None
_client_lock = threading.Lock()


def client():
    global _client
    with _client_lock:
        if _client is None:
            _client = PowerBI()
        return _client


def query(dataset, dax):
    return client().execute_query(dataset, dax)
