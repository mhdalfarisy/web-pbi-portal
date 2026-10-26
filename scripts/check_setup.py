"""Cek setup MANTRA: .env, login Microsoft Entra, service principal Power BI, akses tiap semantic model, AI agent.

Pemakaian:
    python scripts/check_setup.py
    python scripts/check_setup.py --dashboard material-readiness --dax "EVALUATE TOPN(5, 'DWMaterialReadiness')"

Tidak mengubah apa pun. Secret tidak pernah dicetak.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import msal  # noqa: E402
import requests  # noqa: E402

from mantra.config import Config  # noqa: E402
from mantra.core import powerbi, registry  # noqa: E402

failed = 0


def report(ok, label, detail="", hints=()):
    global failed
    failed += ok is False
    mark = {True: "OK   ", False: "GAGAL", None: "LEWAT"}[ok]
    print(f"  {mark} {label}{'  -> ' + detail if detail else ''}")
    if ok is False:
        for hint in hints:
            print(f"        - {hint}")


def check_env():
    print("\n[1] File .env")
    report(bool(Config.SECRET_KEY), "FLASK_SECRET_KEY terisi")
    report(None if Config.AUTH_DISABLED else True, "AUTH_DISABLED",
           "1 (login dilewati, hanya untuk development)" if Config.AUTH_DISABLED else "0 (login email + password aktif)")
    for key in ("ENTRA_TENANT_ID", "ENTRA_CLIENT_ID", "ENTRA_CLIENT_SECRET", "PBI_CLIENT_ID", "PBI_CLIENT_SECRET"):
        # Entra opsional (login utama email + password); kalau kosong cukup dilewati
        report(bool(getattr(Config, key)) or (None if key.startswith("ENTRA") else False), f"{key} terisi")


def check_entra():
    print("\n[2] Login Microsoft Entra, opsional (app registration MANTRA Portal)")
    if not (Config.ENTRA_TENANT_ID and Config.ENTRA_CLIENT_ID and Config.ENTRA_CLIENT_SECRET):
        report(None, "dilewati, ENTRA_* belum lengkap")
        return
    url = f"https://login.microsoftonline.com/{Config.ENTRA_TENANT_ID}/v2.0/.well-known/openid-configuration"
    resp = requests.get(url, timeout=20)
    report(resp.ok, "tenant ID dikenali Microsoft", "" if resp.ok else f"HTTP {resp.status_code}",
           ["Cek ENTRA_TENANT_ID (Directory (tenant) ID di halaman Overview app registration)."])
    if not resp.ok:
        return
    # Client credentials hanya untuk memastikan client ID + secret cocok; tokennya tidak dipakai
    app = msal.ConfidentialClientApplication(Config.ENTRA_CLIENT_ID, client_credential=Config.ENTRA_CLIENT_SECRET,
                                             authority=f"https://login.microsoftonline.com/{Config.ENTRA_TENANT_ID}")
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    ok = "access_token" in result
    report(ok, "client ID + client secret cocok", "" if ok else (result.get("error_description") or "").splitlines()[0],
           ["AADSTS7000215: yang disalin 'Secret ID', bukan 'Value'.",
            "AADSTS700016: ENTRA_CLIENT_ID salah atau app ada di tenant lain.",
            "AADSTS7000222: client secret kedaluwarsa, buat yang baru."])
    print(f"        Catatan: redirect URI http://localhost:{Config.PORT}/auth/callback dan assignment user")
    print(f"        hanya bisa dicek dengan login langsung di http://localhost:{Config.PORT}")


def check_powerbi(dashboards):
    print("\n[3] Power BI (service principal mantra-powerbi)")
    try:
        client = powerbi.client()
        client.token()
        report(True, "token Microsoft Entra")
    except powerbi.PowerBIError as exc:
        report(False, "token Microsoft Entra", str(exc)[:200],
               ["Cek PBI_CLIENT_ID / PBI_CLIENT_SECRET (kolom Value) / tenant ID."])
        return
    try:
        workspaces = {w["id"].lower(): w["name"] for w in client.list_workspaces()}
        report(True, f"daftar workspace yang bisa diakses ({len(workspaces)})")
    except powerbi.PowerBIError as exc:
        report(False, "daftar workspace", str(exc)[:200],
               ["HTTP 401/403: mantra-powerbi belum masuk grup sg-powerbi-api, atau tenant setting",
                "'Service principals can use Fabric APIs' belum mengizinkan grup itu. Tunggu ~15 menit setelah diubah."])
        return

    for d in dashboards:
        if d.dataset is None:
            continue
        workspace_id, _ = d.dataset.ids
        print(f"\n    {d.title} ({d.slug})")
        in_ws = workspace_id.lower() in workspaces
        report(in_ws, "akses workspace", workspaces.get(workspace_id.lower(), workspace_id),
               ["Power BI > workspace > Manage access > tambahkan mantra-powerbi sebagai Contributor/Member."])
        if not in_ws:
            continue
        try:
            info = client.dataset_info(d.dataset)
            storage = {"Abf": "Import", "PremiumFiles": "Import (large)"}.get(info.get("targetStorageMode"),
                                                                            info.get("targetStorageMode"))
            report(True, "semantic model", f"{info.get('name')} · {storage}")
            rls = info.get("isEffectiveIdentityRolesRequired")
            report(not rls, "tanpa RLS", "dataset memakai RLS" if rls else "",
                   ["executeQueries lewat service principal tidak didukung untuk dataset dengan RLS."])
            client.execute_query(d.dataset, 'EVALUATE ROW("ok", 1)')
            report(True, "executeQueries (DAX)")
        except powerbi.PowerBIError as exc:
            report(False, "semantic model / executeQueries", str(exc)[:200],
                   ["HTTP 404: dataset ID salah atau bukan di workspace ini.",
                    "HTTP 401/403: tenant setting 'Dataset Execute Queries REST API' belum aktif."])


def check_ai():
    print(f"\n[4] AI agent ({Config.AI_PROVIDER})")
    if Config.AI_PROVIDER != "gemini":
        report(None, f"provider {Config.AI_PROVIDER} belum punya cek otomatis")
        return
    if not Config.GEMINI_API_KEY:
        report(None, "GEMINI_API_KEY kosong: tombol Tanya AI disembunyikan")
        return
    from google import genai
    try:
        client = genai.Client(api_key=Config.GEMINI_API_KEY)  # simpan di variabel: client yang dibuang menutup koneksi
        next(iter(client.models.list(config={"page_size": 1})))
        report(True, "API key valid")
    except Exception as exc:  # noqa: BLE001
        report(False, "API key", str(exc)[:200], ["Buat ulang di https://aistudio.google.com/apikey"])


def run_dax(dashboards, slug, dax):
    dashboard = next((d for d in dashboards if d.slug == slug), None)
    if dashboard is None or dashboard.dataset is None:
        sys.exit(f"Dashboard '{slug}' tidak ada atau tidak punya dataset. Pilihan: "
                 f"{', '.join(d.slug for d in dashboards if d.dataset)}")
    rows = powerbi.query(dashboard.dataset, dax)
    print(f"{len(rows)} baris")
    if rows:
        cols = list(rows[0])
        widths = {c: min(40, max(len(str(c)), *(len(str(r[c])) for r in rows[:50]))) for c in cols}
        print("  ".join(str(c)[:40].ljust(widths[c]) for c in cols))
        for r in rows[:50]:
            print("  ".join(str(r[c])[:40].ljust(widths[c]) for c in cols))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dashboard", help="slug dashboard untuk --dax")
    parser.add_argument("--dax", help="jalankan query DAX ke semantic model dashboard ini")
    args = parser.parse_args()

    dashboards = registry.manifests()
    if args.dax:
        run_dax(dashboards, args.dashboard, args.dax)
        return

    check_env()
    check_entra()
    check_powerbi(dashboards)
    check_ai()
    print(f"\n{'SEMUA CEK LULUS' if not failed else f'{failed} cek GAGAL'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
