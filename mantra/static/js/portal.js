/* Portal MANTRA: menu mobile, favorit (bintang), dan filter halaman Reports. */
(function () {
'use strict';

const CSRF = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';

/* ---------- menu sidebar di layar kecil ---------- */
const toggle = document.getElementById('navToggle');
if (toggle) {
    toggle.addEventListener('click', () => document.body.classList.toggle('nav-open'));
    document.getElementById('scrim').addEventListener('click', () => document.body.classList.remove('nav-open'));
}

/* ---------- favorit ---------- */
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

/* ---------- filter Reports (search + kategori) ---------- */
const grid = document.getElementById('reportGrid');
if (grid) {
    const search = document.getElementById('reportSearch');
    const category = document.getElementById('reportCategory');
    const apply = () => {
        const q = search.value.trim().toLowerCase();
        const c = category.value;
        let shown = 0;
        grid.querySelectorAll('.report-card').forEach((card) => {
            const ok = (!q || card.dataset.search.includes(q)) && (!c || card.dataset.category === c);
            card.hidden = !ok;
            shown += ok ? 1 : 0;
        });
        document.getElementById('reportEmpty').hidden = shown > 0;
    };
    search.addEventListener('input', apply);
    category.addEventListener('change', apply);
    apply();
}
})();
