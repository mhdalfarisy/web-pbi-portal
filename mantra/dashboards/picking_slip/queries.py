"""Query dashboard Picking Slip ke semantic model "All Site - SCM - Picking Slip" (workspace ALLDATASET).

Dua halaman diambil dari measure HTML report di model itu:
  Summary : dax_picking_slip_summary_v9
  Detail  : dax_picking_slip_detail_header_v5
Measure membuat setiap kumpulan data dengan CONCATENATEX ( <tabel>, <teks satu baris>, SEP_R ) lalu menempelkannya ke
JavaScript. Di sini <tabel> dan <teks satu baris> yang sama dijalankan sebagai query tabel biasa (tanpa batas teks DAX
~2,1 juta karakter yang membuat measure Detail gagal), lalu digabung di Python dengan pemisah yang sama. JS halaman
(static/summary.js, static/detail.js) membaca teks itu persis seperti di measure. Escape untuk literal JS di measure
(\\, \', \x3C) tidak dipakai: data dikirim sebagai JSON.
"""
from ...config import Config
from ...core.cache import Cache
from ...core.common import stamp_info  # noqa: F401  (stamp_info dipakai routes.py)
from ...core.powerbi import DATA_ERRORS, Dataset, query  # noqa: F401  (DATA_ERRORS dipakai routes.py)

# ID dari URL Power BI: app.powerbi.com/groups/<WORKSPACE_ID>/datasets/<DATASET_ID>/...
# Bisa ditimpa lewat .env: PICKING_SLIP_WORKSPACE_ID / PICKING_SLIP_DATASET_ID
DATASET = Dataset("PICKING_SLIP", workspace_id="3c13f5a0-78cb-4372-82eb-aa271bf8dc85",
                  dataset_id="30233aea-63d6-4d77-876f-5a3806305d02")

SEP_R = "\ue001"   # UNICHAR(57345): pemisah baris, sama dengan measure (pemisah field SEP_F = UNICHAR(57344) di DAX)

_cache = Cache(Config.CACHE_SECONDS)

# ---------------------------------------------------------------- Summary (measure dax_picking_slip_summary_v9)

SUMMARY = {
    # Data utama, satu baris per company | PS number | stock code | status | unit | warehouse | department | tanggal.
    # Urutan field: 0 company | 1 PS number | 2 stock code | 3 status code | 4 unit | 5 warehouse | 6 department |
    # 7 amount | 8 date stamp yyyyMMdd | 9 count
    "jsRaw": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
VAR grp = SUMMARIZECOLUMNS (
    'sales_order_line'[company],
    'sales_order_line'[dax_so_suffix],
    'sales_order_line'[stock_code],
    'sales_order_line'[dax_so_order_status],
    'sales_order_line'[stk_unit_desc],
    'sales_order_line'[dax_warehouse],
    'sales_order_line'[dax_department],
    'sales_order_line'[dax_so_date_stamp],
    KEEPFILTERS ( FILTER ( ALL ( 'sales_order_line'[dax_warehouse] ), 'sales_order_line'[dax_warehouse] <> "ADV" ) ),
    "amt", SUM ( 'sales_order_line'[dax_total_ps_amount] ),
    "cnt", [dax_so_order_status_category_count]
)
EVALUATE
SELECTCOLUMNS (
    grp,
    "r",
    'sales_order_line'[company] & SEP_F & 'sales_order_line'[dax_so_suffix] & SEP_F & 'sales_order_line'[stock_code] & SEP_F &
    'sales_order_line'[dax_so_order_status] & SEP_F & 'sales_order_line'[stk_unit_desc] & SEP_F & 'sales_order_line'[dax_warehouse] & SEP_F &
    'sales_order_line'[dax_department] & SEP_F &
    SUBSTITUTE ( FORMAT ( COALESCE ( [amt], 0 ), "0.##" ), ",", "." ) & SEP_F &
    FORMAT ( 'sales_order_line'[dax_so_date_stamp], "yyyyMMdd" ) & SEP_F &
    FORMAT ( COALESCE ( [cnt], 0 ), "0" )
)
""",
    # Kamus: kode status -> dax_so_order_status_category
    "jsStat": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    SUMMARIZECOLUMNS (
        'sales_order_line'[dax_so_order_status],
        'sales_order_line'[dax_so_order_status_category],
        KEEPFILTERS ( FILTER ( ALL ( 'sales_order_line'[dax_warehouse] ), 'sales_order_line'[dax_warehouse] <> "ADV" ) ),
        "n", COUNTROWS ( 'sales_order_line' )
    ),
    "r",
    'sales_order_line'[dax_so_order_status] & SEP_F & 'sales_order_line'[dax_so_order_status_category]
)
""",
    # Kamus: territory code -> dax_teritory_description
    "jsTer": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    SUMMARIZECOLUMNS (
        'sales_order_line'[dax_teritory_code],
        'sales_order_line'[dax_teritory_description],
        KEEPFILTERS ( FILTER ( ALL ( 'sales_order_line'[dax_warehouse] ), 'sales_order_line'[dax_warehouse] <> "ADV" ) ),
        "n", COUNTROWS ( 'sales_order_line' )
    ),
    "r",
    'sales_order_line'[dax_teritory_code] & SEP_F & 'sales_order_line'[dax_teritory_description]
)
""",
    # Kamus company: kode | nama | warna grup (logo & warna header)
    "jsComp": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    SUMMARIZE ( 'DWMasterIconCompany', 'DWMasterIconCompany'[Company Code], 'DWMasterIconCompany'[Company Name], 'DWMasterIconCompany'[Company Group Color] ),
    "r",
    'DWMasterIconCompany'[Company Code] & SEP_F &
    'DWMasterIconCompany'[Company Name] & SEP_F &
    'DWMasterIconCompany'[Company Group Color]
)
""",
    # Kamus per company|PS number: WO code | WO description
    "jsProj": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    SUMMARIZECOLUMNS (
        'sales_order_line'[company],
        'sales_order_line'[dax_so_suffix],
        KEEPFILTERS ( FILTER ( ALL ( 'sales_order_line'[dax_warehouse] ), 'sales_order_line'[dax_warehouse] <> "ADV" ) ),
        "wc", MAX ( 'project_commitment'[job_code] ),
        "wd", MAX ( 'project_commitment'[project_description] )
    ),
    "r",
    'sales_order_line'[company] & "|" & 'sales_order_line'[dax_so_suffix] & SEP_F & [wc] & SEP_F & [wd]
)
""",
    # Kamus stock code -> deskripsi item
    "jsItems": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    SUMMARIZECOLUMNS (
        'sales_order_line'[stock_code],
        KEEPFILTERS ( FILTER ( ALL ( 'sales_order_line'[dax_warehouse] ), 'sales_order_line'[dax_warehouse] <> "ADV" ) ),
        "nm", MAX ( 'sales_order_line'[line_description] )
    ),
    "r",
    'sales_order_line'[stock_code] & SEP_F & [nm]
)
""",
}


