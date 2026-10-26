/* Halaman portal: filter halaman Reports (search + kategori). Sidebar & favorit ada di shell.js. */
(function () {
'use strict';

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
