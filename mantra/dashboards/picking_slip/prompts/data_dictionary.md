<!--
================================================================================
 dashboards/picking_slip/prompts/data_dictionary.md : KAMUS DATA AGENT PICKING SLIP
================================================================================
 Diambil dari semantic model "All Site - SCM - Picking Slip" (workspace ALLDATASET) pada 1 November 2026.
 Cek ulang struktur model:
   python scripts/check_setup.py --dashboard picking-slip --dax "EVALUATE INFO.VIEW.COLUMNS()"
================================================================================
-->
# Kamus data

## Sumber

Semantic model Power BI "All Site - SCM - Picking Slip" (mode Import). Halaman dibangun dari measure HTML
dax_picking_slip_summary_v9 (Summary) dan dax_picking_slip_detail_header_v5 (Detail). Warehouse ADV tidak ikut.

| Tabel | Isi |
|---|---|
| sales_order_line | baris picking slip (sales order) per company: PS number (dax_so_suffix), item (stock_code), status, unit, warehouse, department, tanggal, amount (dax_total_ps_amount), qty ordered / shipped / backorder |
| stock_master | status stok item; halaman Detail hanya item stocked (stk_stock_status = S) dengan tipe baris SN |
| stock_warehouse_detail | quantity on hand & on order per company / item / warehouse |
| project_commitment | WO (job_code) & deskripsi project per picking slip |
| DWMasterIconCompany | master company: kode, nama, warna grup |

## Istilah

- PS number: nomor picking slip; satu nomor bisa ada di beberapa company, jadi selalu sebutkan company-nya.
- Status category (contoh): Backorder, Picking Slip printed, Ready for Picking, On Hold, Rdy to Print Invoice,
  Transfer backorder, Credit Hold Entered.
- Territory: diambil dari department (karakter ke-7 dan 8).
- WO: work order (job_code) yang meminta barang; WO status mis. Planned / In Progress.
