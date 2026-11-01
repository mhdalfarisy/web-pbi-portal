# Rilis Picking Slip ke Staging & Live (`web-pbi-portal-dashboard`)

Cara kerja folder **`web-pbi-portal-dashboard/mantra/dashboards/picking_slip/`**: apa isinya, bagaimana isinya
terbentuk, dan langkah menaikkan versi baru ke **staging** lalu **live**.

Alur development sebelum tahap ini (membuat dan mengubah kode di `web-pbi-portal`) ada di
**`PANDUAN_PICKING_SLIP.md`**.

---

## 1. Aturan utama: folder ini TIDAK dikerjakan dengan tangan

`web-pbi-portal-dashboard` adalah **paket rilis**, yaitu hasil cetakan otomatis dari `web-pbi-portal`. Setiap rilis,
isinya **dihapus lalu dicetak ulang**. Akibatnya:

- jangan mengedit, menambah, atau menghapus file di `web-pbi-portal-dashboard/mantra/dashboards/picking_slip/`, karena
  perubahannya akan **hilang** di rilis berikutnya;
- jangan menaruh catatan atau dokumen di folder ini (alasan yang sama);
- **semua perubahan Picking Slip dikerjakan di `web-pbi-portal/mantra/dashboards/picking_slip/`**, lalu dicetak ke
  sini.

Jadi "development di `web-pbi-portal-dashboard`" artinya: **mencetak paket, memeriksa isinya, lalu mengirimnya ke
server**, bukan menulis kode.

---

## 2. Peta folder, GitHub, dan server

```text
LAPTOP                                   GITHUB                                  SERVER SUMOPOD (43.173.42.175)

web-pbi-portal                     ──►   mhdalfarisy/web-pbi-portal
(tempat ngoding, branch develop)         (branch develop = backup kode)
        │
        │ cetak paket
        ▼
web-pbi-portal-dashboard           ──►   mhdalfarisy/test-prod-pbi-apps
(paket rilis)                              ├─ branch staging ──────────────►   /opt/mantra-staging
                                           │                                    https://staging.43-173-42-175.sslip.io
                                           └─ branch main ─────────────────►   /opt/mantra   (LIVE)
                                                                                https://43-173-42-175.sslip.io
```

- Branch **`staging`** berisi versi yang **sedang dicoba**.
- Branch **`main`** berisi versi **live** yang dipakai user.
- Live **hanya menerima versi yang sudah lewat staging**. Paketnya tidak dicetak ulang, melainkan versi yang sama
  dipindahkan dari `staging` ke `main`.

---

## 3. Isi `picking_slip/` di paket vs di folder kerja

| File | `web-pbi-portal` (kerja) | `web-pbi-portal-dashboard` (paket) | Alasan |
|---|---|---|---|
| `__init__.py`, `queries.py`, `routes.py`, `tools.py` | ✅ | ✅ | dibutuhkan website |
| `templates/picking_slip/` (`_ui.html`, `summary.html`, `detail.html`) | ✅ | ✅ | dibutuhkan website |
| `static/` (`picking.css`, `picking.js`) | ✅ | ✅ | dibutuhkan browser |
| `prompts/` (`system.md`, `data_dictionary.md`) | ✅ | ✅ | dibaca AI agent saat website jalan |
| `chat_cases.py` | ✅ | ❌ | hanya untuk menguji AI di laptop |
| `tests/test_picking_slip.py` | ✅ | ❌ | test tidak dijalankan di server |
| `docs/`, `README.md`, file panduan | ✅ | ❌ | dokumentasi tidak dibutuhkan server |
| `.env` (secret), `instance/` (database) | ✅ (laptop) | ❌ | setiap server punya `.env` dan database sendiri |

Selain itu, paket berisi `VERSION`, yang mencatat **nomor commit `web-pbi-portal`** asal paket, misalnya
`6b2b31b  develop`. Dengan begitu selalu jelas kode mana yang sedang berjalan di server.

---

## 4. Syarat sebelum rilis

1. Perubahan di `web-pbi-portal` sudah **lulus test**, **di-commit**, dan **di-push** (lihat `PANDUAN_PICKING_SLIP.md`,
   tahap 10–13).
2. Jaringan **mengizinkan SSH** ke server. Wi-Fi kantor memblokir SSH; pakai hotspot HP.
3. Laptop sudah punya akses SSH ke server (SSH key terpasang) dan akses push ke repo `test-prod-pbi-apps`.

---

## 5. Cara A: otomatis (dipakai sehari-hari)

Dari folder `web-pbi-portal` (bukan dari folder paket):

```bash
cd ~/Documents/Portfolio/web-pbi-portal
scripts/release.sh staging
```

Yang terjadi otomatis:

1. Menolak jalan kalau masih ada perubahan yang belum di-commit.
2. Mencetak paket ke `web-pbi-portal-dashboard`.
3. Menyimpan paket sebagai commit `Release <nomor commit>` di repo paket.
4. Mengirimnya ke branch `staging` di GitHub.
5. Menyuruh server staging update: backup database, ambil versi baru, install library, restart, cek `/healthz`.

Output yang benar:

```text
Paket baru: Release 6b2b31b
Backup: /var/lib/mantra-staging/backups/mantra-....db
staging: 3ed5c99 -> ea23572  (VERSION: 6b2b31b  develop)  healthz OK
```

**Coba di staging:** `https://staging.43-173-42-175.sslip.io/d/picking-slip/`. Pastikan ada label oranye STAGING, lalu
cek Summary, Detail, filter, Ask AI, dan dashboard lain. Kalau aman:

```bash
scripts/release.sh live
```

