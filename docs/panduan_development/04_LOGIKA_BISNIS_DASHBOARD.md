# Pendalaman 4 — Logika Bisnis Dashboard

> Bagian dari [Panduan Development Berurutan](../PANDUAN_DEVELOPMENT_BERURUTAN.md) (Fase 10 & 12). Bab ini menjelaskan
> **dari mana setiap angka berasal**: tabel, aturan baris, dan rumus. Sumber kebenaran: `queries.py` dan
> `prompts/data_dictionary.md` masing-masing dashboard (dibaca 28 Okt 2026). Kalau angka berbeda dengan report Power BI,
> mulai dari bab ini.

## Daftar isi

1. [Material Readiness](#1-material-readiness)
   - [1.1 Sumber data & arti satu baris](#11-sumber-data--arti-satu-baris)
   - [1.2 Aturan baris yang dihitung](#12-aturan-baris-yang-dihitung)
   - [1.3 Status & legend](#13-status--legend)
   - [1.4 Halaman Summary: "summary cube"](#14-halaman-summary-summary-cube)
   - [1.5 Halaman Detail: filter, KPI, lead time](#15-halaman-detail-filter-kpi-lead-time)
   - [1.6 Tool AI: lookup, breakdown, chart totals](#16-tool-ai-lookup-breakdown-chart-totals)
   - [1.7 Jebakan yang sering membuat angka beda](#17-jebakan-yang-sering-membuat-angka-beda)
2. [PANI](#2-pani)
   - [2.1 Sumber data & aturan umum](#21-sumber-data--aturan-umum)
   - [2.2 Halaman Processing](#22-halaman-processing)
   - [2.3 Halaman Equipment](#23-halaman-equipment)
   - [2.4 Halaman Mining](#24-halaman-mining)
   - [2.5 Halaman Production (stockpile)](#25-halaman-production-stockpile)
   - [2.6 Validasi angka terhadap report](#26-validasi-angka-terhadap-report)
3. [Checklist saat membangun logika dashboard baru](#3-checklist-saat-membangun-logika-dashboard-baru)

---

## 1. Material Readiness

File: [queries.py](../../mantra/dashboards/material_readiness/queries.py),
[tools.py](../../mantra/dashboards/material_readiness/tools.py),
[prompts/data_dictionary.md](../../mantra/dashboards/material_readiness/prompts/data_dictionary.md).

### 1.1 Sumber data & arti satu baris

- Semantic model **"All Site - AMNT - Material Readiness"** (mode Import, refresh terjadwal harian 09:00 WIB). Data di
  portal sesegar refresh terakhir dataset, ditambah cache `CACHE_MINUTES`.
- Tabel utama `'DWMaterialReadiness'` (konstanta `T`), tabel master company `'DWMasterIconCompany'` (konstanta `C`).
- **Satu baris = satu item material (`Stock_Code`) pada satu dokumen PO/SO (`Doc_No`) untuk satu work order
  (`Job_Code`) di satu plant.** Karena itu satu work order bisa muncul di banyak baris.
- `Type`: **PO** = Purchase Order (beli dari vendor), **SO** = Stock Order (ambil dari stok gudang).

### 1.2 Aturan baris yang dihitung

Semua angka dashboard (Summary, Detail, dan semua tool AI kecuali `lookup`) memakai aturan yang sama:

| Aturan | DAX di `queries.py` | Alasan |
|---|---|---|
| Hanya branch **FP** dan **ME** | `BRANCH = TREATAS({"FP", "ME"}, T[branch_code])` | sama dengan report Power BI aslinya; branch SITE, PM, PROJ tidak tampil |
| Status description terisi (bukan kosong / `(Blank)`) | `_filled(T[PO_Status Description], "(Blank)")` | aturan chart Summary |
| Legend terisi | `_filled(T[PO Legend Description], "(Blank)")` | baris tanpa legend (mis. PO status 75 Goods Returned, SO 02 Quotation) tidak punya kelompok |
| Week category terisi | `_filled(T[dax_week_category_year])` | sumbu X chart Summary |
| Periode berdasarkan **Start_Date** | `_period_args()` memakai `T[Start Year Month No]` (YYYYMM) | semua slicer tahun/bulan/This Month |

`_summary_rule(type_)` menghasilkan tiga filter "terisi" itu, dan `_table()` selalu memakainya. Inilah yang menjamin
**angka Detail = angka Summary** untuk filter yang sama.

### 1.3 Status & legend

Setiap baris punya **status detail** (dari sistem sumber) dan **legend** (kelompok yang tampil di dashboard):

| Type | Status (kode → description) | Legend |
|---|---|---|
| PO | 90 Completed, 70 Goods Updated | **FP Ready** |
| PO | 40 On Order | **FP In Progress** |
| PO | 20 Requistion - Approval Required, 11 Backorder | **FP Approval** |
| PO | 10 PO - Approval Required, 33 Return - Ready to Print, 42 In Transit - Shippped, 50 In Transit, 51 In Transit - Invoice Updated | **FP Not Ready** |
| PO | 75 Goods Returned | (kosong: tidak dihitung) |
| SO | 40 Picking Slip printed | **All Ready** |
| SO | 30 Ready for Picking | **All Inprogress** |
| SO | 11 Backorder | **All Not Ready** |
| SO | 20 On Hold | **On Hold** |
| SO | 02 Quotation | (kosong: tidak dihitung) |

Salah ketik "Requistion", "Shippped" berasal dari sistem sumber; ditampilkan apa adanya.

**Urutan & kelompok status** ditentukan oleh **teks**, bukan kode (`status_rank` di Python dan `statusRank` di
`dash-common.js` harus sama):

| Teks legend mengandung | Rank | Kelompok KPI | Warna badge |
|---|---|---|---|
| `approv` | 1 | approval | biru |
| `progress` | 2 | in_progress | kuning |
| `not` | 3 | not_ready | merah |
| `ready` | 4 | ready | hijau |
| lainnya (mis. "On Hold") | 9 | other | abu-abu |

Urutan cek penting: "FP Not Ready" mengandung `ready` **dan** `not`; karena `not` dicek lebih dulu, hasilnya not_ready.

**Readiness (%)** = baris Ready ÷ total baris sesuai filter.

### 1.4 Halaman Summary: "summary cube"

Satu query mengambil **seluruh** data chart, lalu slicer bekerja di browser. DAX intinya (`_CUBE_PART`, satu kali untuk
PO dan satu kali untuk SO, digabung `UNION`):

```dax
DEFINE VAR _base = CALCULATETABLE('DWMaterialReadiness', TREATAS({"FP", "ME"}, 'DWMaterialReadiness'[branch_code]))
EVALUATE UNION(
  SELECTCOLUMNS(
    GROUPBY(
      ADDCOLUMNS(
        FILTER(_base, <status terisi> && <legend terisi> && <week terisi>),
        "@S", <legend>, "@W", [dax_week_category_year],
        "@Y", YEAR([Start_Date]), "@M", MONTH([Start_Date]), "@C", RELATED('DWMasterIconCompany'[Company Name])),
      [@S], [@W], [@Y], [@M], [@C],
      "@Q", COUNTX(CURRENTGROUP(), [QTY_Order]),
      "@J", COUNTX(CURRENTGROUP(), [Job_Code])),
    "t", 0, ...),            -- PO
  SELECTCOLUMNS(..., "t", 1, ...)   -- SO
)
```

Hasilnya list baris `[t, status, week, tahun, bulan, q, j, company]`:

| Index | Isi | Dipakai chart |
|---|---|---|
| 0 | 0 = PO, 1 = SO | memilih chart PO / SO |
| 1 | legend | warna & legenda |
| 2 | week category ("44 - 2026") | sumbu X |
| 3, 4 | tahun & bulan Start_Date (0 kalau kosong) | slicer Year / Month / This Month |
| 5 | `COUNTX(QTY_Order)` | chart **"ALL Material ... Readiness"** |
| 6 | `COUNTX(Job_Code)` | chart **"ALL Work Order ... Readiness"** |
| 7 | company name | slicer Company |

**Perhatikan:** `COUNTX` **menghitung baris yang kolomnya tidak kosong**, bukan menjumlahkan QTY_Order dan bukan
menghitung work order unik. Jadi chart "Material" = jumlah baris item, chart "Work Order" = jumlah baris yang punya
Job_Code. Ini meniru measure report aslinya (`v16`), dan dicatat di kamus data supaya AI tidak menyebutnya "jumlah work order".

**This Month** (default ON): memakai tahun & bulan **sekarang (WIB)** berdasarkan Start_Date, bukan tanggal refresh.

### 1.5 Halaman Detail: filter, KPI, lead time

`/d/material-readiness/api/detail?type=PO&tm=0&year=2026&month=10&company=...` → `queries.detail(f)`.

`parse_filters` menormalkan semua parameter URL: `type` hanya PO/SO, `tm` (This Month) default ON, `sort` hanya kolom
yang ada di tampilan, `size` hanya 25/50/100/200. Input yang tidak valid diganti default, **tidak pernah** masuk DAX
mentah. Teks bebas (`q`) di-escape untuk `CONTAINSSTRING` (`~`, `*`, `?`) lalu `dax_str`.

Dua query berjalan **paralel** (`ThreadPoolExecutor`):

| Query | Isi | Catatan |
|---|---|---|
| `_detail_rows` | maks `DETAIL_LIMIT` = 15.000 baris, terurut | tabel & export; `total` = baris yang dimuat |
| `_meta` | satu `UNION` berisi KPI per legend, lead time, jumlah per tab PO/SO, dan opsi setiap filter | `matched` = semua baris cocok (bisa > 15.000) |

- **Opsi filter "facet"**: daftar plant dihitung dengan semua filter **kecuali** filter plant itu sendiri
  (`_table(f, skip=("plant",))`), supaya pilihan lain tetap terlihat.
- **Lead time (hari)** = rata-rata `Schedule_Date − Start_Date`, hanya baris yang kedua tanggalnya ≥ 1901 (tanggal
  pengganti `1899-12-31` dari sistem sumber dibuang).
- **Tab PO/SO** dihitung tanpa filter status & doc (`skip=("status", "doc")`), karena nilai status berbeda antar tipe.
- **Company "Unidentified"** = kode company yang tidak ada di `DWMasterIconCompany`.
- Export TSV = baris yang dimuat (maks 15.000), tanggal format `dd/mm/yyyy`, langsung bisa di-paste ke Excel.

### 1.6 Tool AI: lookup, breakdown, chart totals

| Tool | Sumber angka | Aturan khusus |
|---|---|---|
| `get_chart_totals` | `summary_cube()` (sama dengan chart) | `measure=material` (index 5) / `work_order` (index 6); bulan kosong → ikut filter dashboard, hasil diberi `note`; kalau `week` diisi, laporkan juga bagian week itu yang Start_Date-nya di bulan lain (`same_week_other_months`) |
| `get_readiness_kpi` | `_meta` (sama dengan KPI Detail) | bisa difilter plant/warehouse/teks |
| `get_breakdown` | `GROUPBY` + `TOPN` di atas `_table` | jumlah baris per kelompok + pecahan ready/not_ready/in_progress/approval + total QTY (di sini QTY **dijumlahkan**) |
| `get_rows` | `detail_rows` | maks 30 baris contoh |
| `lookup` | 3 query paralel **tanpa filter branch** | satu Job Code / Doc No / Stock Code di semua branch, plus `dashboard_notes` yang menjelaskan kenapa baris itu tampil atau tidak di dashboard (mis. branch SITE, week kosong) |

### 1.7 Jebakan yang sering membuat angka beda

| Gejala | Penyebab | Cek |
|---|---|---|
| Total portal < total report | report difilter branch lain, atau baris tanpa week/legend ikut dihitung di report | samakan filter branch & aturan §1.2 |
| Satu week "hilang" sebagian | week melintasi dua bulan Start_Date, filter bulan memotongnya | `get_chart_totals` dengan `week` → lihat `same_week_other_months` |
| "Work order" tidak sama dengan jumlah WO unik | chart menghitung **baris** (COUNTX), bukan DISTINCTCOUNT | §1.4 |
| Angka berubah setelah 10 menit | cache kedaluwarsa dan dataset sudah refresh | `CACHE_MINUTES`, kotak Last Update |
| Status "On Hold" tidak masuk Ready/Not Ready | rank 9 → kelompok `other` | §1.3 |
| Job Code ada di sistem tapi tidak muncul | branch bukan FP/ME | tanya AI dengan `lookup` |

---

## 2. PANI

Judul di portal (`title` di manifest): **PROCESSING, EQUIPMENT, MINING & STOCKPILE PRODUCTION**, slug `pani-processing`.

File: [queries.py](../../mantra/dashboards/pani_processing/queries.py),
[routes.py](../../mantra/dashboards/pani_processing/routes.py),
[tools.py](../../mantra/dashboards/pani_processing/tools.py),
[prompts/data_dictionary.md](../../mantra/dashboards/pani_processing/prompts/data_dictionary.md).

### 2.1 Sumber data & aturan umum

Semantic model **"PANI - PRCS - Processing"** (workspace PANI-MCG) berisi 4 report yang di portal menjadi 4 halaman:

| Halaman | Tabel | Company di header | Rentang default (tanpa `?start=&end=`) |
|---|---|---|---|
| Processing | `v_bq_pani_se_fact_period` + `v_bq_pani_se_dim_metric` | BSI | seluruh rentang data → mode **YTD** |
| Equipment | `mpx_dmr_view` + `mpx_dmr_gainloss_view` | MMI | tanggal data terakhir saja |
| Mining | `mpx_daily_pondok_view` | MMI | awal bulan s/d tanggal actual terakhir |
| Production | `mpx_stockpile_summary_view` | MMI | awal bulan s/d tanggal data terakhir |

Aturan yang berlaku di semua halaman:
- **Rumus measure report tidak bisa dibaca** service principal; semua angka **direkonstruksi** dari tabel, lalu
  dibandingkan dengan teks measure HTML report (§2.6).
- Filter tanggal dibaca dari URL, sehingga link bisa dibagikan. `date_range()` menukar start/end kalau terbalik dan
  **membatasi** ke tanggal data pertama/terakhir (tanggal ekstrem seperti `0001-01-01` tidak membuat error 500, dan
  tidak membuat query baru untuk setiap rentang yang diketik).
- Tabel kosong (`MIN/MAX` = BLANK) → halaman "no data" (`dashboard/empty.html`), bukan error.
- `fmt_num` membulatkan **setengah ke atas** seperti `FORMAT` di DAX (88.125 → 88.13), bukan *banker's rounding*
  Python (`round(88.125, 2)` = 88.12). Ini salah satu sumber selisih angka kalau diabaikan.
- **Achievement (%)** = actual ÷ target × 100. **Variance (%)** = (actual − plan) ÷ plan × 100.

### 2.2 Halaman Processing

Tabel fakta `v_bq_pani_se_fact_period`: satu baris = satu metrik (`code`) pada satu tanggal (`date_key`) untuk satu
`period_type` (`DAILY`, `MTD`, `YTD`), berisi `actual_value`, `target_value`, `variance_pct`, `is_provisional`.
Definisi metrik (label, satuan, desimal, grup, apakah kandidat driver) dari `v_bq_pani_se_dim_metric`.

**Dua mode**, ditentukan rentang tanggal:

| Mode | Kapan | Angka utama | Top 5 drivers | Sparkline |
|---|---|---|---|---|
| **YTD** | rentang mencakup tanggal data pertama s/d terakhir (default) | baris `YTD` pada tanggal akhir | dari baris YTD | nilai **kumulatif** |
| **Selected Period** | rentang lain | agregasi baris `DAILY` dalam rentang | dari baris DAILY tanggal akhir | nilai harian |

Agregasi Selected Period (`_selected_rows`): metrik bersatuan **Oz** dan **t** di-**SUM**; metrik rasio (%, ppm, m³/h)
di-**AVERAGE**. Menjumlahkan persen akan menghasilkan angka tak bermakna.

Isi halaman:
- **Gold / Silver Produced (Ads)** (`total_gold_produced_ads`, `total_silver_produced_ads`, Oz) + achievement.
- **Overall** = (gold + silver actual) ÷ (gold + silver target).
- **Stage** (urut `stage_order`): Crushing (`total_crushed_ore`, t) → Heap Leach (`gold_leached`, Oz) → Adsorption
  (`feed_flowrate`, m³/h) → Elution - Smelting (`gold_poured`, Oz).
- **Metallurgy** (%) dan **Grade** (ppm, urutan tetap `GRADE_ORDER`).
- **Snapshot** Daily / MTD / YTD pada tanggal akhir untuk gold & silver.
- **Top 5 Negative Variance Drivers**: metrik dengan `is_driver_candidate`, `variance < 0`, diurutkan dari variance
  paling negatif; kalau sama, urutan prioritas dict `DRIVERS` (meniru perilaku measure). Label & keterangan
  (mis. "Lower throughput against target capacity.") persis dari measure report.
- Chart "Actual vs Forecast Production (Ton Dry)" = `total_crushed_ore` harian.
- Tanda **provisional** kalau ada baris `is_provisional` pada tanggal akhir.

### 2.3 Halaman Equipment

Tabel `mpx_dmr_view`: satu baris = satu **unit** pada satu **hari** (`machine_date`), berisi `duration_sum`,
`bd_duration_sum` (breakdown), `pa_avg` (Physical Availability %), `ua_avg` (Use of Availability %), `status`.

| Angka | Rumus |
|---|---|
| Total / Active / Inactive Unit | jumlah **baris unit-hari** dalam rentang (bukan unit unik), persen terhadap semua baris |
| Average PA% / UA% | rata-rata semua unit pada **hari terakhir** rentang (unit nonaktif bernilai 0) |
| "vs yesterday" | selisih dengan hari sebelum hari terakhir (kosong kalau tidak ada data) |
| PA/UA per model | AVERAGE semua baris unit-hari model itu |
| Kartu model hijau (`ok`) | **semua** unit model itu PA ≥ 85% **dan** UA ≥ 70% (`PA_TARGET`, `UA_TARGET`) |
| Urutan kartu model | model yang punya unit aktif dulu, lalu kode unit terkecil |
| Top 5 Duration Breakdown | 5 unit dengan durasi terbesar (filter `?status=active/inactive`), tie-break kode unit; ditampilkan dari kecil ke besar |
| Gain/Loss | `mpx_dmr_gainloss_view`: SUM `duration` per kode, net = jumlah semuanya |

### 2.4 Halaman Mining

Tabel `mpx_daily_pondok_view`: actual & plan (`lomp`) per `leaf_key` per hari, hanya `unit = "ton"`.

| Baris tabel | Actual | Plan |
|---|---|---|
| Total Ore Mined | `hl_ore_rom` + `hl_ore_stockpile` | + `cil_ore_stockpile` |
| Total Waste Mined | `waste` | `waste` + `mw` |
| Total Mined | Ore + Waste | Ore + Waste |
| Total Out-Pit Movement | `total_outpit_movement` | 0 (tidak ada di model) |
| Total Mining Movement | Total Mined + Out-Pit | Total Mined + Out-Pit |

- Setiap baris dihitung untuk tiga periode: rentang filter ("daily"), **MTD** (awal bulan tanggal akhir s/d tanggal
  akhir), **YTD** (1 Januari s/d tanggal akhir).
- Kartu "(MTD)", Key Highlights, dan donut memakai **rentang filter**; chart Total Mined / Movement memakai awal bulan
  s/d tanggal akhir (harian + kumulatif). Perbedaan ini meniru report.
- **Weather Loss** = SUM durasi gain/loss bernama Hujan, Jalan Licin, Kabut, Petir, Debu dalam bulan berjalan.
  Daftar ini **asumsi** (dicatat di kode), bukan dari model.
- Warna ring achievement: ≥ 90% hijau, ≥ 70% oranye, di bawahnya merah (`ring_mtd`).

### 2.5 Halaman Production (stockpile)

Tabel `mpx_stockpile_summary_view`: `tonnes_addition` (input) dan `tonnes_depletion` (output) per `dump_location` per
`ritase_date`. Satuan di tabel **BCM**.

| Angka | Rumus |
|---|---|
| Total Input / Output | SUM `tonnes_addition` / SUM `tonnes_depletion` |
| Net Movement | output − input |
| Grand Total | input + output |
| Konversi ke ton | input × **2,19**, output × **1,93** (faktor tetap dari report: `BCM_TO_TON_INPUT/OUTPUT`) |
| Output % / Net % | output ÷ input × 100 / (output − input) ÷ input × 100 |
| Tahap alur | nama lokasi mengandung "crusher"/"crushing" → Crushing, "screen" → Screening, "stockpile" → Stockpile |
| Top Input / Output Detail | 4 lokasi teratas (`TOP_LOCATIONS`) |
| Tren | per hari, per minggu ISO (`W44 2026`), per bulan |
| Kartu Rekomendasi | 2 lokasi stockpile dengan input terbesar |
| Insight PA% | dari halaman Equipment pada hari terakhir rentang (boleh kosong kalau data equipment belum ada) |

### 2.6 Validasi angka terhadap report

```bash
python scripts/compare_pani_with_powerbi.py               # semua halaman, 14 skenario filter
python scripts/compare_pani_with_powerbi.py processing    # satu halaman
python scripts/compare_pani_with_powerbi.py --fixed       # uji DAX perbaikan (pulihkan docs/powerbi_fixes dari git dulu)
```
Script menjalankan measure HTML report (mis. `html_gold_produced_ads_ytd`) lewat `executeQueries` dengan filter tanggal
yang sama, membaca teksnya, lalu membandingkan dengan angka portal **dalam format tampilan yang sama**. Hasil tercatat
di README: 272 sama, 76 beda karena bug di report (ditandai `BEDA*`); dengan `--fixed` (19 measure diperbaiki) 348/348
sama. Output ini **tidak** direkam ulang untuk panduan karena memanggil Power BI sungguhan.

---

## 3. Checklist saat membangun logika dashboard baru

Urutan yang dipakai kedua dashboard di atas, dan sebaiknya diulang untuk dashboard berikutnya:

1. **Kenali model:** `python scripts/check_setup.py --dashboard <slug> --dax "EVALUATE INFO.VIEW.COLUMNS()"`. Catat
   tabel, kolom, dan arti **satu baris** (§1.1).
2. **Tulis aturan baris** yang dihitung report (branch, status terisi, dsb.) sebagai **satu** fungsi yang dipakai semua
   query (seperti `_table` + `_summary_rule`). Kalau aturannya tersebar, angka antar halaman akan beda.
3. **Tulis rumus setiap angka** di kamus data (`prompts/data_dictionary.md`) **sebelum** koding, termasuk SUM vs AVERAGE
   vs COUNT, dan satuan.
4. **Samakan pembulatan & format** dengan report (`fmt_num` half-up).
5. **Batasi input URL** (`parse_filters`, `date_range`) sebelum masuk DAX; nilai teks lewat `dax_str`.
6. **Bandingkan dengan report** untuk beberapa kombinasi filter; catat selisih yang memang bug report.
7. **Buat tool AI di atas fungsi query yang sama** dengan halaman, lalu pertanyaan acuan yang jawabannya dihitung dari
   tool (`chat_cases.py`).
