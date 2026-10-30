<!--
================================================================================
 dashboards/material_readiness/prompts/data_dictionary.md : KAMUS DATA AGENT MATERIAL READINESS
================================================================================
 Definisi tabel, kolom, dan status di semantic model. Dikirim setelah base.md dan
 system.md di setiap pertanyaan. Aturan placeholder & cara mengubah
 sama dengan system.md.

 Kapan diperbarui:
 - Ada kolom baru di semantic model, atau kolom baru yang bisa dibaca tool di tools.py.
 - Ada status baru (PO_Status / SO_Status) atau perubahan pemetaan ke legend.
   Cek pemetaan terbaru dengan: python scripts/check_setup.py --dashboard material-readiness --dax "<query>", mis.:
   EVALUATE SUMMARIZECOLUMNS('DWMaterialReadiness'[PO_Status], 'DWMaterialReadiness'[PO_Status Description],
       'DWMaterialReadiness'[PO Legend Description], "rows", COUNTROWS('DWMaterialReadiness'))
 - Kolom "Dibaca chatbot" HARUS sesuai dengan tool di tools.py. Kalau tool belum bisa
   membaca kolom itu, tulis "belum" supaya chatbot tidak mengarang jawaban.

 Pemetaan status di bawah diambil dari data branch FP & ME pada 23 Oktober 2026.
================================================================================
-->
# Kamus data

## Sumber dan cakupan

- Semantic model Power BI "All Site - AMNT - Material Readiness". Tabel utama: DWMaterialReadiness.
- Satu baris = satu item material (Stock_Code) pada satu dokumen PO/SO untuk satu work order (Job_Code) di satu plant.
- Dashboard dan semua tool kecuali `lookup` hanya membaca branch {{branches}}, dan hanya baris yang status
  description, legend, dan week category-nya terisi (aturan chart Summary). `lookup` membaca semua branch.
- Semua filter periode (year, month, This Month) memakai Start_Date.

## Tabel DWMaterialReadiness

| Kolom | Arti | Contoh | Dibaca chatbot |
|---|---|---|---|
| Type | Jenis dokumen: PO = Purchase Order (beli dari vendor), SO = Stock Order (ambil dari stok gudang) | PO | semua tool |
| branch_code | Kode branch. FP & ME tampil di dashboard. SITE, PM, PROJ hanya lewat `lookup` | SITE | `lookup` |
| Company | Kode company, dipetakan ke nama lewat DWMasterIconCompany | B02 | semua tool (sebagai nama) |
| Job_Code | Nomor work order (WO) | W0417321 | `lookup`, `get_rows`, `get_breakdown`, search |
| Job_Code_Desc | Deskripsi pekerjaan work order | ORDER TOOL FSS | `lookup`, `get_rows`, `get_breakdown` |
| Plant_No / Plant_Desc | Kode dan nama plant (unit, equipment, atau area kerja) | EX2005 / EXCAVATOR KOMATSU PC2000-11 | `lookup`, `get_rows`, `get_breakdown`, filter plant |
| Warehouse | Kode gudang | WSPC | `get_rows`, `get_breakdown`, filter |
| Doc_No | Nomor dokumen PO/SO | 193221 | `lookup`, `get_rows`, `get_breakdown`, filter doc |
| Doc_Suffix | Suffix dokumen | | belum |
| Stock_Code | Kode material | 5130-03-335862 | `lookup`, `get_rows`, `get_breakdown`, search |
| QTY_Order | Jumlah yang dipesan. Chart "Material" menghitung JUMLAH BARIS, bukan menjumlahkan QTY_Order. Total QTY ada di `get_breakdown` (qty_order) | 1 | `get_rows`, `get_breakdown` |
| Start_Date | Tanggal mulai work order, dasar semua filter periode | 20/12/2023 | `get_rows`, `lookup` (per bulan) |
| Schedule_Date | Tanggal jadwal. Lead time = Schedule_Date − Start_Date (hari) | 20/12/2023 | `get_rows`, `get_readiness_kpi` |
| Received_Date | Tanggal barang diterima (PO) | 09/09/2023 | `get_rows` (PO) |
| PO_Status | Kode status PO (lihat tabel status PO) | 90 | belum (pakai description) |
| PO_Status Description | Status detail PO | Completed | `lookup` |
| PO Legend Description | Kelompok status PO di dashboard | FP Ready | semua tool |
| SO_Status | Kode status SO | 40 | belum (pakai description) |
| Status SO Description | Status detail SO | Picking Slip printed | `lookup`, `get_rows` (SO) |
| SO Legend Description | Kelompok status SO di dashboard | All Ready | semua tool |
| dax_week_category_year | Week category, format "minggu - tahun". Sumbu X chart Summary | 44 - 2026 | `get_chart_totals`, `get_breakdown`, filter |
| Start Year Month No | Tahun-bulan Start_Date (YYYYMM) | 202610 | `lookup`, `get_breakdown` (month) |
| Section, Responsible_Code, Work_Group, Finished_Date | Ada di semantic model | | belum |

## Tabel DWMasterIconCompany

- Company Code → Company Name, mis. MMI = PT Merdeka Mining Indonesia, B02 = PT Bumi Suksesindo,
  BTR = PT Batutua Tembaga Raya, MTU = PT Merdeka Tsingshan Indonesia.
- Daftar company saat ini: {{companies}}.
- Baris yang kode company-nya tidak ada di tabel ini disebut "Unidentified".

## Status PO

| PO_Status | PO_Status Description | PO Legend Description |
|---|---|---|
| 90 | Completed | FP Ready |
| 70 | Goods Updated | FP Ready |
| 40 | On Order | FP In Progress |
| 20 | Requistion - Approval Required | FP Approval |
| 11 | Backorder | FP Approval |
| 10 | PO - Approval Required | FP Not Ready |
| 33 | Return - Ready to Print | FP Not Ready |
| 42 | In Transit - Shippped | FP Not Ready |
| 50 | In Transit | FP Not Ready |
| 51 | In Transit - Invoice Updated | FP Not Ready |
| 75 | Goods Returned | (kosong, tidak tampil di dashboard) |

## Status SO

| SO_Status | Status SO Description | SO Legend Description |
|---|---|---|
| 40 | Picking Slip printed | All Ready |
| 30 | Ready for Picking | All Inprogress |
| 11 | Backorder | All Not Ready |
| 20 | On Hold | On Hold |
| 02 | Quotation | (kosong, tidak tampil di dashboard) |

## Istilah

- WO / work order = Job_Code. Material = item Stock_Code.
- Ready = legend FP Ready / All Ready. Not Ready = FP Not Ready / All Not Ready.
  In Progress = FP In Progress / All Inprogress. Approval = FP Approval (hanya PO).
- Readiness (%) = jumlah baris Ready dibagi total baris, sesuai filter.
- This Month = bulan berjalan berdasarkan Start_Date.
- Start_Date yang sangat jauh di masa lalu atau masa depan (mis. 1899-12-31, 2030-12-30) bisa jadi tanggal
  pengganti dari sistem sumber. Sebutkan apa adanya, jangan ditafsirkan.