# ---------------------------------------------------------------- Detail (measure dax_picking_slip_detail_header_v5)

DETAIL = {
    # Data utama: satu baris per baris picking slip (company, PS number, sequence, type, item, unit, job, ...)
    "jsRaw": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    SUMMARIZECOLUMNS (
        'sales_order_line'[company],
        'sales_order_line'[dax_so_suffix],
        'sales_order_line'[sol_line_seq],
        'sales_order_line'[sol_line_type],
        'sales_order_line'[stock_code],
        'sales_order_line'[stk_unit_desc],
        'sales_order_line'[job_code],
        KEEPFILTERS ( FILTER ( ALL ( 'sales_order_line'[dax_warehouse] ), 'sales_order_line'[dax_warehouse] <> "ADV" ) ),
        KEEPFILTERS ( TREATAS ( { "S" }, 'stock_master'[stk_stock_status] ) ),
        KEEPFILTERS ( TREATAS ( { "SN" }, 'sales_order_line'[sol_line_type] ) ),
        "oq", SUM ( 'sales_order_line'[sol_ordered_qty] ),
        "sq", SUM ( 'sales_order_line'[sol_shipped_qty] ),
        "bo", SUM ( 'sales_order_line'[backorder_qty] )
    ),
    "r",
    'sales_order_line'[company] & "" & SEP_F &
    'sales_order_line'[dax_so_suffix] & "" & SEP_F &
    FORMAT ( 'sales_order_line'[sol_line_seq], "0" ) & SEP_F &
    'sales_order_line'[sol_line_type] & "" & SEP_F &
    'sales_order_line'[stock_code] & "" & SEP_F &
    'sales_order_line'[stk_unit_desc] & "" & SEP_F &
    'sales_order_line'[job_code] & "" & SEP_F &
    SUBSTITUTE ( FORMAT ( COALESCE ( [oq], 0 ), "0.####" ), ",", "." ) & SEP_F &
    SUBSTITUTE ( FORMAT ( COALESCE ( [sq], 0 ), "0.####" ), ",", "." ) & SEP_F &
    SUBSTITUTE ( FORMAT ( COALESCE ( [bo], 0 ), "0.####" ), ",", "." )
)
""",
    # Header per company|PS number: nomor gabungan, department, tanggal, status, warehouse, ...
    "jsOrd": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    SUMMARIZECOLUMNS (
        'sales_order_line'[company],
        'sales_order_line'[dax_so_suffix],
        'sales_order_line'[dax_company_so_suffix],
        'sales_order_line'[dax_department],
        'sales_order_line'[dax_so_date_stamp],
        'sales_order_line'[dax_so_order_date],
        'sales_order_line'[dax_so_delivery_date],
        'sales_order_line'[dax_so_order_status],
        'sales_order_line'[dax_warehouse],
        KEEPFILTERS ( FILTER ( ALL ( 'sales_order_line'[dax_warehouse] ), 'sales_order_line'[dax_warehouse] <> "ADV" ) ),
        KEEPFILTERS ( TREATAS ( { "S" }, 'stock_master'[stk_stock_status] ) ),
        KEEPFILTERS ( TREATAS ( { "SN" }, 'sales_order_line'[sol_line_type] ) ),
        "n", COUNTROWS ( 'sales_order_line' )
    ),
    "r",
    'sales_order_line'[company] & "|" & 'sales_order_line'[dax_so_suffix] & SEP_F &
    'sales_order_line'[dax_company_so_suffix] & "" & SEP_F &
    'sales_order_line'[dax_department] & "" & SEP_F &
    FORMAT ( 'sales_order_line'[dax_so_date_stamp], "yyyyMMdd" ) & SEP_F &
    FORMAT ( 'sales_order_line'[dax_so_order_date], "yyyyMMdd" ) & SEP_F &
    FORMAT ( 'sales_order_line'[dax_so_delivery_date], "yyyyMMdd" ) & SEP_F &
    'sales_order_line'[dax_so_order_status] & "" & SEP_F &
    'sales_order_line'[dax_warehouse] & ""
)
""",
    # Stok per company|stock code|warehouse: quantity on hand, quantity on order, ...
    "jsStk": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    SUMMARIZECOLUMNS (
        'sales_order_line'[company],
        'sales_order_line'[stock_code],
        'sales_order_line'[dax_warehouse],
        KEEPFILTERS ( FILTER ( ALL ( 'sales_order_line'[dax_warehouse] ), 'sales_order_line'[dax_warehouse] <> "ADV" ) ),
        KEEPFILTERS ( TREATAS ( { "S" }, 'stock_master'[stk_stock_status] ) ),
        KEEPFILTERS ( TREATAS ( { "SN" }, 'sales_order_line'[sol_line_type] ) ),
        "qh", MAX ( 'sales_order_line'[dax_qty_on_hand] ),
        "qo", MAX ( 'sales_order_line'[dax_qty_on_order] ),
        "ac", MAX ( 'sales_order_line'[dax_average_cost] )
    ),
    "r",
    'sales_order_line'[company] & "|" & 'sales_order_line'[stock_code] & "|" & 'sales_order_line'[dax_warehouse] & SEP_F &
    SUBSTITUTE ( FORMAT ( COALESCE ( [qh], 0 ), "0.####" ), ",", "." ) & SEP_F &
    SUBSTITUTE ( FORMAT ( COALESCE ( [qo], 0 ), "0.####" ), ",", "." ) & SEP_F &
    SUBSTITUTE ( FORMAT ( COALESCE ( [ac], 0 ), "0.####" ), ",", "." )
)
""",
    # Kamus company|stock code -> deskripsi item
    "jsDesc": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    SUMMARIZECOLUMNS (
        'sales_order_line'[company],
        'sales_order_line'[stock_code],
        KEEPFILTERS ( FILTER ( ALL ( 'sales_order_line'[dax_warehouse] ), 'sales_order_line'[dax_warehouse] <> "ADV" ) ),
        KEEPFILTERS ( TREATAS ( { "S" }, 'stock_master'[stk_stock_status] ) ),
        KEEPFILTERS ( TREATAS ( { "SN" }, 'sales_order_line'[sol_line_type] ) ),
        "ds", MAX ( 'stock_master'[dax_detail_description] )
    ),
    "r",
    'sales_order_line'[company] & "|" & 'sales_order_line'[stock_code] & SEP_F & [ds] & ""
)
""",
    # Kamus company|job code -> WO status & project description
    "jsJob": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    SUMMARIZECOLUMNS (
        'sales_order_line'[company],
        'sales_order_line'[job_code],
        KEEPFILTERS ( FILTER ( ALL ( 'sales_order_line'[dax_warehouse] ), 'sales_order_line'[dax_warehouse] <> "ADV" ) ),
        KEEPFILTERS ( TREATAS ( { "S" }, 'stock_master'[stk_stock_status] ) ),
        KEEPFILTERS ( TREATAS ( { "SN" }, 'sales_order_line'[sol_line_type] ) ),
        "ws", MAX ( 'sales_order_line'[dax_wo_status_category] ),
        "pd", MAX ( 'sales_order_line'[project_description] )
    ),
    "r",
    'sales_order_line'[company] & "|" & 'sales_order_line'[job_code] & SEP_F & [ws] & "" & SEP_F & [pd] & ""
)
""",
    # Kamus: kode status -> dax_so_order_status_category
    "jsStat": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    SUMMARIZECOLUMNS (
        'sales_order_line'[dax_so_order_status],
        'sales_order_line'[dax_so_order_status_category],
        KEEPFILTERS ( FILTER ( ALL ( 'sales_order_line'[dax_warehouse] ), 'sales_order_line'[dax_warehouse] <> "ADV" ) ),
        KEEPFILTERS ( TREATAS ( { "S" }, 'stock_master'[stk_stock_status] ) ),
        KEEPFILTERS ( TREATAS ( { "SN" }, 'sales_order_line'[sol_line_type] ) ),
        "n", COUNTROWS ( 'sales_order_line' )
    ),
    "r",
    'sales_order_line'[dax_so_order_status] & "" & SEP_F & 'sales_order_line'[dax_so_order_status_category] & ""
)
""",
    # Kamus: territory code -> dax_teritory_description
    "jsTer": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    SUMMARIZECOLUMNS (
        'sales_order_line'[dax_teritory_code],
        'sales_order_line'[dax_teritory_description],
        KEEPFILTERS ( FILTER ( ALL ( 'sales_order_line'[dax_warehouse] ), 'sales_order_line'[dax_warehouse] <> "ADV" ) ),
        KEEPFILTERS ( TREATAS ( { "S" }, 'stock_master'[stk_stock_status] ) ),
        KEEPFILTERS ( TREATAS ( { "SN" }, 'sales_order_line'[sol_line_type] ) ),
        "n", COUNTROWS ( 'sales_order_line' )
    ),
    "r",
    'sales_order_line'[dax_teritory_code] & "" & SEP_F & 'sales_order_line'[dax_teritory_description] & ""
)
""",
    # Kamus company: kode | nama | warna grup (logo & warna header)
    "jsComp": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    SUMMARIZE ( 'DWMasterIconCompany', 'DWMasterIconCompany'[Company Code], 'DWMasterIconCompany'[Company Name], 'DWMasterIconCompany'[Company Group Color] ),
    "r",
    'DWMasterIconCompany'[Company Code] & "" & SEP_F &
    'DWMasterIconCompany'[Company Name] & "" & SEP_F &
    'DWMasterIconCompany'[Company Group Color] & ""
)
""",
    # Kamus company|PS number -> WO code & project description
    "jsProj": """
DEFINE
VAR SEP_F = UNICHAR ( 57344 )
EVALUATE
SELECTCOLUMNS (
    CALCULATETABLE (
        SUMMARIZE ( 'project_commitment', 'project_commitment'[dax_company_so_suffix], 'project_commitment'[job_code], 'project_commitment'[project_description] ),
        KEEPFILTERS ( FILTER ( ALL ( 'sales_order_line'[dax_warehouse] ), 'sales_order_line'[dax_warehouse] <> "ADV" ) ),
        KEEPFILTERS ( TREATAS ( { "S" }, 'stock_master'[stk_stock_status] ) ),
        KEEPFILTERS ( TREATAS ( { "SN" }, 'sales_order_line'[sol_line_type] ) )
    ),
    "r",
    'project_commitment'[dax_company_so_suffix] & "" & SEP_F &
    'project_commitment'[job_code] & "" & SEP_F &
    'project_commitment'[project_description] & ""
)
""",
}

