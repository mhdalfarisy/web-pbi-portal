/* Halaman Summary. Logika chart & slicer diambil dari measure dax_html_material_readiness_v16.
   Bedanya: data datang dari Flask (window.SUMMARY), dan tombol Details / klik bar membuka halaman Detail. */
(function () {
'use strict';

var P = window.SUMMARY;
/* DATA : [tipe 0=PO 1=SO, status, week category, tahun Start_Date, bulan Start_Date, count QTY_Order, count Job_Code, company] */
var DATA = P.data;
var LOGO = P.logo;
var CUR_Y = P.curY, CUR_M = P.curM;
var DEF_TM = 'ON';
var esc = Dash.esc, fmt = Dash.fmt, sRank = Dash.statusRank, moName = Dash.moName;

var CH = [
    { t: 0, m: 5, name: 'ALL Material PO Readiness',   unit: 'Count of QTY_Order' },
    { t: 1, m: 5, name: 'ALL Material SO Readiness',   unit: 'Count of QTY_Order' },
    { t: 0, m: 6, name: 'ALL Work Order PO Readiness', unit: 'Count of Job_Code' },
    { t: 1, m: 6, name: 'ALL Work Order SO Readiness', unit: 'Count of Job_Code' }
];
var HID = [{}, {}, {}, {}];
var SEP = '~|~';
var PAL = ['#0ea5e9', '#8b5cf6', '#f97316', '#a855f7', '#84cc16', '#64748b', '#ec4899', '#14b8a6', '#6366f1', '#eab308', '#0f766e', '#b45309'];
var SCOL = { 1: '#1e4d8c', 2: '#f1d98b', 3: '#d9464f', 4: '#3d9a89' };
var colMap = {};

function el(id) { return document.getElementById(id); }
function pct(x) { return ((x || 0) * 100).toFixed(1) + '%'; }

/* Warna unik per status: 4 status utama pakai warna gambar, sisanya dari palet (sama dengan Power BI) */
(function () {
    var u = {};
    DATA.forEach(function (r) { u[r[1]] = 1; });
    var used = {}, pi = 0;
    Object.keys(u).sort(function (a, b) { return (sRank(a) - sRank(b)) || a.localeCompare(b); }).forEach(function (st) {
        var r = sRank(st);
        if (SCOL[r] && !used[r]) { colMap[st] = SCOL[r]; used[r] = 1; }
        else { colMap[st] = PAL[pi % PAL.length]; pi++; }
    });
})();
function sCol(s) { return colMap[s] || '#94a3b8'; }

/* Urutan sumbu X (dax_week_category_year, mis. '41 - 2026'): tahun dulu, lalu minggu */
function wKey(v) {
    var t = String(v), m = t.match(/(\d{1,2})\D+(\d{4})/), m2 = t.match(/(\d{4})\D+(\d{1,2})/);
    if (m) { return +m[2] * 100 + +m[1]; }
    if (m2) { return +m2[1] * 100 + +m2[2]; }
    var n = parseFloat(t);
    return isNaN(n) ? null : n;
}
function wCmp(a, b) {
    var x = wKey(a), y = wKey(b);
    if (x !== null && y !== null && x !== y) { return x - y; }
    if (x !== null && y === null) { return -1; }
    if (x === null && y !== null) { return 1; }
    return String(a).localeCompare(String(b), undefined, { numeric: true });
}

/* =========================================================
   SLICER COMPANY, YEAR & MONTH (dari Start_Date)
   ========================================================= */
var YEARS = (function () {
    var m = {};
    DATA.forEach(function (r) { m[r[3]] = 1; });
    return Object.keys(m).map(Number).sort(function (a, b) { return b - a; });
})();
var YSEL = 'ALL', MSEL = 'ALL', COSEL = 'ALL';
var NO_CO = 'Unidentified';  /* baris tanpa pasangan di DWMasterIconCompany */
var COMPANIES = (function () {
    var m = {};
    DATA.forEach(function (r) { m[r[7] || NO_CO] = 1; });
    return Object.keys(m).sort(function (a, b) { return (a === NO_CO) - (b === NO_CO) || a.localeCompare(b); });
})();
function passCo(r) { return COSEL === 'ALL' || (r[7] || NO_CO) === COSEL; }
var THIS_MONTH = DEF_TM === 'ON', PREV_SEL = null;
if (THIS_MONTH) { PREV_SEL = { y: YSEL, m: MSEL }; YSEL = String(CUR_Y); MSEL = String(CUR_M); }

function yLbl() {
    if (THIS_MONTH) { return 'This Month (' + moName(CUR_M) + ' ' + CUR_Y + ')'; }
    var y = YSEL === 'ALL' ? '' : (+YSEL === 0 ? 'No Start Date' : YSEL);
    if (MSEL === 'ALL') { return y ? 'Year ' + y : 'All Years'; }
    return moName(MSEL) + ' ' + (y || '(All Years)');
}
function passPeriod(r) {
    if (!passCo(r)) { return false; }
    if (YSEL !== 'ALL' && r[3] !== +YSEL) { return false; }
    if (MSEL !== 'ALL' && r[4] !== +MSEL) { return false; }
    return true;
}

function fillSlicers() {
    var co = '<option value="ALL">All Companies</option>';
    COMPANIES.forEach(function (c) { co += '<option value="' + esc(c) + '">' + esc(c) + '</option>'; });
    var sc = el('sbCo');
    sc.innerHTML = co; sc.value = COSEL;
    sc.classList.toggle('is-active', COSEL !== 'ALL');

    var yl = YEARS.slice();
    if (THIS_MONTH && yl.indexOf(CUR_Y) < 0) { yl.unshift(CUR_Y); }
    var yo = '<option value="ALL">All Years</option>';
    yl.forEach(function (y) { yo += '<option value="' + y + '">' + (y === 0 ? 'No Date' : y) + '</option>'; });
    var sy = el('sbYr');
    sy.innerHTML = yo; sy.value = YSEL;

    /* Bulan yang tersedia mengikuti tahun yang dipilih */
    var mm = {};
    DATA.forEach(function (r) { if (passCo(r) && (YSEL === 'ALL' || r[3] === +YSEL)) { mm[r[4]] = 1; } });
    var months = Object.keys(mm).map(Number).sort(function (a, b) { return (a || 99) - (b || 99); });
    if (THIS_MONTH && months.indexOf(CUR_M) < 0) { months.push(CUR_M); months.sort(function (a, b) { return (a || 99) - (b || 99); }); }
    if (MSEL !== 'ALL' && months.indexOf(+MSEL) < 0) { MSEL = 'ALL'; }
    var mo = '<option value="ALL">All Months</option>';
    months.forEach(function (m) { mo += '<option value="' + m + '">' + moName(m) + '</option>'; });
    var sm = el('sbMo');
    sm.innerHTML = mo; sm.value = MSEL;

    sy.classList.toggle('is-active', YSEL !== 'ALL');
    sm.classList.toggle('is-active', MSEL !== 'ALL');
    /* Toggle This Month: kunci slicer Year & Month */
    sy.disabled = THIS_MONTH; sm.disabled = THIS_MONTH;
    el('sbTm').checked = THIS_MONTH;
    el('sbTmTxt').textContent = THIS_MONTH ? 'ON' : 'OFF';
    el('sbInfo').textContent = 'Showing: ' + yLbl() + (COSEL !== 'ALL' ? '  |  ' + COSEL : '') + '  |  Branch FP & ME';
    Dash.setHeaderCompany(COSEL === 'ALL' ? '' : COSEL, LOGO);
}

function onToggleTM() {
    THIS_MONTH = el('sbTm').checked;
    if (THIS_MONTH) {
        PREV_SEL = { y: YSEL, m: MSEL };
        YSEL = String(CUR_Y); MSEL = String(CUR_M);
    } else {
        YSEL = PREV_SEL ? PREV_SEL.y : 'ALL';
        MSEL = PREV_SEL ? PREV_SEL.m : 'ALL';
        PREV_SEL = null;
    }
    SCROLL = [-1, -1, -1, -1];
    fillSlicers();
    renderAll();
}
function onSlicer() {
    COSEL = el('sbCo').value;
    YSEL = el('sbYr').value;
    MSEL = el('sbMo').value;
    SCROLL = [-1, -1, -1, -1];
    fillSlicers();
    renderAll();
}
function resetSlicer() {
    COSEL = 'ALL'; YSEL = 'ALL'; MSEL = 'ALL';
    THIS_MONTH = DEF_TM === 'ON'; PREV_SEL = null;
    if (THIS_MONTH) { PREV_SEL = { y: YSEL, m: MSEL }; YSEL = String(CUR_Y); MSEL = String(CUR_M); }
    HID = [{}, {}, {}, {}];
    SCROLL = [-1, -1, -1, -1];
    fillSlicers();
    renderAll();
}

/* =========================================================
   AGGREGATION
   ========================================================= */
function agg(ci) {
    var c = CH[ci], W = {}, S = {}, M = {};
    DATA.forEach(function (r) {
        if (r[0] !== c.t) { return; }
        if (!passPeriod(r)) { return; }
        var v = r[c.m];
        if (!v) { return; }
        var w = r[2] === '' ? '(Blank)' : r[2], s = r[1];
        W[w] = 1; S[s] = 1;
        M[w + SEP + s] = (M[w + SEP + s] || 0) + v;
    });
    return {
        weeks: Object.keys(W).sort(wCmp),
        stats: Object.keys(S).sort(function (a, b) { return (sRank(a) - sRank(b)) || a.localeCompare(b); }),
        M: M
    };
}

function niceStep(max, n) {
    if (max <= 0) { return 1; }
    var raw = max / n, p = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), f = raw / p;
    var s = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
    return Math.max(1, s * p);
}

/* =========================================================
   STACKED COLUMN CHART (SVG)
   ========================================================= */
/* MIN_BAND     : lebar minimal per week (px). Kalau tidak muat, chart bisa di-scroll ke kanan/kiri
   BAR_HEADROOM : ruang kosong di atas bar tertinggi (1.06 = bar tertinggi mengisi ~94% tinggi chart)
   CHART_TOP / CHART_BOTTOM : jarak (px) area bar dari atas & bawah kotak chart */
var MIN_BAND = 62;
var BAR_HEADROOM = 1.06;
var CHART_TOP = 16, CHART_BOTTOM = 18;
var START_AT_END = false;
var SCROLL = [-1, -1, -1, -1], CACHE = [];

function renderChart(ci, quiet) {
    var box = el('chart' + ci), A = agg(ci), hid = HID[ci];
    var tot = {}, grand = 0;
    A.weeks.forEach(function (w) {
        var t = 0;
        A.stats.forEach(function (s) { if (!hid[s]) { t += A.M[w + SEP + s] || 0; } });
        tot[w] = t; grand += t;
    });
    CACHE[ci] = { A: A, tot: tot };
    el('meta' + ci).textContent = 'Total: ' + fmt(grand);
    renderLegend(ci, A);

    /* simpan posisi scroll sebelum digambar ulang */
    var oldXs = box.querySelector('.xs');
    if (oldXs && SCROLL[ci] >= 0) { SCROLL[ci] = oldXs.scrollLeft; }

    var n = A.weeks.length;
    if (!n) { el('xt' + ci).innerHTML = 'Week Category'; box.innerHTML = '<div class="empty">No data available</div>'; return; }

    var W = box.clientWidth || 300, H = box.clientHeight || 180;
    var mL = 44, mR = 10, mT = CHART_TOP, mB = CHART_BOTTOM;
    var availW = Math.max(10, W - mL);
    var band = Math.max(MIN_BAND, (availW - mR) / n);
    var contentW = Math.max(availW, band * n + mR);
    var scroll = contentW > availW + 1;
    var SH = scroll ? H - 10 : H;
    CACHE[ci].G = { mL: mL, mT: mT, ph: Math.max(10, SH - mT - mB), SH: SH, band: band, contentW: contentW,
        bw: Math.max(6, Math.min(band * 0.62, 56)), maxCh: Math.max(3, Math.floor(band / 6.3)), top: -1 };

    box.innerHTML = '<div class="yax"><svg width="' + mL + '" height="' + SH + '"></svg></div>'
        + '<div class="xs"><svg width="' + contentW.toFixed(1) + '" height="' + SH + '"></svg></div>';
    el('xt' + ci).innerHTML = 'Week Category' + (scroll ? '<span>&#8644; scroll to see all ' + n + ' weeks</span>' : '');

    var xs = box.querySelector('.xs');
    xs.scrollLeft = SCROLL[ci] < 0 ? (START_AT_END ? xs.scrollWidth : 0) : SCROLL[ci];
    SCROLL[ci] = xs.scrollLeft;
    drawBars(ci, true, quiet);
    if (scroll) { bindScroll(ci, xs); }
}

/* Gambar bar. Skala Y mengikuti nilai tertinggi dari week yang sedang terlihat.
   anim = gambar ulang penuh, quiet = tanpa animasi tumbuh (dipakai saat resize) */
function drawBars(ci, anim, quiet) {
    var C = CACHE[ci], A = C.A, G = C.G, tot = C.tot, hid = HID[ci];
    var box = el('chart' + ci), xs = box.querySelector('.xs');
    if (!xs || !G) { return; }
    var i0 = Math.max(0, Math.floor(xs.scrollLeft / G.band));
    var i1 = Math.min(A.weeks.length - 1, Math.ceil((xs.scrollLeft + xs.clientWidth) / G.band) - 1);
    var mx = 0;
    for (var k = i0; k <= i1; k++) { if (tot[A.weeks[k]] > mx) { mx = tot[A.weeks[k]]; } }
    var st = niceStep(mx, 3), top = mx > 0 ? mx * BAR_HEADROOM : st;
    if (!anim && top === G.top) { return; }
    G.top = top;
    function y(v) { return G.mT + G.ph - (v / top) * G.ph; }

    var ys = '', s = '';
    for (var v = 0; v <= top + 1e-9; v += st) {
        var yy = y(v).toFixed(1);
        ys += '<text class="ytk" x="' + (G.mL - 8) + '" y="' + yy + '" dy="0.32em" text-anchor="end">' + fmt(v) + '</text>';
        if (v > 0) { s += '<line class="gl" x1="0" x2="' + G.contentW.toFixed(1) + '" y1="' + yy + '" y2="' + yy + '"/>'; }
    }
    s += '<line class="base" x1="0" x2="' + G.contentW.toFixed(1) + '" y1="' + y(0).toFixed(1) + '" y2="' + y(0).toFixed(1) + '"/>';

    A.weeks.forEach(function (w, i) {
        var cx = G.band * i + G.band / 2, x = cx - G.bw / 2, acc = 0;
        A.stats.forEach(function (st2) {
            if (hid[st2]) { return; }
            var val = A.M[w + SEP + st2] || 0;
            if (!val) { return; }
            var y1 = Math.max(0, y(acc + val)), y0 = y(acc);
            acc += val;
            s += '<rect class="seg" x="' + x.toFixed(1) + '" y="' + y1.toFixed(1) + '" width="' + G.bw.toFixed(1) + '" height="' + Math.max(1, y0 - y1).toFixed(1) + '"'
                + ' fill="' + sCol(st2) + '" style="animation-delay:' + Math.min(Math.max(0, i - i0) * 30, 600) + 'ms"'
                + ' data-tt="' + esc(st2) + '" data-tw="' + esc(w) + '" data-tv="' + fmt(val) + '"'
                + ' data-tp="' + pct(val / tot[w]) + '" data-tot="' + fmt(tot[w]) + '" data-tc="' + sCol(st2) + '"/>';
        });
        if (tot[w] > 0) {
            s += '<text class="tot" x="' + cx.toFixed(1) + '" y="' + Math.max(10, y(tot[w]) - 5).toFixed(1) + '" text-anchor="middle">' + fmt(tot[w]) + '</text>';
        }
        var lbl = String(w);
        if (lbl.length > G.maxCh) { lbl = lbl.slice(0, G.maxCh - 1) + '…'; }
        s += '<text class="xtk" x="' + cx.toFixed(1) + '" y="' + (G.mT + G.ph + 15) + '" text-anchor="middle"><title>' + esc(w) + '</title>' + esc(lbl) + '</text>';
    });
    box.querySelector('.yax svg').innerHTML = ys;
    var sv = xs.querySelector('svg');
    sv.setAttribute('class', anim && !quiet ? 'anim' : '');
    sv.innerHTML = s;
}

/* Scroll mouse (atas/bawah) = geser kanan/kiri, dan klik-tahan-geser (drag) */
function bindScroll(ci, xs) {
    var raf = 0;
    xs.addEventListener('scroll', function () {
        SCROLL[ci] = xs.scrollLeft; hideTip();
        if (!raf) { raf = requestAnimationFrame(function () { raf = 0; drawBars(ci, false); }); }
    });
    xs.addEventListener('wheel', function (ev) {
        var d = Math.abs(ev.deltaX) > Math.abs(ev.deltaY) ? ev.deltaX : ev.deltaY;
        var max = xs.scrollWidth - xs.clientWidth;
        if ((d < 0 && xs.scrollLeft <= 0) || (d > 0 && xs.scrollLeft >= max)) { return; }
        ev.preventDefault();
        xs.scrollLeft += d;
    }, { passive: false });
    xs.addEventListener('pointerdown', function (ev) {
        if (ev.pointerType === 'mouse' && ev.button !== 0) { return; }
        if (ev.offsetY > xs.clientHeight) { return; } /* klik di scrollbar */
        DRAG = { xs: xs, x: ev.clientX, sl: xs.scrollLeft, moved: false };
    });
}
var DRAG = null, JUST_DRAGGED = false;
window.addEventListener('pointermove', function (ev) {
    if (!DRAG) { return; }
    var dx = ev.clientX - DRAG.x;
    if (!DRAG.moved && Math.abs(dx) > 4) { DRAG.moved = true; DRAG.xs.classList.add('dragging'); hideTip(); }
    if (DRAG.moved) { DRAG.xs.scrollLeft = DRAG.sl - dx; }
});
window.addEventListener('pointerup', function () {
    if (!DRAG) { return; }
    DRAG.xs.classList.remove('dragging');
    if (DRAG.moved) { JUST_DRAGGED = true; setTimeout(function () { JUST_DRAGGED = false; }, 0); }
    DRAG = null;
});

function renderLegend(ci, A) {
    var h = '';
    A.stats.forEach(function (st) {
        h += '<span class="lg' + (HID[ci][st] ? ' off' : '') + '" data-s="' + esc(st) + '" title="Click to show / hide">'
            + '<i style="background:' + sCol(st) + '"></i>' + esc(st) + '</span>';
    });
    el('leg' + ci).innerHTML = h;
}

function renderAll() { hideTip(); for (var i = 0; i < CH.length; i++) { renderChart(i); } }

/* =========================================================
   DETAIL: buka halaman Detail dengan filter yang sama
   ========================================================= */
function detailUrl(ci, week, status) {
    var p = new URLSearchParams();
    p.set('type', CH[ci].t === 0 ? 'PO' : 'SO');
    if (THIS_MONTH) {
        p.set('tm', '1');
    } else {
        p.set('tm', '0');
        if (YSEL !== 'ALL') { p.set('year', YSEL); }
        if (MSEL !== 'ALL') { p.set('month', MSEL); }
    }
    if (COSEL !== 'ALL') { p.set('company', COSEL); }
    if (week) { p.set('week', week); }
    if (status) { p.set('status', status); }
    return P.detailUrl + '?' + p.toString();
}

/* =========================================================
   TOOLTIP
   ========================================================= */
function showTip(seg, ci) {
    var c = seg.getAttribute('data-tc'), tip = el('tip');
    tip.innerHTML = '<div class="tip-head"><span class="tip-dot" style="background:' + c + '"></span>' + esc(seg.getAttribute('data-tt')) + '</div>'
        + '<div class="tip-rank">' + esc(CH[ci].name) + ' &middot; Week ' + esc(seg.getAttribute('data-tw')) + '</div>'
        + '<div class="tip-grid">'
        + '<div><small>' + esc(CH[ci].unit) + '</small><b>' + seg.getAttribute('data-tv') + '</b></div>'
        + '<div><small>% of Week</small><b>' + seg.getAttribute('data-tp') + '</b></div>'
        + '<div><small>Week Total</small><b>' + seg.getAttribute('data-tot') + '</b></div>'
        + '</div>'
        + '<div class="tip-bar"><div style="width:' + seg.getAttribute('data-tp') + ';background:' + c + '"></div></div>'
        + '<div class="tip-hint">Click to open the detail rows</div>';
    tip.classList.add('show');
}
function moveTip(ev) {
    var t = el('tip'), w = t.offsetWidth, h = t.offsetHeight, x = ev.clientX + 14, y = ev.clientY + 14;
    if (x + w > window.innerWidth - 8) { x = ev.clientX - w - 14; }
    if (y + h > window.innerHeight - 8) { y = ev.clientY - h - 14; }
    t.style.left = Math.max(4, x) + 'px';
    t.style.top = Math.max(4, y) + 'px';
}
function hideTip() { el('tip').classList.remove('show'); }

/* =========================================================
   EVENTS & INIT
   ========================================================= */
el('sbCo').addEventListener('change', onSlicer);
el('sbYr').addEventListener('change', onSlicer);
el('sbMo').addEventListener('change', onSlicer);
el('sbTm').addEventListener('change', onToggleTM);
el('sbReset').addEventListener('click', resetSlicer);

document.querySelectorAll('.detail-btn[data-ci]').forEach(function (b) {
    b.addEventListener('click', function () { location.href = detailUrl(+b.getAttribute('data-ci')); });
});

CH.forEach(function (c, ci) {
    var box = el('chart' + ci);
    box.addEventListener('mouseover', function (ev) {
        var seg = ev.target.closest('.seg');
        if (seg && !DRAG) { showTip(seg, ci); moveTip(ev); } else { hideTip(); }
    });
    box.addEventListener('mousemove', function (ev) { if (ev.target.closest('.seg')) { moveTip(ev); } });
    box.addEventListener('mouseleave', hideTip);
    box.addEventListener('click', function (ev) {
        var seg = ev.target.closest('.seg');
        if (!seg || JUST_DRAGGED) { return; }
        location.href = detailUrl(ci, seg.getAttribute('data-tw'), seg.getAttribute('data-tt'));
    });
    el('leg' + ci).addEventListener('click', function (ev) {
        var lg = ev.target.closest('.lg');
        if (!lg) { return; }
        var s = lg.getAttribute('data-s');
        if (HID[ci][s]) { delete HID[ci][s]; } else { HID[ci][s] = 1; }
        renderChart(ci);
    });
});

/* Gambar ulang chart kalau ukuran kotaknya berubah (resize jendela, layout selesai, dll) */
var SIZE = [], resizeTimer = 0;
var ro = new ResizeObserver(function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
        CH.forEach(function (c, ci) {
            var box = el('chart' + ci), key = box.clientWidth + 'x' + box.clientHeight;
            if (SIZE[ci] !== key) { SIZE[ci] = key; renderChart(ci, true); }
        });
    }, 100);
});

/* Filter aktif untuk chatbot */
window.DashContext = function () {
    var y = THIS_MONTH ? CUR_Y : YSEL, m = THIS_MONTH ? CUR_M : MSEL;
    return 'Summary page; period ' + yLbl() + ' (year=' + y + ', month=' + m + '); company: '
        + (COSEL === 'ALL' ? 'all' : COSEL);
};
window.DashFilters = function () {
    return {
        year: THIS_MONTH ? CUR_Y : (YSEL === 'ALL' ? null : +YSEL),
        month: THIS_MONTH ? CUR_M : (MSEL === 'ALL' ? null : +MSEL),
        company: COSEL === 'ALL' ? null : COSEL,
    };
};

fillSlicers();
renderAll();
CH.forEach(function (c, ci) {
    var box = el('chart' + ci);
    SIZE[ci] = box.clientWidth + 'x' + box.clientHeight;
    ro.observe(box);
});
})();
