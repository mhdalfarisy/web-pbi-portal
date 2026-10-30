# Ebook MANTRA

`MANTRA_Development_Ebook.pdf` = seluruh isi `docs/` (panduan development berurutan, playbook 00-33, AUTH.md) dalam
satu PDF: sampul, daftar isi & bookmark yang bisa di-klik, link antar bab, dan diagram mermaid yang sudah digambar.

Bangun ulang setelah dokumentasi berubah (dari root project):

```bash
python docs/ebook/build_ebook.py
```

Butuh `pandoc` (`brew install pandoc`) dan Google Chrome. Urutan bab diatur di `PARTS` dalam `build_ebook.py`;
dokumen `.md` baru yang belum dimasukkan ke `PARTS` dilaporkan sebagai peringatan saat build. Tampilan cetak ada di
`ebook.css`, kerangka HTML di `template.html`. File kerja sementara di `.build/` (tidak masuk git).