# Jumlah company di master logo (TOTAL_MASTER_COMP di JS: "All Companies" kalau semua company terpilih)
COMPANY_COUNT = """
EVALUATE ROW ( "v", CALCULATE ( DISTINCTCOUNT ( 'DWMasterIconCompany'[Company Code] ), ALL ( 'DWMasterIconCompany' ) ) )
"""


def _rows(dax):
    """Hasil query tabel digabung seperti CONCATENATEX ( ..., SEP_R ). Baris baru di teks diganti spasi (sama dengan measure)."""
    return SEP_R.join((r["r"] or "").replace("\r", " ").replace("\n", " ") for r in query(DATASET, dax))


def _load(queries):
    data = {name: _rows(dax) for name, dax in queries.items()}
    data["totalMasterCompCount"] = int(query(DATASET, COMPANY_COUNT)[0]["v"] or 0)
    data["jsPbiFilters"] = ""   # filter visual Power BI: tidak ada di MANTRA, filter dipilih di halaman
    return data


def summary():
    """Data halaman Summary untuk static/summary.js. Mengembalikan (data, waktu diambil)."""
    return _cache.get("summary", lambda: _load(SUMMARY))


def detail():
    """Data halaman Detail untuk static/detail.js. Mengembalikan (data, waktu diambil)."""
    return _cache.get("detail", lambda: _load(DETAIL))
