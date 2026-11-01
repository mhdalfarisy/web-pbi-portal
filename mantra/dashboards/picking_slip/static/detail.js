/* Halaman Detail Picking Slip: JavaScript dari measure dax_picking_slip_detail_header_v5, dibungkus fungsi supaya tidak
   bentrok dengan JS MANTRA. Data dari queries.py lewat window.PICKING_SLIP (di measure: literal teks dari DAX).
   Logo i.ibb.co -> i.ibb.co.com sama dengan core.common.fix_logo_url (i.ibb.co diblokir di beberapa jaringan). */
(function () {
    var PS = window.PICKING_SLIP;

    var RAW_TXT  = PS.jsRaw;
    var ORD_TXT  = PS.jsOrd;
    var STK_TXT  = PS.jsStk;
    var DESC_TXT = PS.jsDesc;
    var JOB_TXT  = PS.jsJob;
    var STAT_TXT = PS.jsStat;
    var TER_TXT  = PS.jsTer;
    var COMP_TXT = PS.jsComp;
    var PROJ_TXT = PS.jsProj;
    var PBI_FILTERS_TXT = PS.jsPbiFilters;
    var TOTAL_MASTER_COMP = PS.totalMasterCompCount;
    // Pemisah field / baris (sama dengan UNICHAR 57344 / 57345 di DAX)
    var SF = '', SR = '';
    var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    var SLICERS = [
    { id: 'sbCompany',  key: 'cn',  label: 'All Companies' },
    { id: 'sbWoCode',   key: 'wc',  label: 'All WO Codes' },
    { id: 'sbPsNum',    key: 'psn', label: 'All PS Numbers' },
    { id: 'sbPsItem',   key: 'psi', label: 'All PS Items' },
    { id: 'sbPsStat',   key: 'pss', label: 'All PS Status' },
    { id: 'sbUnitDesc', key: 'u',   label: 'All Units' },
    { id: 'sbWh',       key: 'w',   label: 'All Warehouses' },
    { id: 'sbTer',      key: 't',   label: 'All Territories' },
    { id: 'sbPsDesc',   key: 'psd', label: 'All PS Descriptions' },
    { id: 'sbWoDesc',   key: 'wod', label: 'All WO Descriptions' }
    ];
    var COLS = [
    { k: 'c',    h: 'Company Code',          t: 's', a: 'c' },
    { k: 'cn',   h: 'Company Name',          t: 's' },
    { k: 'psn',  h: 'PS Number',             t: 's' },
    { k: 'seq',  h: 'Sequence',              t: 'i', a: 'c' },
    { k: 'typ',  h: 'Type',                  t: 's', a: 'c' },
    { k: 'psi',  h: 'Item Code',             t: 's' },
    { k: 'u',    h: 'PS Unit Description',   t: 's', a: 'c' },
    { k: 'ides', h: 'Item Description',      t: 's' },
    { k: 'qoh',  h: 'Quantity On Hand',      t: 'n', sum: 1 },
    { k: 'qoo',  h: 'Quantity PO On Order',  t: 'n', sum: 1 },
    { k: 'job',  h: 'WO Number',             t: 's' },
    { k: 'jobd', h: 'WO Description',         t: 's' },
    { k: 'wos',  h: 'WO Status',              t: 's', st: 1 },
    { k: 'psd',  h: 'Department',             t: 's' },
    { k: 'tc',   h: 'Territory Code',         t: 's', a: 'c' },
    { k: 't',    h: 'Territory Description',  t: 's' },
    { k: 'dus',  h: 'Update Date',            t: 'd', a: 'c' },
    { k: 'dor',  h: 'Date',                   t: 'd', a: 'c' },
    { k: 'drq',  h: 'Required Date',          t: 'd', a: 'c' },
    { k: 'sts',  h: 'Status',                 t: 's' },
    { k: 'pss',  h: 'Status Category',        t: 's', st: 1 },
    { k: 'cost', h: 'Line Item Cost',         t: 'n' },
    { k: 'w',    h: 'Warehouse',              t: 's', a: 'c' },
    { k: 'oq',   h: 'SO Order Quantity',      t: 'n', sum: 1 },
    { k: 'sq',   h: 'Shipped Quantity',       t: 'n', sum: 1 },
    { k: 'bo',   h: 'Backorder',              t: 'n', sum: 1 },
    { k: 'amt',  h: 'Total Amount',           t: 'n', sum: 1 },
    { k: 'samt', h: 'Total Shipped Amount',   t: 'n', sum: 1 }
    ];
    // Default: Year / Month / Day = All, Today = Off, Rows = All
    var DATA = [], FS = {}, DSEL = { y: 0, m: 0, d: 0 };
    var todayOn = false, cachedDate = null, MS_OPEN = '', INITED = false, ALL_COMP = 0;
    var VIEW = [], PAGE = 1, PSIZE = 999999, SORT = { k: '', dir: 1 }, HIDE = Object.create(null), QRY = '';

    function el(id) { return document.getElementById(id); }
    function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/'/g, '&#39;').replace(/\x22/g, '&quot;'); }
    function cmp(a, b) { return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' }); }
    function num(v) { var n = parseFloat(v); return isNaN(n) ? 0 : n; }
    function fmtN(n, dec) { return Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }); }
    function fmtD(v) { v = String(v || ''); return v.length === 8 ? v.substr(6, 2) + '/' + v.substr(4, 2) + '/' + v.substr(0, 4) : ''; }
    function cellText(r, c) {
    var v = r[c.k];
    if (c.t === 'n') return fmtN(v, 2);
    if (c.t === 'i') return v === '' || v == null ? '' : String(v);
    if (c.t === 'd') return fmtD(v);
    return v == null ? '' : String(v);
    }
    function rawText(r, c) {
    var v = r[c.k];
    if (c.t === 'n') return String(Math.round(num(v) * 100) / 100);
    if (c.t === 'd') return fmtD(v);
    return v == null ? '' : String(v);
    }
    function stCls(v) {
    var s = String(v || '').toLowerCase();
    if (/overdue|hold|cancel|closed - not|reject/.test(s)) return 'st-bad';
    if (/complete|finish|closed|invoic|shipped/.test(s)) return 'st-ok';
    if (/pending|backorder|progress|printed|waiting/.test(s)) return 'st-warn';
    if (/ready|open|entered/.test(s)) return 'st-info';
    return '';
    }
    function dict(txt, nVal) {
    var m = Object.create(null);
    if (!txt) return m;
    var rs = txt.split(SR);
    for (var i = 0; i < rs.length; i++) {
    var p = rs[i].split(SF);
    if (p.length < nVal + 1 || (p[0] in m)) continue;
    m[p[0]] = nVal === 1 ? p[1] : p.slice(1);
    }
    return m;
    }

    var COMP_COLOR = Object.create(null);
    var COMP_NAME_TO_CODE = Object.create(null);

    function parseData() {
    DATA = [];
    var comp = dict(COMP_TXT, 2), proj = dict(PROJ_TXT, 2), ord = dict(ORD_TXT, 7), stk = dict(STK_TXT, 3), desc = dict(DESC_TXT, 1),
    job = dict(JOB_TXT, 2), stat = dict(STAT_TXT, 1), ter = dict(TER_TXT, 1), seen = Object.create(null);

    for (var cc in comp) {
    var cName = comp[cc][0], cColor = comp[cc][1];
    if (cColor) COMP_COLOR[cName] = cColor;
    COMP_NAME_TO_CODE[cName.toLowerCase()] = cc;
    COMP_NAME_TO_CODE[cc.toLowerCase()] = cc;
    }

    if (!RAW_TXT) return;
    var rows = RAW_TXT.split(SR), NO = ['', '', '', '', '', '', ''], NS = ['0', '0', '0'], NJ = ['', ''];
    for (var i = 0; i < rows.length; i++) {
    var p = rows[i].split(SF);
    if (p.length < 10) continue;
    // o: 0 company_so_suffix | 1 department | 2 dax_so_date_stamp | 3 order date | 4 delivery date | 5 status | 6 warehouse
    var c = p[0], o = ord[c + '|' + p[1]] || NO, wh = o[6];
    var s = stk[c + '|' + p[4] + '|' + wh] || NS, jb = job[c + '|' + p[6]] || NJ, pj = proj[o[0]] || ['', ''];
    var dept = o[1], tc = dept.substr(6, 2);
    // Slicer Year / Month / Day diambil dari sales_order_line[dax_so_date_stamp]
    var cost = num(s[2]), oq = num(p[7]), sq = num(p[8]), dt = parseInt(o[2], 10) || 0;
    if (!(c in seen)) { seen[c] = 1; ALL_COMP++; }
    var compName = comp[c] ? comp[c][0] : c;
    DATA.push({
    c: c, cn: compName, wc: pj[0], wod: pj[1], psn: p[1], seq: p[2], typ: p[3], psi: p[4], u: p[5],
    ides: desc[c + '|' + p[4]] || '', qoh: num(s[0]), qoo: num(s[1]), job: p[6], jobd: jb[1], wos: jb[0],
    psd: dept, tc: tc, t: ter[tc] || '', dus: o[2], dor: o[3], drq: o[4], sts: o[5], pss: stat[o[5]] || '',
    cost: cost, w: wh, oq: oq, sq: sq, bo: num(p[9]), amt: cost * oq, samt: cost * sq,
    y: Math.floor(dt / 10000), m: Math.floor(dt / 100) % 100, d: dt % 100
    });
    }
    }

    function getSl(id) { for (var i = 0; i < SLICERS.length; i++) if (SLICERS[i].id === id) return SLICERS[i]; return null; }
    function selOf(id) { return FS[id] || (FS[id] = { v: Object.create(null), n: 0 }); }
    function inPeriod(r) { return (!DSEL.y || r.y === DSEL.y) && (!DSEL.m || r.m === DSEL.m) && (!DSEL.d || r.d === DSEL.d); }

    function passSlicers(r, skipId) {
    for (var k = 0; k < SLICERS.length; k++) {
    var s = SLICERS[k], sel = FS[s.id];
    if (s.id === skipId) continue;
    if (sel && sel.n && !(r[s.key] in sel.v)) return false;
    }
    return true;
    }

    function calcOpts() {
    var sets = {}, counts = {};
    SLICERS.forEach(function (s) {
    sets[s.id] = Object.create(null);
    counts[s.id] = Object.create(null);
    var sel = selOf(s.id);
    for (var v in sel.v) sets[s.id][v] = 1;
    });
    for (var i = 0; i < DATA.length; i++) {
    var r = DATA[i];
    if (!inPeriod(r)) continue;
    for (var k = 0; k < SLICERS.length; k++) {
        var s = SLICERS[k];
        if (passSlicers(r, s.id)) {
            var val = r[s.key];
            sets[s.id][val] = 1;
            counts[s.id][val] = (counts[s.id][val] || 0) + 1;
        }
    }
    }
    SLICERS.forEach(function (s) {
    s.opts = Object.keys(sets[s.id]).sort(cmp);
    s.counts = counts[s.id];
    });
    }

    function buildSlicers() {
    SLICERS.forEach(function (s, i) {
    var box = el(s.id);
    if (!box) return;
    if (i >= SLICERS.length - 3) box.classList.add('right');
    box.innerHTML =
    '<button type=\'button\' class=\'ms-btn\' data-sl=\'' + s.id + '\'></button>' +
    '<div class=\'ms-panel\'>' +
    '<div class=\'ms-tools\'><input type=\'text\' class=\'ms-search\' data-sl=\'' + s.id + '\' placeholder=\'Search...\'>' +
    '<button type=\'button\' class=\'ms-clear\' data-sl=\'' + s.id + '\'>Clear</button></div>' +
    '<div class=\'ms-list\'></div>' +
    '</div>';
    });
    }

    function applyPbiFilters() {
    if (!PBI_FILTERS_TXT) return;
    var comp = dict(COMP_TXT, 2);
    var entries = PBI_FILTERS_TXT.split(SR);
    entries.forEach(function (ent) {
    var parts = ent.split(SF);
    if (parts.length < 2) return;
    var key = parts[0], rawVals = parts[1].split(';');
    var targetKey = (key === 'c' || key === 'cn_raw') ? 'cn' : key;
    var targetSlicer = null;
    for (var i = 0; i < SLICERS.length; i++) {
    if (SLICERS[i].key === targetKey) { targetSlicer = SLICERS[i]; break; }
    }
    if (!targetSlicer) return;
    var sel = selOf(targetSlicer.id);
    rawVals.forEach(function (v) {
    var finalVal = v;
    if (key === 'c' && comp[v]) finalVal = comp[v][0];
    if (!(finalVal in sel.v)) {
    sel.v[finalVal] = 1;
    sel.n++;
    }
    });
    });
    }

    function renderOpts(s) {
    var box = el(s.id);
    if (!box) return;
    var list = box.querySelector('.ms-list'), inp = box.querySelector('.ms-search');
    var q = inp ? inp.value.toLowerCase().trim() : '';
    var sel = selOf(s.id), h = '', shown = 0, total = 0, LIM = 300;
    for (var i = 0; i < s.opts.length; i++) {
    var v = s.opts[i], txt = v === '' ? '(Blank)' : v;
    if (q && txt.toLowerCase().indexOf(q) < 0) continue;
    total++;
    if (shown >= LIM) continue;
    shown++;
    var on = v in sel.v;
    var cnt = (s.counts && s.counts[v]) ? s.counts[v] : 0;
    h += '<div class=\'ms-opt' + (on ? ' is-on' : '') + '\' data-sl=\'' + s.id + '\' data-i=\'' + i + '\'>' +
    '<input type=\'checkbox\' tabindex=\'-1\'' + (on ? ' checked' : '') + '>' +
    '<span class=\'t\' title=\'' + esc(txt) + '\'>' + esc(txt) + '</span>' +
    '<span class=\'ms-cnt\'>(' + fmtN(cnt, 0) + ')</span></div>';
    }
    if (!total) h = '<div class=\'ms-note\'>No results</div>';
    else if (total > shown) h += '<div class=\'ms-note\'>Showing ' + shown + ' of ' + total + '. Type to search.</div>';
    list.innerHTML = h;
    }

    function updateBtn(s) {
    var box = el(s.id), btn = box && box.querySelector('.ms-btn');
    if (!btn) return;
    var sel = selOf(s.id);
    var isAll = false;
    if (s.id === 'sbCompany') {
    isAll = (!sel.n) || (TOTAL_MASTER_COMP > 0 && sel.n >= TOTAL_MASTER_COMP);
    } else {
    isAll = (!sel.n) || (s.opts && sel.n >= s.opts.length);
    }

    if (isAll) {
    btn.textContent = s.label;
    btn.classList.remove('is-active');
    }
    else if (sel.n === 1) {
    var k;
    for (k in sel.v) break;
    btn.textContent = k === '' ? '(Blank)' : k;
    btn.classList.add('is-active');
    }
    else {
    btn.textContent = sel.n + ' Selected';
    btn.classList.add('is-active');
    }
    btn.title = btn.textContent;
    }

    function refreshSlicers() { calcOpts(); SLICERS.forEach(function (s) { renderOpts(s); updateBtn(s); }); }

    function toggleOpt(id, i) {
    var s = getSl(id);
    if (!s) return;
    var v = s.opts[i], sel = selOf(id);
    if (v in sel.v) { delete sel.v[v]; sel.n--; } else { sel.v[v] = 1; sel.n++; }
    PAGE = 1; applyFilters();
    }

    function clearSlicer(id) { FS[id] = { v: Object.create(null), n: 0 }; PAGE = 1; applyFilters(); }

    function closeAll() {
    if (MS_OPEN) msToggleOpen(MS_OPEN);
    var ccBox = el('ccBox');
    if (ccBox) ccBox.classList.remove('open');
    }

    function msToggleOpen(id) {
    MS_OPEN = (MS_OPEN === id) ? '' : id;
    SLICERS.forEach(function (s) { var b = el(s.id); if (b) b.classList.toggle('open', s.id === MS_OPEN); });
    if (MS_OPEN) {
    var ccBox = el('ccBox');
    if (ccBox) ccBox.classList.remove('open');
    var inp = el(MS_OPEN).querySelector('.ms-search');
    if (inp) inp.focus();
    }
    }

    function daysIn(y, m) { if (!m) return 31; return new Date(Date.UTC(y || 2000, m, 0)).getUTCDate(); }

    function fillSel(id, items, cur) {
    var s = el(id), h = '';
    items.forEach(function (it) { h += '<option value=\'' + it[0] + '\'' + (String(it[0]) === String(cur) ? ' selected' : '') + '>' + esc(it[1]) + '</option>'; });
    s.innerHTML = h;
    s.classList.toggle('is-active', +cur > 0);
    }

    // Daftar Year / Month / Day diambil dari sales_order_line[dax_so_date_stamp] (field y, m, d di DATA)
    function renderDate() {
    var years = [], ySeen = {}, months = [], mSeen = {}, days = [], dSeen = {};
    DATA.forEach(function (r) {
    if (!r.y) return;
    if (!ySeen[r.y]) { ySeen[r.y] = 1; years.push(r.y); }
    if (DSEL.y && r.y !== DSEL.y) return;
    if (r.m && !mSeen[r.m]) { mSeen[r.m] = 1; months.push(r.m); }
    if (DSEL.m && r.m !== DSEL.m) return;
    if (r.d && !dSeen[r.d]) { dSeen[r.d] = 1; days.push(r.d); }
    });
    if (DSEL.y && !ySeen[DSEL.y]) years.push(DSEL.y);
    if (DSEL.m && !mSeen[DSEL.m]) months.push(DSEL.m);
    if (DSEL.d && !dSeen[DSEL.d]) days.push(DSEL.d);
    years.sort(function (a, b) { return b - a; });
    months.sort(function (a, b) { return a - b; });
    days.sort(function (a, b) { return a - b; });
    fillSel('sbYr', [[0, 'All']].concat(years.map(function (y) { return [y, y]; })), DSEL.y);
    fillSel('sbMo', [[0, 'All']].concat(months.map(function (m) { return [m, MON[m - 1]]; })), DSEL.m);
    fillSel('sbDy', [[0, 'All']].concat(days.map(function (d) { return [d, d]; })), DSEL.d);
    }

    function onDateChange() {
    if (todayOn) setTodayBtn(false);
    DSEL = { y: +el('sbYr').value || 0, m: +el('sbMo').value || 0, d: +el('sbDy').value || 0 };
    PAGE = 1; renderDate(); applyFilters();
    }

    function setTodayBtn(on) { todayOn = on; var b = el('btnToday'); b.classList.toggle('is-active', on); b.textContent = on ? 'On' : 'Off'; }

    function toggleToday() {
    if (todayOn) { setTodayBtn(false); DSEL = cachedDate || { y: 0, m: 0, d: 0 }; }
    else {
    cachedDate = { y: DSEL.y, m: DSEL.m, d: DSEL.d };
    var n = new Date();
    DSEL = { y: n.getFullYear(), m: n.getMonth() + 1, d: n.getDate() };
    setTodayBtn(true);
    }
    PAGE = 1; renderDate(); applyFilters();
    }

    function visCols() { return COLS.filter(function (c) { return !HIDE[c.k]; }); }

    function buildView() {
    var q = QRY.toLowerCase(), vc = visCols(), out = [];
    for (var i = 0; i < DATA.length; i++) {
    var r = DATA[i];
    if (!inPeriod(r) || !passSlicers(r, '')) continue;
    if (q) {
    var hit = false;
    for (var j = 0; j < vc.length && !hit; j++) { if (cellText(r, vc[j]).toLowerCase().indexOf(q) >= 0) hit = true; }
    if (!hit) continue;
    }
    out.push(r);
    }
    if (SORT.k) {
    var c = null;
    COLS.forEach(function (x) { if (x.k === SORT.k) c = x; });
    var numeric = c && (c.t === 'n' || c.t === 'i' || c.t === 'd');
    out.sort(function (a, b) {
    var x = a[SORT.k], y = b[SORT.k];
    var res = numeric ? (num(x) - num(y)) : cmp(x, y);
    return res * SORT.dir;
    });
    }
    VIEW = out;
    }

    function renderTable() {
    var vc = visCols(), tb = el('tb');
    if (!vc.length) {
        tb.innerHTML = '<tbody><tr><td class=\'tb-empty\'>No columns selected. Please choose columns from the Columns menu.</td></tr></tbody>';
        renderFoot(0);
        return;
    }

    var h = '<thead><tr>';
    h += '<th style=\'width:40px;text-align:center;\'>No</th>';
    vc.forEach(function (c) {
        var on = SORT.k === c.k;
        h += '<th data-k=\'' + c.k + '\' class=\'' + (on ? 'sorted' : '') + '\' title=\'Click to sort\'>' + esc(c.h) +
             '<span class=\'si\'>' + (on ? (SORT.dir > 0 ? '&#9650;' : '&#9660;') : '&#9650;&#9660;') + '</span></th>';
    });
    h += '</tr></thead><tbody>';

    var pages = Math.max(1, Math.ceil(VIEW.length / PSIZE));
    if (PAGE > pages) PAGE = pages;
    var s = (PAGE - 1) * PSIZE, e = Math.min(VIEW.length, s + PSIZE);

    if (!VIEW.length) {
        h += '<tr><td class=\'tb-empty\' colspan=\'' + (vc.length + 1) + '\'>No data available for the selected filters</td></tr>';
    }

    for (var i = s; i < e; i++) {
        var r = VIEW[i];
        h += '<tr>';
        h += '<td class=\'c\' style=\'font-weight:600;color:#64748b;\'>' + (i + 1) + '</td>';
        for (var j = 0; j < vc.length; j++) {
            var c = vc[j], tx = cellText(r, c);
            var cls = (c.t === 'n' ? 'n' : (c.a === 'c' || c.t === 'i' ? 'c' : '')) + (c.st ? ' ' + stCls(tx) : '');
            h += '<td class=\'' + cls + '\' data-r=\'' + i + '\' data-k=\'' + c.k + '\' title=\'' + esc(tx) + '\'>' + esc(tx) + '</td>';
        }
        h += '</tr>';
    }
    h += '</tbody><tfoot><tr>';

    var tot = {};
    vc.forEach(function (c) { if (c.sum) tot[c.k] = 0; });
    for (var t = 0; t < VIEW.length; t++) { for (var k in tot) tot[k] += VIEW[t][k] || 0; }

    h += '<td></td>';
    vc.forEach(function (c, j) {
        if (c.sum) h += '<td class=\'n\'>' + fmtN(tot[c.k], 2) + '</td>';
        else h += '<td>' + (j === 0 ? 'Total' : '') + '</td>';
    });
    h += '</tr></tfoot>';

    tb.innerHTML = h;
    renderFoot(pages);
    }

    function renderFoot(pages) {
    var n = VIEW.length, s = n ? (PAGE - 1) * PSIZE + 1 : 0, e = Math.min(n, PAGE * PSIZE);
    el('tbInfo').textContent = 'Showing ' + fmtN(s, 0) + '–' + fmtN(e, 0) + ' of ' + fmtN(n, 0) + ' records';
    var h = '<button type=\'button\' data-p=\'' + (PAGE - 1) + '\'' + (PAGE <= 1 ? ' disabled' : '') + '>&#8249;</button>';
    var list = [], P = pages;
    if (P <= 7) { for (var i = 1; i <= P; i++) list.push(i); }
    else {
    list.push(1);
    var a = Math.max(2, PAGE - 1), b = Math.min(P - 1, PAGE + 1);
    if (PAGE <= 3) { a = 2; b = 5; }
    if (PAGE >= P - 2) { a = P - 4; b = P - 1; }
    if (a > 2) list.push('...');
    for (var j = a; j <= b; j++) list.push(j);
    if (b < P - 1) list.push('...');
    list.push(P);
    }
    list.forEach(function (p) {
    if (p === '...') h += '<span class=\'dots\'>...</span>';
    else h += '<button type=\'button\' data-p=\'' + p + '\' class=\'' + (p === PAGE ? 'on' : '') + '\'>' + p + '</button>';
    });
    h += '<button type=\'button\' data-p=\'' + (PAGE + 1) + '\'' + (PAGE >= P ? ' disabled' : '') + '>&#8250;</button>';
    el('tbPg').innerHTML = h;
    }

    function renderColChooser() {
    var h = '';
    COLS.forEach(function (c) {
    var on = !HIDE[c.k];
    h += '<div class=\'ms-opt' + (on ? ' is-on' : '') + '\' data-cc=\'' + c.k + '\'><input type=\'checkbox\' tabindex=\'-1\'' + (on ? ' checked' : '') + '><span class=\'t\'>' + esc(c.h) + '</span></div>';
    });
    el('ccList').innerHTML = h;
    var nv = visCols().length;
    el('ccLbl').textContent = nv === COLS.length ? 'All Columns' : nv + ' Columns';
    el('ccBtn').classList.toggle('is-active', nv !== COLS.length);
    }

    var toastT = null;
    function toast(msg) {
    var t = el('toast');
    t.textContent = msg; t.classList.add('on');
    clearTimeout(toastT); toastT = setTimeout(function () { t.classList.remove('on'); }, 1600);
    }

    function showCopyBox(txt) {
    var ta = el('cpmTa');
    ta.value = txt; el('cpm').classList.add('on');
    ta.focus(); ta.select();
    }

    function copyText(txt, label) {
    var ok = false;
    try {
    var ta = document.createElement('textarea');
    ta.value = txt; ta.setAttribute('readonly', '');
    ta.style.position = 'fixed'; ta.style.top = '0'; ta.style.left = '0'; ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus(); ta.select();
    ok = document.execCommand('copy');
    document.body.removeChild(ta);
    } catch (e) { ok = false; }
    if (ok) { toast(label); return; }
    if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(txt).then(function () { toast(label); }, function () { showCopyBox(txt); });
    return;
    }
    showCopyBox(txt);
    }

    function copyCell(td) {
    var r = VIEW[+td.getAttribute('data-r')], k = td.getAttribute('data-k'), c = null;
    COLS.forEach(function (x) { if (x.k === k) c = x; });
    if (!r || !c) return;
    var prev = document.querySelectorAll('.tb td.cp');
    for (var i = 0; i < prev.length; i++) prev[i].classList.remove('cp');
    td.classList.add('cp');
    var v = rawText(r, c);
    copyText(v, 'Copied: ' + (v === '' ? '(Blank)' : v));
    }

    function copyRow(td) {
    var r = VIEW[+td.getAttribute('data-r')];
    if (!r) return;
    var vc = visCols();
    copyText(vc.map(function (c) { return rawText(r, c); }).join('\t'), 'Copied 1 row');
    }

    function copyTable() {
    var vc = visCols();
    if (!vc.length || !VIEW.length) { toast('No data available to copy'); return; }
    var lines = [vc.map(function (c) { return c.h; }).join('\t')];
    for (var i = 0; i < VIEW.length; i++) {
    var r = VIEW[i];
    lines.push(vc.map(function (c) { return rawText(r, c).replace(/[\t\r\n]+/g, ' '); }).join('\t'));
    }
    copyText(lines.join('\r\n'), 'Copied ' + fmtN(VIEW.length, 0) + ' rows');
    }

    // ================= MAPPING LOGO HOLDING GROUP =================
    var HOLDING_LOGOS = {
    'MCG': 'https://i.ibb.co.com/C1HHKQS/MCG.png',
    'MBM': 'https://i.ibb.co.com/7nwFp7Z/MBMA.png',
    'MGR': 'https://i.ibb.co.com/VpCH8NKK/MGR.png'
    };

    var COMPANY_TO_HOLDING = {
    // --- HOLDING MBM ---
    'mtu': 'MBM', 'mti': 'MBM', 'merdeka tsingshan indonesia': 'MBM', 'pt merdeka tsingshan indonesia': 'MBM',
    'mtib': 'MBM', 'mtibi': 'MBM', 'ikip': 'MBM', 'csid': 'MBM', 'zhn': 'MBM', 'bsid': 'MBM', 'abp': 'MBM',
    'hnmi': 'MBM', 'sci': 'MBM', 'scm': 'MBM', 'mbm': 'MBM', 'mbma': 'MBM', 'jim': 'MBM', 'jpi': 'MBM',
    'mim': 'MBM', 'deg': 'MBM', 'gar': 'MBM', 'cbm': 'MBM', 'apk': 'MBM', 'wim': 'MBM', 'ham': 'MBM', 'tsp': 'MBM',

    // --- HOLDING MCG ---
    'b00': 'MCG', 'mcg': 'MCG', 'merdeka copper gold': 'MCG', 'pt merdeka copper gold tbk': 'MCG',
    'b02': 'MCG', 'bsi': 'MCG', 'bumi suksesindo': 'MCG', 'pt bumi suksesindo': 'MCG',
    'btr': 'MCG', 'bkp': 'MCG', 'mms': 'MCG', 'mts': 'MCG', 'motl': 'MCG', 'mosl': 'MCG',
    'sgt': 'MCG', 'alf': 'MCG', 'sjs': 'MCG', 'isc': 'MCG',

    // --- HOLDING MGR ---
    'mgr': 'MGR', 'merdeka gold resource': 'MGR', 'pt merdeka gold resource tbk': 'MGR',
    'mmn': 'MGR', 'gsm': 'MGR', 'p08': 'MGR', 'pets': 'MGR', 'p06': 'MGR', 'pbt': 'MGR',
    'p09': 'MGR', 'pbj': 'MGR', 'pin': 'MGR', 'btp': 'MGR', 'mmi': 'MGR', 'ela': 'MGR',
    'pbl': 'MGR', 'hilcon': 'MGR', 'sss': 'MGR'
    };

    function getHoldingLogoUrl(companyStr) {
    if (!companyStr) return '';
    var raw = String(companyStr).toLowerCase().trim();
    var clean = raw.replace(/^pt\s+/i, '').trim();

    var holding = COMPANY_TO_HOLDING[clean] || COMPANY_TO_HOLDING[raw];

    if (!holding) {
        var code = (COMP_NAME_TO_CODE[clean] || COMP_NAME_TO_CODE[raw] || '').toLowerCase();
        if (code) holding = COMPANY_TO_HOLDING[code];
    }

    if (!holding) {
        if (raw.indexOf('tsingshan') >= 0 || raw.indexOf('battery') >= 0 || raw.indexOf('konawe') >= 0 || raw.indexOf('smelter') >= 0 || raw.indexOf('nickel') >= 0) {
            holding = 'MBM';
        } else if (raw.indexOf('copper') >= 0 || raw.indexOf('suksesindo') >= 0 || raw.indexOf('tembaga') >= 0 || raw.indexOf('wetar') >= 0) {
            holding = 'MCG';
        } else if (raw.indexOf('gold') >= 0 || raw.indexOf('pani') >= 0 || raw.indexOf('gorontalo') >= 0 || raw.indexOf('puncak emas') >= 0) {
            holding = 'MGR';
        }
    }

    return HOLDING_LOGOS[holding] || HOLDING_LOGOS['MBM'];
    }

    function renderHeaderLogo(ks) {
    var box = el('hdLogoBox');
    if (!box) return;

    if (!ks || ks.length === 0 || ks.length > 1) {
        box.innerHTML =
            '<div class=\'hd-logos even\'>' +
                '<img src=\'https://i.ibb.co.com/C1HHKQS/MCG.png\' title=\'MCG\' />' +
                '<img src=\'https://i.ibb.co.com/7nwFp7Z/MBMA.png\' title=\'MBM\' />' +
                '<img src=\'https://i.ibb.co.com/VpCH8NKK/MGR.png\' title=\'MGR\' />' +
            '</div>';
    } else {
        var singleName = ks[0];
        var imgUrl = getHoldingLogoUrl(singleName);
        box.innerHTML =
            '<div class=\'hd-logos\'>' +
                '<img src=\'' + imgUrl + '\' title=\'' + esc(singleName) + '\' />' +
            '</div>';
    }
    }

    function shadeHex(hex, f) {
    var h = String(hex).replace('#', '').trim();
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    if (!/^[0-9a-fA-F]{6}$/.test(h)) return null;
    var n = parseInt(h, 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    function c(x) { return Math.round(f < 0 ? x * (1 + f) : x + (255 - x) * f); }
    return 'rgb(' + c(r) + ',' + c(g) + ',' + c(b) + ')';
    }

    function setHeaderColor(ks) {
    var hd = document.querySelector('.hd');
    if (!hd) return;
    var col = null;
    for (var i = 0; i < ks.length; i++) {
        var c = COMP_COLOR[ks[i]];
        if (!c || (col && c.toLowerCase() !== col.toLowerCase())) { col = null; break; }
        col = c;
    }
    var dark = col ? shadeHex(col, -0.35) : null, light = col ? shadeHex(col, 0.15) : null;
    if (dark && light) { hd.style.setProperty('--hd1', dark); hd.style.setProperty('--hd2', light); }
    else { hd.style.removeProperty('--hd1'); hd.style.removeProperty('--hd2'); }
    }

    function renderHeader() {
    var sel = FS.sbCompany;
    var isAll = (!sel || !sel.n || (TOTAL_MASTER_COMP > 0 && sel.n >= TOTAL_MASTER_COMP));
    var t = 'All Companies', ks = [];

    if (!isAll && sel && sel.n) {
        ks = Object.keys(sel.v);
        t = ks.length === 1 ? ks[0] : (ks.length === 2 ? ks.join(', ') : ks.length + ' Companies');
        el('hdEntity').title = ks.join(', ');
    } else {
        el('hdEntity').title = t;
    }

    el('hdEntity').textContent = t;
    setHeaderColor(ks);
    renderHeaderLogo(ks);
    }

    function applyFilters() { refreshSlicers(); buildView(); renderTable(); renderHeader(); }
    function refreshTable() { buildView(); renderTable(); renderHeader(); }

    function resetFilters() {
    FS = {}; DSEL = { y: 0, m: 0, d: 0 }; cachedDate = null; setTodayBtn(false);
    SLICERS.forEach(function (s) { var inp = el(s.id).querySelector('.ms-search'); if (inp) inp.value = ''; });
    QRY = ''; el('tbSearch').value = ''; SORT = { k: '', dir: 1 }; HIDE = Object.create(null); PAGE = 1;
    PSIZE = 999999; el('tbSize').value = '999999';
    closeAll(); renderColChooser();
    renderDate(); applyFilters();
    }

    function init() {
    if (INITED) return;
    INITED = true;

    parseData();
    buildSlicers();
    applyPbiFilters();

    // Default: Year / Month / Day = All, Today = Off, Rows = All
    DSEL = { y: 0, m: 0, d: 0 };
    setTodayBtn(false);
    PSIZE = 999999; el('tbSize').value = '999999';

    renderDate();
    renderColChooser();

    var sT = null;
    document.onclick = function (e) {
        var t = e.target;
        if (!t || !t.closest) return;
        var b = t.closest('.ms-btn'); if (b) { msToggleOpen(b.getAttribute('data-sl')); return; }
        var c = t.closest('.ms-clear'); if (c) { clearSlicer(c.getAttribute('data-sl')); return; }
        var o = t.closest('.ms-opt[data-sl]'); if (o) { toggleOpt(o.getAttribute('data-sl'), +o.getAttribute('data-i')); return; }
        if (t.closest('#ccBtn')) { var box = el('ccBox'); if (MS_OPEN) msToggleOpen(MS_OPEN); box.classList.toggle('open'); return; }
        var co = t.closest('.ms-opt[data-cc]');
        if (co) { var k = co.getAttribute('data-cc'); if (HIDE[k]) delete HIDE[k]; else HIDE[k] = 1; renderColChooser(); refreshTable(); return; }
        if (t.closest('#ccAll')) { HIDE = Object.create(null); renderColChooser(); refreshTable(); return; }
        if (t.closest('#ccNone')) { COLS.forEach(function (x) { HIDE[x.k] = 1; }); renderColChooser(); refreshTable(); return; }
        if (t.closest('#btnCopyTbl')) { copyTable(); return; }
        if (t.closest('#cpmX') || t.id === 'cpm') { el('cpm').classList.remove('on'); return; }
        var th = t.closest('.tb th');
        if (th) { var sk = th.getAttribute('data-k'); if (!sk) return; if (SORT.k === sk) { if (SORT.dir > 0) SORT.dir = -1; else SORT = { k: '', dir: 1 }; } else SORT = { k: sk, dir: 1 }; refreshTable(); return; }
        var td = t.closest('.tb tbody td[data-k]');
        if (td) { if (e.ctrlKey || e.metaKey) copyRow(td); else copyCell(td); return; }
        var pg = t.closest('.pg button');
        if (pg && !pg.disabled) { PAGE = +pg.getAttribute('data-p'); renderTable(); el('tbWrap').scrollTop = 0; return; }
        if (!t.closest('.ms') && !t.closest('.cc')) closeAll();
    };

    document.oninput = function (e) {
        var t = e.target;
        if (!t) return;
        if (t.classList && t.classList.contains('ms-search')) { var s = getSl(t.getAttribute('data-sl')); if (s) renderOpts(s); return; }
        if (t.id === 'tbSearch') { clearTimeout(sT); sT = setTimeout(function () { QRY = t.value.trim(); PAGE = 1; refreshTable(); }, 250); }
    };

    ['sbYr', 'sbMo', 'sbDy'].forEach(function (id) { el(id).onchange = onDateChange; });
    el('tbSize').onchange = function () { PSIZE = +this.value || 25; PAGE = 1; renderTable(); };
    el('btnToday').onclick = toggleToday;
    el('btnReset').onclick = resetFilters;

    applyFilters();
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