Yang terjadi: versi yang **sama** dengan staging dipindahkan ke branch `main`, lalu server live update dengan urutan
yang sama.

```text
Naik ke live: ea23572 Release 6b2b31b
live: 3ed5c99 -> ea23572  (VERSION: 6b2b31b  develop)  healthz OK
```

**Cek di live:** `https://43-173-42-175.sslip.io/d/picking-slip/`.

---

## 6. Cara B: manual, langkah demi langkah

Isinya sama dengan cara A, tapi dikerjakan satu per satu. Berguna untuk belajar, atau kalau cara A berhenti di tengah
jalan (misalnya karena SSH terputus).

### Staging

| No | Di folder | Perintah | Fungsi |
|---|---|---|---|
| 1 | `web-pbi-portal` | `git status` dan `git log --oneline -1` | pastikan bersih, catat nomor commit |
| 2 | `web-pbi-portal` | `scripts/build_production.sh ../web-pbi-portal-dashboard` | cetak paket |
| 3 | `web-pbi-portal-dashboard` | `cat VERSION` dan `git status --short` | cek asal paket dan file yang berubah (`VERSION` tidak boleh berakhiran `-belum-commit`) |
| 4 | `web-pbi-portal-dashboard` | `git add -A` lalu `git commit -m "Release <nomor commit>"` | simpan sebagai versi rilis |
| 5 | `web-pbi-portal-dashboard` | `git push origin HEAD:staging` | kirim ke branch staging |
| 6 | mana saja | `ssh ubuntu@43.173.42.175 mantra-update staging` | server staging update |
| 7 | browser | buka staging | coba |

### Live

| No | Di folder | Perintah | Fungsi |
|---|---|---|---|
| 8 | `web-pbi-portal-dashboard` | `git fetch origin` lalu `git log --oneline -1 origin/staging` | lihat versi yang sudah dicoba |
| 9 | `web-pbi-portal-dashboard` | `git push origin origin/staging:main` | pindahkan versi yang sama ke live (ditolak kalau `main` punya versi lain, sebagai pengaman) |
| 10 | mana saja | `ssh ubuntu@43.173.42.175 mantra-update live` | server live update |
| 11 | browser | buka live | cek |

---

## 7. Mengecek versi yang sedang berjalan

| Yang dicek | Cara |
|---|---|
| Posisi branch paket | di `web-pbi-portal-dashboard`: `git fetch origin` lalu `git log --oneline --decorate -3`. Kalau `origin/staging` dan `origin/main` ada di commit yang sama, staging = live |
| Versi di server | `ssh ubuntu@43.173.42.175 'sudo git -C /opt/mantra-staging log --oneline -1; sudo git -C /opt/mantra log --oneline -1'` |
| Service jalan | `ssh ubuntu@43.173.42.175 'systemctl is-active mantra-staging mantra'` → `active active` |
| Website sehat | buka `/healthz` di staging dan live → `{"status":"ok"}` |
| Kode asal | isi file `VERSION` di paket = nomor commit `web-pbi-portal` |

---

## 8. Kembali ke versi sebelumnya

- **Cara rapi** (tercatat di git): di `web-pbi-portal`, batalkan commit terakhir dengan `git revert HEAD`, push, lalu
  rilis ulang ke staging, cek, dan rilis ke live.
- **Cara darurat** (live langsung kembali dalam hitungan detik): di server, kembalikan folder `/opt/mantra` ke nomor
  commit lama (terlihat di output rilis, angka sebelum tanda `->`), lalu restart service `mantra`. Setelah itu rapikan
  dengan cara rapi.

Database **tidak ikut berubah** saat rilis atau rollback, dan selalu di-backup otomatis sebelum setiap update
(`/var/lib/mantra/backups/` dan `/var/lib/mantra-staging/backups/`).

---

## 9. Kalau ada masalah

| Muncul | Penyebab | Solusi |
|---|---|---|
| `Ada perubahan yang belum di-commit` | kode di `web-pbi-portal` belum di-commit | commit & push dulu |
| `VERSION` berakhiran `-belum-commit` | paket dicetak dari kode yang belum di-commit | commit dulu, cetak ulang |
| `Paket tidak berubah dari rilis sebelumnya` | tidak ada perubahan kode server sejak rilis terakhir | wajar (yang berubah mungkin hanya docs atau test) |
| `rejected (non-fast-forward)` saat naik live | `main` punya versi yang tidak ada di `staging` | selalu lewat staging dulu; jangan push langsung ke `main` |
| `Connection reset by ... port 22` | jaringan memblokir SSH | pakai hotspot, jalankan ulang |
| `GAGAL start setelah update` | versi baru error saat start | jalankan perintah "kembali ke versi lama" yang dicetak, lalu lihat log server (`journalctl -u mantra-staging`) |
| Staging lambat / data belum berubah | kuota staging 20 query/menit, cache 10 menit | tunggu 1 menit / 10 menit |
| Folder paket berisi file yang tidak dikenal | ada yang mengedit folder paket dengan tangan | cetak ulang dari `web-pbi-portal`; jangan edit folder paket |

---

## 10. Ringkasan

```text
web-pbi-portal (ngoding, test, commit, push)
   → scripts/release.sh staging   (cetak paket → branch staging → server staging)
   → coba di staging
   → scripts/release.sh live      (versi yang sama → branch main → server live)
   → cek di live → beri akses user di Admin → Users
```

`web-pbi-portal-dashboard` cukup dibuka untuk **memeriksa** isi paket (`VERSION`, file yang ikut, riwayat rilis), bukan
untuk menulis kode.
