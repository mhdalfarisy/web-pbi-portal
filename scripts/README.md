# scripts/

Perintah manual untuk developer & admin. **Bukan bagian dari website**: tidak ikut jalan saat `python run.py`, hanya
saat dipanggil sendiri dari folder project (aktifkan `.venv` dulu):

```powershell
python scripts\<nama>.py ...
```

| Script | Gunanya | Kapan dipakai | Butuh layanan luar? |
|---|---|---|---|
| `manage_users.py` | Kelola akun dari server: akun awal (`seed`), buat user, hak akses, reset password, role, backup database | Setup pertama; darurat (mis. lupa password Super Admin terakhir); memberi role Super Admin (tidak bisa lewat web) | Tidak |
| `check_setup.py` | Cek `.env`, login Microsoft Entra, akses Power BI ke tiap semantic model, API AI. Bisa menjalankan DAX (`--dashboard ... --dax ...`) | Setelah setup / pindah laptop; dashboard menampilkan "Could not load data" | Ya (Entra, Power BI, Gemini). Tidak mengubah apa pun |
| `check_ai_agent.py` | Tes AI agent: `--static` cek prompt & tools (gratis); `--dashboard <slug>` + pertanyaan acuan | Setelah mengubah prompt atau `tools.py` | `--static`: tidak. `--dashboard`: Gemini + Power BI (pakai kuota) |
| `create_dashboard.py` | Buat folder dashboard baru dari `mantra/dashboards/_template` | Menambah report baru ke portal | Tidak |
| `compare_pani_with_powerbi.py` | Bandingkan angka dashboard PANI di MANTRA dengan measure report Power BI asli (14 skenario filter) | Memastikan angka MANTRA sama dengan report | Ya (Power BI) |

Contoh:

```powershell
python scripts\manage_users.py seed
python scripts\check_setup.py
python scripts\check_ai_agent.py --static
python scripts\create_dashboard.py work-order "Work Order"
python scripts\compare_pani_with_powerbi.py processing
```

Detail pemakaian ada di docstring bagian atas setiap file.
