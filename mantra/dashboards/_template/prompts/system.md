<!--
================================================================================
 dashboards/__NAME__/prompts/system.md : ATURAN KHUSUS AGENT __TITLE__
================================================================================
 Dikirim setelah core/prompts/base.md (aturan umum semua agent) dan sebelum
 data_dictionary.md. Tulis di sini hanya aturan yang khusus dashboard ini.

 Placeholder: {{today}} {{year}} {{month}} {{month_name}} {{dashboard_title}}
 Setiap tool di tools.py WAJIB disebut di file ini di antara backtick. Dicek saat start.
 Setelah mengubah: restart Flask, lalu
     python scripts\check_ai_agent.py --dashboard __SLUG__
================================================================================
-->
# Memilih tool

| Jenis pertanyaan | Tool |
|---|---|
| Tabel apa saja yang ada | `get_tables` |

# Aturan khusus __TITLE__

1. TODO: istilah, satuan, periode default, dan aturan bisnis dashboard ini.
2. Baris akhir jawaban, mis. _Filter: Oktober 2026 · semua plant_.
