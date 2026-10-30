# 19 — Workflow D: Perubahan Backend atau Data Contract

### A. Objective
Mengubah route, query, database, integrasi Power BI, atau logika bisnis tanpa merusak pemakai yang sudah ada.

### B. When to use
Angka salah, field baru di payload/API, query baru, aturan bisnis baru, tabel database baru.

### C. Prerequisites
Baseline test; akses Power BI untuk validasi angka; backup DB jika menyentuh skema.

### D. Architecture context
Kontrak antar modul di [09](09_BACKEND_ARCHITECTURE.md) §2; kontrak HTTP di [10](10_FRONTEND_BACKEND_CONTRACT.md).
Satu fungsi `queries.py` biasanya dipakai **tiga** pemakai: halaman, tools AI, dan `chat_cases.py` (plus
`compare_pani_with_powerbi.py` untuk PANI).

### E. Files involved
Tergantung perubahan; selalu cari pemakai dulu (langkah 3).

### F. Step-by-step instructions
1. **Temukan handler & dependency.** URL → endpoint: lihat dok 10 atau
   `python -c "import sys; sys.path.insert(0,'.'); from mantra import create_app; [print(r.rule, r.endpoint) for r in create_app().url_map.iter_rules()]"`
   (memakai `.env` & `instance/mantra.db` asli dan melakukan hal yang sama dengan start server biasa: migrasi bila
   perlu + menyamakan katalog dashboard; tidak memanggil Power BI/AI). Endpoint `blueprint.fungsi` → file `routes.py`.
2. **Tetapkan kontrak sebelum mengubah**: tulis input (parameter, tipe), output (key JSON/payload), error.
3. **Cari semua pemakai kontrak**:
   ```bash
   grep -rnE "nama_fungsi|nama_key" mantra scripts tests --include='*.py' --include='*.js' --include='*.html'
   ```
4. **Compatibility**: menambah key/parameter opsional = kompatibel. Mengganti nama/menghapus = breaking → ubah semua
   pemakai dalam satu perubahan. URL publik jangan diganti.
5. **Implementasi**: DAX hanya di `queries.py`; nilai user lewat `dax_str` / konversi tipe; cache key memuat semua
   filter; error Power BI dibiarkan naik sebagai `DATA_ERRORS` (ditangani routes).
6. **Tests**: tambah/ubah test (stub `_query` / `PowerBI.request` seperti `test_errors_and_security.py`).
7. **Logging & security**: jangan log secret; detail error lewat `log_data_error`; route baru di blueprint dashboard
   otomatis dijaga `_guard`, route di blueprint lain butuh decorator.
8. **Integration & regression**: `python -m pytest`, `python scripts/check_ai_agent.py --static`; dengan akses Power
   BI: buka halaman, bandingkan dengan report; PANI: `python scripts/compare_pani_with_powerbi.py <halaman>`.
9. **Dokumentasi**: dok 10, data dictionary, README bila perilaku berubah.

### G. Code or patch — contoh perubahan lintas dashboard
Kasus: format "Last Update" diubah di `core/common.stamp_info`. Pemakai (Verified): `core/errors.py`,
`material_readiness/queries.py` + `routes.py`, `pani_processing/routes.py`, `_template/routes.py`, dan template
`dashboard/base.html` (`header.date`, `header.time`), serta JS yang membaca `fetched` (`detail.js`).

Langkah: (1) pertahankan key `date` & `time` (kompatibel) dan tambah key baru bila perlu; (2) jalankan seluruh test;
(3) buka satu halaman setiap dashboard + halaman error (`dashboard/error.html` juga memakai `header`).

### H. Code explanation
Fungsi `core/` dipakai banyak dashboard; mengubah output tanpa mempertahankan key lama merusak semua dashboard sekaligus.

### I. Commands
```bash
python -m pytest
python scripts/check_ai_agent.py --static
python scripts/check_setup.py --dashboard material-readiness --dax "EVALUATE TOPN(5, 'DWMaterialReadiness')"
```

### J. Expected result
Test lulus; angka sama dengan report; tidak ada pemakai kontrak yang rusak.

### K. Validation
Halaman + API terkait + jawaban AI untuk pertanyaan yang memakai fungsi itu (`check_ai_agent.py --dashboard <slug>`,
memakai kuota).

### L. Troubleshooting
Angka salah → telusuri: template (format) → payload (`Cmd+Option+U` / response API) → fungsi `queries.py` → DAX
(`check_setup.py --dax`) → report Power BI (filter yang sama?). Lihat dok 23.

### M. Regression impact
`core/*` → semua dashboard; `queries.py` → halaman + AI + chat_cases; `accounts.py`/`db.py` → login & akses.

### N. Acceptance criteria
Kontrak terdokumentasi, pemakai diperbarui, test baru lulus, validasi angka dilakukan (atau dicatat NOT RUN).

### O. Documentation updates
Dok 09, 10, 15, data dictionary.

### P. Actual status
Prosedur: NOT RUN (tidak ada perubahan backend di sesi dokumentasi ini).
