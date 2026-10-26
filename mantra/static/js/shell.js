/* Kerangka MANTRA (semua halaman): sidebar ringkas / drawer, loading saat pindah halaman, tombol favorit. */
(function () {
'use strict';

const root = document.documentElement;
const body = document.body;
const CSRF = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
const DESKTOP = window.matchMedia('(min-width: 1200px)');

/* ---------- sidebar ----------
   Desktop (>= 1200px): tombol menu meringkas sidebar jadi ikon saja; pilihan disimpan di browser.
   Tablet (900-1199px): sidebar selalu ringkas; tombol menu membuka sidebar penuh di atas konten.
   Mobile (< 900px): sidebar tersembunyi; tombol menu membukanya sebagai drawer. */
const toggle = document.getElementById('navToggle');
const main = document.querySelector('.main');

function setNavOpen(open) {
    body.classList.toggle('nav-open', open);
    syncAria();
}
function syncAria() {
    const expanded = DESKTOP.matches ? !root.classList.contains('sb-mini') : body.classList.contains('nav-open');
    toggle.setAttribute('aria-expanded', String(expanded));
}

if (toggle) {
    toggle.addEventListener('click', () => {
        if (DESKTOP.matches) {
            try { localStorage.setItem('mantra.sidebar', root.classList.contains('sb-mini') ? 'full' : 'mini'); } catch (e) { /* mode privat */ }
            window.mantraSidebar();
            syncAria();
        } else {
            setNavOpen(!body.classList.contains('nav-open'));
        }
    });
    document.getElementById('scrim').addEventListener('click', () => setNavOpen(false));
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && body.classList.contains('nav-open')) { setNavOpen(false); toggle.focus(); }
    });
    DESKTOP.addEventListener('change', () => { body.classList.remove('nav-open'); syncAria(); });
    window.addEventListener('resize', () => window.mantraSidebar());
    syncAria();
}

/* Lebar area konten berubah tanpa resize jendela saat sidebar diringkas / dilebarkan.
   Chart report digambar ulang lewat event resize, jadi kirim event itu setelah animasi selesai. */
if (main) {
    main.addEventListener('transitionend', (e) => {
        if (e.target === main && e.propertyName === 'margin-left') { window.dispatchEvent(new Event('resize')); }
    });
}

/* ---------- loading saat pindah halaman ----------
   Halaman report mengambil data Power BI di server sebelum tampil, jadi bisa butuh beberapa detik.
   Loader muncul setelah jeda singkat (lihat .page-loader di shell.css) supaya tidak berkedip di halaman yang cepat. */
const loaderText = document.getElementById('pageLoaderText');
const REPORT_LABEL = 'Memuat report dari Power BI...';
const DEFAULT_LABEL = body.classList.contains('is-report-page') ? REPORT_LABEL : 'Memuat halaman...';
let nextLabel = DEFAULT_LABEL;

document.addEventListener('click', (e) => {
    const a = e.target.closest('a[href]');
    if (!a || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) { return; }
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin) { return; }
    nextLabel = url.pathname.startsWith('/d/') ? REPORT_LABEL : 'Memuat halaman...';
});
window.addEventListener('beforeunload', () => {
    if (loaderText) { loaderText.textContent = nextLabel; }
    root.classList.add('is-loading');
    body.classList.remove('nav-open');
});
/* Kembali lewat tombol Back browser (halaman dari cache): sembunyikan loader lagi */
window.addEventListener('pageshow', () => {
    root.classList.remove('is-loading');
    nextLabel = DEFAULT_LABEL;
});

/* ---------- favorit (kartu report & tombol bintang di top bar halaman report) ---------- */
document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.fav-btn');
    if (!btn) { return; }
    e.preventDefault();
    btn.disabled = true;
    try {
        const r = await fetch('/api/favorites/' + encodeURIComponent(btn.dataset.slug), {
            method: 'POST', headers: { 'X-CSRF-Token': CSRF },
        });
        const data = await r.json();
        if (!r.ok) { throw new Error(data.error || r.status); }
        btn.classList.toggle('on', data.favorite);
        btn.setAttribute('aria-pressed', String(data.favorite));
        btn.title = data.favorite ? 'Hapus dari Favorites' : 'Tambahkan ke Favorites';
        /* Di halaman Favorites, kartu yang batal difavoritkan langsung hilang */
        const grid = document.getElementById('favoriteGrid');
        if (grid && !data.favorite) {
            btn.closest('.report-card').remove();
            if (!grid.children.length) { grid.hidden = true; document.getElementById('favoriteEmpty').hidden = false; }
        }
    } catch (err) {
        btn.title = 'Gagal menyimpan favorit';
    }
    btn.disabled = false;
});
})();
