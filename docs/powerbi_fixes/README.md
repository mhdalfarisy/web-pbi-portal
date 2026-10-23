# Perbaikan DAX report Power BI "PANI - PRCS - Processing"

MANTRA menghitung ulang semua angka report ini. Saat dibandingkan (`scripts\compare_pani_report.py`), ditemukan bug di
beberapa measure report. File `.dax` di folder ini adalah versi yang sudah diperbaiki. Bagian yang diubah selalu
ditandai komentar `PERBAIKAN`. Tampilan HTML/CSS tidak diubah.

Semua file sudah diuji langsung ke semantic model (lewat `DEFINE MEASURE`, report tidak berubah) dengan
`python scripts\compare_pani_report.py --fixed`. Hasilnya **348/348 sama dengan MANTRA** (19 measure) di keempat halaman dan
14 skenario filter.

## Daftar perbaikan

### Halaman Production (tabel `mpx_stockpile_summary_view`)

| Measure | Bug di report | Perbaikan |
|---|---|---|
| `Card_TotalInput_HTML` | Baris "Tonnes" berisi angka BCM | Tonnes = BCM x 2.19 (faktor yang sama dengan diagram alur) |
| `Card_TotalOutput_HTML` | Sama | Tonnes = BCM x 1.93 |
| `Card_NetMovement_HTML` | Sama | Tonnes = Output x 1.93 - Input x 2.19 |
| `Card_GrandTotal_HTML` | Sama | Tonnes = Input x 2.19 + Output x 1.93 |
| `Bottom_Dashboard_HTML` | Net = Input - Output (tandanya berlawanan dengan kartu Net Movement), Tonnes x 1.6, % Loss/Gain dibagi output | Net = Output - Input, Tonnes memakai 2.19 / 1.93, % terhadap input |
| `Trend_Produksi_Dynamic_HTML` | Daily: setiap batang berisi total yang sama dan berlanjut sampai hari ini. Weekly/MTD: mengabaikan filter tanggal. Garis Net = Input - Output | Data diambil per tanggal yang ada di filter, lalu Weekly/MTD dijumlahkan dari data itu. Garis Net = Output - Input |
| `Insight_Rekomendasi_HTML` | Semua teks ditulis tetap ("Stockpile WD4 42.53%", "FOB 25.85%", "PA% 85.15%", dst.) | Semua teks dihitung dari filter: lokasi input/output tertinggi, net movement, PA% equipment hari terakhir rentang, rekomendasi |
| `Flow_Dashboard_HTML` | Bar di bawah Crushing/Screening/Stockpile lebarnya tetap (biru 20%, oranye 80%) | Lebar bar = porsi tiap tahapan dari total ketiganya (biru Crushing, hijau Screening, oranye Stockpile) |

### Halaman Equipment Performance (tabel `mpx_dmr_view`)

| Measure | Bug di report | Perbaikan |
|---|---|---|
| `Card_ActiveUnit_HTML` | Garis sparkline digambar tetap (`M 0 0 Q 30 20 80 22 ...`), tidak mengikuti data | Garis dihitung dari jumlah unit aktif per tanggal |
| `Card_AvgPA_HTML` | Sama | Garis dihitung dari PA% harian |
| `Card_AvgUA_HTML` | Sama | Garis dihitung dari UA% harian |
| `Card_InactiveUnit_HTML` | Titik garis tidak diurutkan (CONCATENATEX tanpa urutan), jadi garis bisa melompat | Titik diurutkan per tanggal |
| `Top_5_Inactive_HTML` | Selalu memakai status "active": tabel kosong saat status Inactive dipilih | Mengikuti status yang dipilih. Tanpa pilihan status, semua unit ikut dihitung. Seri diputus dengan kode unit, jadi hasilnya selalu 5 baris |

### Halaman Processing

Tidak ada bug. Semua angka sama dengan MANTRA.

### Halaman Mining Production (tabel `mpx_daily_pondok_view`)

| Measure | Bug di report | Perbaikan |
|---|---|---|
| `Table_PerformanceSummary_HTML` | Out-Pit "bebas unit": baris ton dan bcm ikut dijumlahkan (mis. 55,018, seharusnya 36,616), sehingga Total Mining Movement ikut salah. `ROUND(…, 2)` lalu `FORMAT "#,##0"` membulatkan dua kali (2,366,949.4997 menjadi 2,366,950) | Out-Pit difilter `unit = "ton"`. Sisa desimal dibuang dengan `ROUND(…, 6)` |
| `Card_KeyHighlights_HTML` | leaf_key salah ketik `"total_output_movement"`, akibatnya Total MTD Movement = Total Mined dan Out-Pit kosong ("above plan by  t"). Satuan "bcm". Weather Loss angka tetap 0.0 dan disembunyikan | leaf_key `"total_outpit_movement"`. Satuan "t". Selisih memakai tanda +/-, persen hanya kalau plan ada. Weather Loss dihitung (lihat catatan) dan ditampilkan |
| `Card_TotalMovement_HTML` | Label "bcm" untuk nilai ton | Label "t" |
| `Card_TotalWasteMined_HTML` | Sama | Label "t" |
| `All_In_One_TotalMined_Card_RealChart`, `All_In_One_TotalMovement_Card_RealChart` | Titik legend "Cumm Plan" hijau, padahal garisnya merah | Titik legend merah |

Catatan Weather Loss: dihitung dari `mpx_dmr_gainloss_view`, kategori Hujan, Jalan Licin, Kabut, Petir, Debu, dari awal
bulan sampai tanggal terakhir filter. Rumus ini sama dengan MANTRA. Kalau kategori cuacanya berbeda, ubah daftar di
measure ini dan `WEATHER_LOSS` di `mantra/dashboards/pani_processing/queries.py`.

## Cara memasang di Power BI

Lakukan untuk setiap file `.dax`:

1. Buka model "PANI - PRCS - Processing" (Power BI Desktop, atau web: workspace > model > **Open data model**).
2. Di panel **Data**, buka tabel yang tertera di atas, lalu klik measure dengan nama yang sama dengan nama file.
3. Klik di formula bar, tekan Ctrl+A, lalu tempel seluruh isi file `.dax` (baris pertama `NamaMeasure =` ikut ditempel).
4. Tekan Enter. Simpan / publish ulang kalau memakai Desktop.

Setelah semua dipasang, jalankan:

```powershell
python scripts\compare_pani_report.py
```

Semua baris "BEDA*" seharusnya berubah menjadi "OK", sehingga hasil akhirnya "0 beda karena bug report".

## Kalau DAX di report berubah lagi

Simpan versi barunya di file `.dax` yang sama, lalu uji dulu sebelum ditempel:

```powershell
python scripts\compare_pani_report.py --fixed
```
