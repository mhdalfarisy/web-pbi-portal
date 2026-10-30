<!--
================================================================================
 dashboards/pani_processing/prompts/data_dictionary.md : KAMUS DATA AGENT PANI
================================================================================
 Diambil dari semantic model "PANI - PRCS - Processing" (workspace PANI-MCG) pada 23 Oktober 2026.
 Cek ulang struktur model:
   python scripts/check_setup.py --dashboard pani-processing --dax "EVALUATE INFO.VIEW.COLUMNS()"
================================================================================
-->
# Kamus data

## Sumber

Semantic model Power BI "PANI - PRCS - Processing" (mode Import, refresh terjadwal). Berisi 4 report:

| Halaman | Tabel | Company di data |
|---|---|---|
| Processing | v_bq_pani_se_fact_period (actual/target per metrik per tanggal, period_type DAILY/MTD/YTD), v_bq_pani_se_dim_metric | BSI (PT Bumi Suksesindo) |
| Equipment | mpx_dmr_view (per unit per hari: duration, breakdown, pa_avg, ua_avg, status), mpx_dmr_gainloss_view | MMI (PT Merdeka Mining Indonesia) |
| Mining | mpx_daily_pondok_view (actual & lomp/plan per leaf_key per hari, unit ton/bcm) | MMI |
| Production | mpx_stockpile_summary_view (tonnes_addition = input, tonnes_depletion = output per dump_location) | MMI |

## Metrik Processing (kode → nama, satuan)

- KPI: total_gold_produced_ads → Gold Produced (Ads), Oz; total_silver_produced_ads → Silver Produced (Ads), Oz.
- Stage (urutan proses): total_crushed_ore → Crushing (t); gold_leached → Heap Leach (Oz); feed_flowrate → Adsorption (m³/h);
  gold_poured → Elution - Smelting (Oz).
- Metallurgy (%): gold_adsorption_efficiency, silver_adsorption_efficiency, gold_stripping_efficiency.
- Grade (ppm): gold_grade_crushed, silver_grade_crushed, feed_gold_grade (Gold Grade Feed), feed_silver_grade.
- Crushing lain: opp_crushed_ore, cr72_crushed_ore, mobile_crusher_crushed_ore (t), gold_crushed, silver_crushed (Oz),
  opp_availability, cr72_availability, opp_uoa, cr72_uoa (%).
- Lainnya: silver_leached, silver_poured, silver_stripping_efficiency, metrik Mining & Stacking (t, Oz, ppm).
- "Throughput (Crushed Ore)" = total_crushed_ore. "Availability (OPP)" = opp_availability.

## Rumus Mining (ton)

- Total Ore Mined = hl_ore_rom + hl_ore_stockpile; plan ditambah cil_ore_stockpile.
- Total Waste Mined = waste; plan = waste + mw.
- Total Mined = ore + waste. Total Out-Pit Movement = total_outpit_movement (plan tidak ada di model = 0).
- Total Mining Movement = Total Mined + Out-Pit Movement.

## Rumus Production (ton)

- Total Input = jumlah tonnes_addition; Total Output = jumlah tonnes_depletion; Net Movement = output - input;
  Grand Total = input + output. Tahap alur: lokasi berisi "Crusher" = Crushing, "Screen" = Screening, "Stockpile" = Stockpile.

## Belum bisa dibaca agent

- Kolom plant di halaman Processing (slicer Plant di report) tidak ada di model yang bisa diakses.
- Rumus DAX measure report (html_*) tidak bisa dibaca; angka direkonstruksi dari tabel dan sudah divalidasi.
