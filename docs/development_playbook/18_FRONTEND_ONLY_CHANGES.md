# 18 — Workflow C: Perubahan Frontend Saja

### A. Objective
Mengubah tampilan (spacing, sidebar, responsif, tabel, tombol filter, panel AI, warna, tipografi) tanpa mengubah
logika bisnis backend.

### B. When to use
Perubahan yang hanya menyentuh `.html`, `.css`, `.js` **dan** tidak mengubah data yang dikirim/diminta ke server.
Jika butuh field baru dari server → Workflow D ([19](19_BACKEND_AND_DATA_CONTRACT_CHANGES.md)).

### C. Prerequisites
Server berjalan, browser dengan DevTools (F12).

### D. Architecture context
Lihat [08](08_FRONTEND_ARCHITECTURE.md): `base.html` → `portal/base.html` / `dashboard/base.html` → halaman. Template
& static dibaca dari disk: perubahan **template** terlihat setelah refresh jika `FLASK_DEBUG=1` (auto reload);
dengan `FLASK_DEBUG=0` restart server bila perubahan tidak muncul. Perubahan CSS/JS: refresh keras (`Ctrl+F5`) untuk
menghindari cache browser.

### E. Files involved — menemukan file yang benar

| Yang dilihat di layar | File |
|---|---|
| Sidebar | `templates/components/sidebar.html`, `static/css/shell.css`, `static/js/shell.js` (perilaku), skrip inline di `base.html` (breakpoint) |
| Top bar, breadcrumb, favorit, tombol Ask AI | `templates/components/topbar.html`, `shell.css` |
| Kartu report, Home, Reports | `templates/portal/_ui.html` (`report_card`), `portal/home.html`, `reports.html`, `portal.css` |
| Header biru report, menu halaman | `templates/dashboard/base.html`, `dashboard.css` (`.hd`) |
| Panel AI (floating) | `dashboard/base.html` (markup), `dashboard.css` (`.chat-panel`), `static/js/chat.js` |
| Isi halaman Material Readiness | `material_readiness/templates/...`, `summary.js` / `detail.js`, `dashboard.css` |
| Isi halaman PANI | `pani_processing/templates/...`, `_ui.html` (bar filter), `pani.css`, `pani.js` |
| Login | `portal/_auth_layout.html`, `login.html`, `portal.css` |
| Admin | `templates/admin/*`, `portal.css` |

Cara pasti: DevTools → *Elements* → klik elemen → lihat class → `grep` class itu di `mantra/static` dan
`mantra/templates` / `mantra/dashboards`. DevTools → *Network* → lihat file CSS/JS yang benar-benar dimuat.

### F. Step-by-step instructions
1. Reproduksi di browser; catat ukuran viewport.
2. Tentukan jenis masalah:
   | Tanda | Jenis |
   |---|---|
   | Elemen ada di *Elements* tapi tampilannya salah | CSS |
   | Elemen tidak ada di HTML sumber (`Ctrl+U`) | Template / kondisi Jinja |
   | Ada di sumber tapi hilang/berubah setelah load; error di *Console* | JavaScript |
   | Angka/teks salah di HTML sumber | Data backend → Workflow D |
   | Sidebar/top bar hilang | Template tidak extend `dashboard/base.html` / `portal/base.html` |
3. Ubah file sekecil mungkin. Komponen bersama (dok 08 §3) → periksa dampak ke semua halaman.
4. Report: breakpoint isi report pakai `@container dash (...)`, **bukan** `@media`.
5. Ukuran global: token di `:root` `shell.css` (`--sidebar-w`, `--topbar-h`, warna).
6. Validasi (K).

### G. Code or patch (contoh pola)
```css
/* dashboard.css — responsif isi report mengikuti lebar area report, bukan jendela */
@container dash (max-width: 900px) {
  .contoh-grid { grid-template-columns: 1fr; }
}
```

### H. Code explanation
`.dash` adalah container; sidebar penuh/ringkas/tersembunyi mengubah lebar area report tanpa mengubah lebar jendela,
sehingga `@media` memberi hasil salah.

### I. Commands
```powershell
python -m pytest            # memastikan template tetap ter-render di test
python run.py
```

### J. Expected result
Tampilan berubah sesuai tujuan; tidak ada error di Console; test lulus.

### K. Validation — viewport & regresi
| Lebar | Mode sidebar (Verified dari `base.html`) |
|---|---|
| ≥ 1200 px | penuh / bisa diringkas (disimpan di `localStorage`) |
| 900-1199 px | selalu ringkas |
| < 900 px | drawer |

Cek di 1280, 1000, 800 px (DevTools *device toolbar*). Regression checklist komponen bersama: Home, Reports,
satu Admin, Login, Material Readiness Summary + Detail, satu halaman PANI, panel Ask AI, favorit (klik bintang),
console bersih.

### L. Troubleshooting
| Gejala | Solusi |
|---|---|
| Perubahan CSS tidak terlihat | `Ctrl+F5`; cek *Network* file yang dimuat |
| Perubahan template tidak terlihat | Restart server (`FLASK_DEBUG=0`) |
| Tombol favorit / chat error 400 | Meta `csrf-token` hilang dari `base.html` |
| Console: `Dash is not defined` | `dash-common.js` tidak dimuat (template tidak extend `dashboard/base.html`) |
| `Pani is not defined` | `{{ scripts() }}` dari `_ui.html` belum dipanggil |

### M. Regression impact
`shell.css`, `shell.js`, `sidebar.html`, `topbar.html`, `base.html`, `dashboard/base.html`, `dashboard.css`,
`dash-common.js`, `chat.js` = semua halaman / semua report.

### N. Acceptance criteria
Tujuan tercapai di 3 lebar, regression checklist lulus, test lulus, tidak ada perubahan pada `.py`.

### O. Documentation updates
Dok 08 jika komponen/token baru.

### P. Actual status
Prosedur: NOT RUN (tidak ada perubahan UI di sesi ini). Tidak ada test otomatis untuk JS/visual (`Not Found`).
