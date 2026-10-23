/* Halaman Detail: filter, KPI dan tabel diproses di server (/api/detail), state disimpan di URL. */
(function () {
'use strict';

const P = window.DETAIL;
const { esc, fmt, badgeColor, moName } = Dash;
const el = (id) => document.getElementById(id);
const TEXT_KEYS = ['company', 'plant', 'warehouse', 'status', 'doc', 'week', 'q'];
const RANK_COLOR = { ready: '#16a34a', in_progress: '#f59e0b', approval: '#2563eb', not_ready: '#dc2626', other: '#94a3b8' };

let S = readState();
let LAST = null;
let SEQ = 0;

function readState() {
    const p = new URLSearchParams(location.search);
    const s = {
        type: (p.get('type') || 'PO').toUpperCase() === 'SO' ? 'SO' : 'PO',
        tm: p.get('tm') !== '0',
        year: p.get('year') || 'ALL',
        month: p.get('month') || 'ALL',
        sort: p.get('sort') || 'start_date',
        dir: p.get('dir') === 'desc' ? 'desc' : 'asc',
        page: +p.get('page') || 1,
        size: +p.get('size') || 50,
    };
    TEXT_KEYS.forEach((k) => { s[k] = p.get(k) || ''; });
    return s;
}

function toParams() {
    const p = new URLSearchParams();
    p.set('type', S.type);
    p.set('tm', S.tm ? '1' : '0');
    if (!S.tm) {
        if (S.year !== 'ALL') { p.set('year', S.year); }
        if (S.month !== 'ALL') { p.set('month', S.month); }
    }
    TEXT_KEYS.forEach((k) => { if (S[k]) { p.set(k, S[k]); } });
    p.set('sort', S.sort);
    p.set('dir', S.dir);
    p.set('page', S.page);
    p.set('size', S.size);
    return p.toString();
}

async function load() {
    const seq = ++SEQ;
    const qs = toParams();
    history.replaceState(null, '', '?' + qs);
    el('tblWrap').classList.add('loading');
    let data;
    try {
        const r = await fetch(P.api + '?' + qs, { headers: { Accept: 'application/json' } });
        if (!(r.headers.get('content-type') || '').includes('json')) { location.reload(); return; } /* sesi habis */
        data = await r.json();
        if (!r.ok) { throw new Error(data.error || 'HTTP ' + r.status); }
    } catch (e) {
        if (seq !== SEQ) { return; }
        el('tblWrap').classList.remove('loading');
        el('pageInfo').textContent = 'Gagal mengambil data dari Power BI: ' + e.message;
        return;
    }
    if (seq !== SEQ) { return; }
    el('tblWrap').classList.remove('loading');
    LAST = data;
    S.page = data.page;
    S.sort = data.filters.sort;
    history.replaceState(null, '', '?' + toParams());
    render(data);
}

/* ---------------------------------------------------------------- render */

function fillSelect(sel, items, value, allLabel) {
    let h = '<option value="">' + esc(allLabel) + '</option>';
    let found = !value;
    items.forEach(([v, t]) => {
        if (String(v) === String(value)) { found = true; }
        h += '<option value="' + esc(v) + '">' + esc(t) + '</option>';
    });
    if (!found) { h += '<option value="' + esc(value) + '">' + esc(value) + '</option>'; }
    sel.innerHTML = h;
    sel.value = value;
    sel.classList.toggle('is-active', !!value);
}

function render(d) {
    const o = d.options, f = d.filters, T = S.type;

    el('pillType').textContent = 'Detail - ' + T;
    document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('on', b.dataset.type === T));
    el('tabPO').textContent = fmt(d.tabs.PO);
    el('tabSO').textContent = fmt(d.tabs.SO);
    /* Sama seperti report Power BI: kalau baris terlalu banyak, hanya sebagian yang dimuat */
    const truncated = d.matched > d.total;
    el('rowsChip').textContent = truncated
        ? '⚠ ' + fmt(d.total) + ' / ' + fmt(d.matched) + ' rows loaded · pick a month in slicer'
        : fmt(d.total) + ' rows';
    el('rowsChip').classList.toggle('warn', truncated);
    el('hdDate').textContent = d.fetched.date;
    el('hdTime').textContent = d.fetched.time;

    /* Year & Month: saat This Month ON, tampilkan bulan berjalan dan kunci pilihan */
    const years = o.years.map((y) => [y, y === 0 ? 'No Date' : y]);
    const yv = f.year === null ? '' : String(f.year);
    fillSelect(el('fYear'), years, yv, 'All Years');
    const months = o.months.map((m) => [m, moName(m)]);
    fillSelect(el('fMonth'), months, f.month === null ? '' : String(f.month), 'All Months');
    el('fYear').disabled = el('fMonth').disabled = S.tm;
    el('fTm').checked = S.tm;
    el('fTmTxt').textContent = S.tm ? 'ON' : 'OFF';

    fillSelect(el('fCompany'), o.companies.map((c) => [c, c]), S.company, 'All');
    fillSelect(el('fPlant'), o.plants.map(([no, desc]) => [no, desc ? no + ' - ' + desc : no]), S.plant, 'All');
    fillSelect(el('fWarehouse'), o.warehouses.map((w) => [w, w]), S.warehouse, 'All');
    fillSelect(el('fStatus'), o.statuses.map((s) => [s, s]), S.status, 'All');
    el('docList').innerHTML = o.docs.map((v) => '<option value="' + esc(v) + '">').join('');
    if (document.activeElement !== el('fDoc')) { el('fDoc').value = S.doc; }
    el('fDoc').classList.toggle('is-active', !!S.doc);

    const wk = el('fWeek');
    wk.hidden = !S.week;
    wk.innerHTML = S.week ? '<span>Week ' + esc(S.week) + '</span><span aria-hidden="true">&times;</span>' : '';
    wk.title = 'Hapus filter week';

    const period = S.tm ? 'This Month (' + moName(f.month) + ' ' + f.year + ')'
        : (f.month !== null ? moName(f.month) + ' ' : '') + (f.year !== null ? (f.year === 0 ? 'No Start Date' : f.year) : (f.month !== null ? '(All Years)' : 'All Years'));
    el('fInfo').textContent = 'Showing: ' + T + ' · ' + period + ' · Branch FP & ME';
    Dash.setHeaderCompany(S.company === 'Unidentified' ? '' : S.company, P.logo);

    renderKpi(d.kpi, T);
    renderTable(d);
    renderPager(d);
}

function pct(n, total) { return total ? (n / total * 100).toFixed(1) + '%' : '0.0%'; }

function renderKpi(k, T) {
    el('k1Label').textContent = 'Selected ' + T + ' Readiness';
    el('k1Val').textContent = fmt(k.total);
    el('k1Sub').innerHTML = '<span class="ok">' + fmt(k.ready) + ' Ready (' + pct(k.ready, k.total) + ')</span> · '
        + fmt(k.not_ready) + ' Not Ready';
    el('k1Bar').innerHTML = ['ready', 'in_progress', 'approval', 'other', 'not_ready']
        .filter((key) => k[key])
        .map((key) => '<div style="width:' + (k[key] / k.total * 100) + '%;background:' + RANK_COLOR[key] + '" title="' + key.replace('_', ' ') + ': ' + fmt(k[key]) + '"></div>')
        .join('');

    el('k2Label').textContent = T + ' Not Ready';
    el('k2Val').textContent = fmt(k.not_ready);
    el('k2Sub').innerHTML = '<span class="bad">' + pct(k.not_ready, k.total) + '</span> of ' + fmt(k.total) + ' rows · '
        + fmt(k.in_progress) + ' In Progress';
    el('k2Bar').innerHTML = k.total ? '<div style="width:' + (k.not_ready / k.total * 100) + '%;background:#dc2626"></div>' : '';

    el('k3Val').textContent = k.lead_days === null ? '-' : k.lead_days.toFixed(1) + ' days';
    el('k3Sub').textContent = 'Start Date → Schedule Date · ' + fmt(k.lead_rows) + ' rows';
}

function fmtDate(v) {
    if (!v) { return '-'; }
    const [y, m, d] = String(v).slice(0, 10).split('-');
    return d + '/' + m + '/' + y;
}

function cell(v, kind) {
    if (kind === 'date') { return '<td>' + fmtDate(v) + '</td>'; }
    if (v === null || v === undefined || v === '') { return '<td>-</td>'; }
    if (kind === 'number') { return '<td class="r">' + Number(v).toLocaleString('en-US') + '</td>'; }
    if (kind === 'type') { return '<td><span class="tpill">' + esc(v) + '</span></td>'; }
    if (kind === 'status') { return '<td><span class="badge" style="background:' + badgeColor(v) + '">' + esc(v) + '</span></td>'; }
    return '<td title="' + esc(v) + '">' + esc(v) + '</td>';
}

function renderTable(d) {
    const head = d.columns.map((c) => {
        const on = c.key === S.sort;
        const arrow = on ? (S.dir === 'asc' ? ' ▲' : ' ▼') : '';
        return '<th data-key="' + c.key + '" class="' + (on ? 'on ' : '') + (c.kind === 'number' ? 'r' : '') + '">' + esc(c.label) + arrow + '</th>';
    }).join('');
    el('tbl').tHead.innerHTML = '<tr>' + head + '</tr>';
    const body = d.rows.length
        ? d.rows.map((r) => '<tr>' + d.columns.map((c) => cell(r[c.key], c.kind)).join('') + '</tr>').join('')
        : '<tr><td class="none" colspan="' + d.columns.length + '">No data available</td></tr>';
    el('tbl').tBodies[0].innerHTML = body;
}

function renderPager(d) {
    el('size').value = String(d.size);
    el('prev').disabled = d.page <= 1;
    el('next').disabled = d.page >= d.pages;
    const from = d.total ? (d.page - 1) * d.size + 1 : 0;
    const to = Math.min(d.total, d.page * d.size);
    el('pageInfo').textContent = 'Page ' + fmt(d.page) + ' of ' + fmt(d.pages) + ' · rows ' + fmt(from) + '–' + fmt(to) + ' of ' + fmt(d.total);
}

/* ---------------------------------------------------------------- events */

function set(changes, keepPage) {
    Object.assign(S, changes);
    if (!keepPage) { S.page = 1; }
    load();
}

el('fYear').addEventListener('change', (e) => set({ year: e.target.value || 'ALL', month: 'ALL' }));
el('fMonth').addEventListener('change', (e) => set({ month: e.target.value || 'ALL' }));
el('fTm').addEventListener('change', (e) => {
    /* Matikan This Month: mulai dari bulan berjalan supaya tidak langsung memuat semua tahun */
    if (!e.target.checked && LAST) { set({ tm: false, year: String(LAST.filters.year), month: String(LAST.filters.month) }); }
    else { set({ tm: e.target.checked }); }
});
el('fCompany').addEventListener('change', (e) => set({ company: e.target.value }));
el('fPlant').addEventListener('change', (e) => set({ plant: e.target.value }));
el('fWarehouse').addEventListener('change', (e) => set({ warehouse: e.target.value }));
el('fStatus').addEventListener('change', (e) => set({ status: e.target.value }));
el('fDoc').addEventListener('change', (e) => set({ doc: e.target.value.trim() }));
el('fWeek').addEventListener('click', () => set({ week: '' }));
el('fReset').addEventListener('click', () => {
    const keep = { type: S.type, sort: 'start_date', dir: 'asc', size: S.size };
    S = Object.assign(readState(), { tm: true, year: 'ALL', month: 'ALL' }, keep);
    TEXT_KEYS.forEach((k) => { S[k] = ''; });
    el('q').value = '';
    set({});
});

document.querySelectorAll('#tabs button').forEach((b) => {
    b.addEventListener('click', () => { if (b.dataset.type !== S.type) { set({ type: b.dataset.type, status: '', sort: 'start_date', dir: 'asc' }); } });
});

let qTimer = 0;
el('q').value = S.q;
el('q').addEventListener('input', (e) => {
    clearTimeout(qTimer);
    qTimer = setTimeout(() => set({ q: e.target.value.trim() }), 300);
});

el('tbl').addEventListener('click', (e) => {
    const th = e.target.closest('th[data-key]');
    if (!th) { return; }
    const key = th.dataset.key;
    set({ sort: key, dir: S.sort === key && S.dir === 'asc' ? 'desc' : 'asc' });
});

el('size').addEventListener('change', (e) => set({ size: +e.target.value }));
el('prev').addEventListener('click', () => set({ page: S.page - 1 }, true));
el('next').addEventListener('click', () => set({ page: S.page + 1 }, true));

/* Copy to Excel: semua baris sesuai filter (bukan hanya halaman ini), format tab-separated */
el('copyBtn').addEventListener('click', async () => {
    const btn = el('copyBtn'), label = btn.querySelector('span');
    label.textContent = 'Copying...';
    try {
        const r = await fetch(P.exportUrl + '?' + toParams());
        const text = await r.text();
        const n = Math.max(0, text.split('\n').length - 2);
        try {
            await navigator.clipboard.writeText(text);
            label.textContent = 'Copied ' + fmt(n) + ' rows ✓';
        } catch (e) {
            /* Clipboard butuh HTTPS; kalau ditolak, unduh sebagai file */
            const a = document.createElement('a');
            a.href = URL.createObjectURL(new Blob(['﻿' + text], { type: 'text/tab-separated-values' }));
            a.download = 'material_readiness_' + S.type.toLowerCase() + '.tsv';
            a.click();
            label.textContent = 'Downloaded ' + fmt(n) + ' rows';
        }
    } catch (e) {
        label.textContent = 'Copy failed';
    }
    setTimeout(() => { label.textContent = 'Copy to Excel'; }, 2500);
});

/* Filter aktif untuk chatbot */
window.DashContext = () => {
    const f = LAST ? LAST.filters : {};
    const parts = ['Halaman Detail ' + S.type, 'year=' + (f.year ?? 'semua'), 'month=' + (f.month ?? 'semua')];
    ['company', 'plant', 'warehouse', 'status', 'doc', 'week', 'q'].forEach((k) => { if (S[k]) { parts.push(k + '=' + S[k]); } });
    return parts.join('; ');
};
window.DashFilters = () => {
    const f = LAST ? LAST.filters : {};
    return { year: f.year ?? null, month: f.month ?? null, company: S.company || null };
};

load();
})();
