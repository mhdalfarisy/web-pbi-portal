/* Dashboard Picking Slip: JavaScript dari measure dax_picking_slip_summary_v9 (Summary) dan
   dax_picking_slip_detail_header_v5 (Detail). Data dari queries.py lewat window.PICKING_SLIP (di measure: literal
   teks dari DAX). Logo i.ibb.co -> i.ibb.co.com sama dengan core.common.fix_logo_url. */
(function () {
    var P = window.PICKING_SLIP || {};

    /* Halaman aktif untuk AI agent */
    var title = P.page === 'detail' ? 'Picking Slip Detail' : 'Picking Slip Summary';
    window.DashContext = function () { return 'Page ' + title + '; filters on page: see dashboard'; };
    window.DashFilters = function () { return { page: title }; };

    if (P.page === 'summary') { summaryPage(P); }
    if (P.page === 'detail') { detailPage(P); }

    /* ======================================================= Halaman Summary */
    function summaryPage(PS) {
        // ================= DATA FROM DAX =================
        var RAW_TXT  = PS.jsRaw;
        var COMP_TXT = PS.jsComp;
        var PROJ_TXT = PS.jsProj;
        var ITEM_TXT = PS.jsItems;
        var STAT_TXT = PS.jsStat;
        var TER_TXT  = PS.jsTer;
        var PBI_FILTERS_TXT = PS.jsPbiFilters;
        var TOTAL_MASTER_COMP = PS.totalMasterCompCount;

        // Pemisah field / baris (sama dengan UNICHAR 57344 / 57345 di DAX)
        var SF = '\uE000', SR = '\uE001';

        var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

        var STATUS = [
            { key: 'ready',  label: 'Ready for Picking', color: '#10b981', match: ['ready for picking', 'c/n ready. for picking', 'transfer rdy to pick'] },
            { key: 'inprog', label: 'In Progress',       color: '#f59e0b', match: ['picking slip printed', 'assem. pick slip prt', 'c/n ready to print'] },
            { key: 'finish', label: 'Finished',          color: '#0ea5e9', match: ['finished', 'complete', 'completed', 'invoiced'] },
            { key: 'back',   label: 'Backorder',         color: '#8b5cf6', match: ['backorder', 'transfer backorder'] }
        ];
        var OTHER = { key: 'other', label: 'Others', color: '#94a3b8' };

        var SLICERS = [
            { id: 'sbCompany',  key: 'c',   label: 'All Companies' },
            { id: 'sbWoCode',   key: 'wc',  label: 'All WO Codes' },
            { id: 'sbPsNum',    key: 'psn', label: 'All PS Numbers' },
            { id: 'sbPsItem',   key: 'psi', label: 'All PS Items' },
            { id: 'sbPsStat',   key: 'pss', label: 'All PS Statuses' },
            { id: 'sbUnitDesc', key: 'u',   label: 'All Units' },
            { id: 'sbWh',       key: 'w',   label: 'All Warehouses' },
            { id: 'sbTer',      key: 't',   label: 'All Territories' },
            { id: 'sbPsDesc',   key: 'psd', label: 'All PS Desc' },
            { id: 'sbWoDesc',   key: 'wod', label: 'All WO Desc' }
        ];

        var DATA = [];
        var FS = {};
        // Default: Year / Month / Day = All, Today = Off (user yang menyalakan)
        var DSEL = { y: 0, m: 0, d: 0 };
        var todayOn = false, cachedDate = null, MS_OPEN = '', MODE = 'amt', INITED = false;
        var DAY = 864e5, WEEK = 7 * DAY;

        function el(id) { return document.getElementById(id); }
        function esc(s) {
            return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/'/g, '&#39;').replace(/\x22/g, '&quot;');
        }
        function fmt(n) { return Number(n || 0).toLocaleString('en-US', { maximumFractionDigits: 0 }); }

        function fmtShort(n) {
            n = Number(n) || 0;
            var inThousand = n / 1e3;
            return (Math.round(inThousand * 10) / 10).toLocaleString('en-US', {
                minimumFractionDigits: 1,
                maximumFractionDigits: 1
            }) + ' K';
        }
        // Angka penuh 0.000.000 untuk tooltip / pop up (tanpa K)
        function fmtFull(n) { n = Math.round(Number(n) || 0); return (n < 0 ? '-' : '') + String(Math.abs(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }
        function fmtVal(n) { return MODE === 'amt' ? fmtShort(n) : fmt(n); }
        function fmtDM(t) { var d = new Date(t); return d.getUTCDate() + ' ' + MON[d.getUTCMonth()]; }
        function niceMax(v) {
            if (!(v > 0)) return 1;
            var e = Math.pow(10, Math.floor(Math.log(v) / Math.LN10));
            var f = v / e;
            var n = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
            return n * e;
        }

        var ST_MAP = Object.create(null);
        STATUS.forEach(function (s) { s.match.forEach(function (m) { ST_MAP[m] = s.key; }); });
        function statusKey(v) { var s = String(v || '').toLowerCase().replace(/\s+/g, ' ').trim(); return ST_MAP[s] || 'other'; }
        function allStatus() { return STATUS.concat([OTHER]); }
        function visibleStatus(res) { return allStatus().filter(function (s) { return s.key !== 'other' || res.st.other.v > 0; }); }

        function Agg() { this.v = 0; this.s = null; }
        Agg.prototype.add = function (r) {
            if (MODE === 'amt') { this.v += r.amt; return; }
            if (!this.s) this.s = Object.create(null);
            var k = r.c + '|' + r.psn;
            if (!(k in this.s)) { this.s[k] = 1; this.v++; }
        };
        function newSt() { var o = {}; allStatus().forEach(function (s) { o[s.key] = new Agg(); }); return o; }

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
            var comp = dict(COMP_TXT, 2), proj = dict(PROJ_TXT, 2), names = dict(ITEM_TXT, 1), stat = dict(STAT_TXT, 1), ter = dict(TER_TXT, 1);
            for (var cc in comp) {
                var cName = comp[cc][0], cColor = comp[cc][1];
                if (cColor) COMP_COLOR[cName] = cColor;
                COMP_NAME_TO_CODE[cName.toLowerCase()] = cc;
                COMP_NAME_TO_CODE[cc.toLowerCase()] = cc;
            }
            if (!RAW_TXT) return;
            var rows = RAW_TXT.split(SR);
            // Field: 0 company | 1 PS number | 2 stock code | 3 status code | 4 unit | 5 warehouse | 6 department | 7 amount | 8 date | 9 count
            for (var i = 0; i < rows.length; i++) {
                var p = rows[i].split(SF);
                if (p.length < 10) continue;
                var dt = parseInt(p[8], 10) || 0;
                var pj = proj[p[0] + '|' + p[1]] || ['', ''];
                var cat = stat[p[3]] != null ? stat[p[3]] : p[3];
                var dept = p[6];
                DATA.push({
                    c: comp[p[0]] ? comp[p[0]][0] : p[0], wc: pj[0], psn: p[1], psi: p[2], pss: cat, u: p[4], w: p[5],
                    t: ter[dept.substr(6, 2)] || '', psd: dept, wod: pj[1],
                    inm: names[p[2]] || '',
                    amt: parseFloat(p[7]) || 0,
                    cnt: parseFloat(p[9]) || 0,
                    y: Math.floor(dt / 10000), m: Math.floor(dt / 100) % 100, d: dt % 100,
                    st: statusKey(cat)
                });
            }
        }

        function getSl(id) { for (var i = 0; i < SLICERS.length; i++) { if (SLICERS[i].id === id) return SLICERS[i]; } return null; }
        function selOf(id) { return FS[id] || (FS[id] = { v: Object.create(null), n: 0 }); }

        function uniq(key) {
            var seen = Object.create(null), out = [];
            for (var i = 0; i < DATA.length; i++) { var v = DATA[i][key]; if (!(v in seen)) { seen[v] = 1; out.push(v); } }
            out.sort(function (a, b) { return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' }); });
            return out;
        }

        function buildSlicers() {
            SLICERS.forEach(function (s) {
                s.opts = uniq(s.key);
                s.counts = Object.create(null);
                for (var d = 0; d < DATA.length; d++) {
                    var val = DATA[d][s.key];
                    s.counts[val] = (s.counts[val] || 0) + 1;
                }

                var box = el(s.id);
                if (!box) return;
                box.innerHTML =
                    '<button type=\'button\' class=\'ms-btn\' data-sl=\'' + s.id + '\'></button>' +
                    '<div class=\'ms-panel\'>' +
                        '<div class=\'ms-tools\'><input type=\'text\' class=\'ms-search\' data-sl=\'' + s.id + '\' placeholder=\'Search...\'>' +
                        '<button type=\'button\' class=\'ms-clear\' data-sl=\'' + s.id + '\'>Clear</button></div>' +
                        '<div class=\'ms-list\'></div>' +
                    '</div>';
                renderOpts(s);
                updateBtn(s);
            });
        }

        // ================= SINKRONISASI FILTER POWER BI KE SLICER =================
        function applyPbiFilters() {
            if (!PBI_FILTERS_TXT) return;
            var comp = dict(COMP_TXT, 2);
            var entries = PBI_FILTERS_TXT.split(SR);
            entries.forEach(function (ent) {
                var parts = ent.split(SF);
                if (parts.length < 2) return;
                var key = parts[0], rawVals = parts[1].split(';');

                var targetKey = (key === 'cn_raw') ? 'c' : key;
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

                renderOpts(targetSlicer);
                updateBtn(targetSlicer);
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
                     '<span class=\'ms-cnt\'>(' + fmt(cnt) + ')</span></div>';
            }
            if (!total) h = '<div class=\'ms-note\'>No results found</div>';
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

        function toggleOpt(id, i) {
            var s = getSl(id);
            if (!s) return;
            var v = s.opts[i], sel = selOf(id);
            if (v in sel.v) { delete sel.v[v]; sel.n--; } else { sel.v[v] = 1; sel.n++; }
            renderOpts(s); updateBtn(s); applyFilters();
        }

        function clearSlicer(id) {
            FS[id] = { v: Object.create(null), n: 0 };
            var s = getSl(id);
            if (s) { renderOpts(s); updateBtn(s); }
            applyFilters();
        }

        function msToggleOpen(id) {
            MS_OPEN = (MS_OPEN === id) ? '' : id;
            SLICERS.forEach(function (s) { var b = el(s.id); if (b) b.classList.toggle('open', s.id === MS_OPEN); });
            if (MS_OPEN) { var inp = el(MS_OPEN).querySelector('.ms-search'); if (inp) inp.focus(); }
        }

        function passSlicers(r) {
            for (var k = 0; k < SLICERS.length; k++) {
                var s = SLICERS[k], sel = FS[s.id];
                if (sel && sel.n && !(r[s.key] in sel.v)) return false;
            }
            return true;
        }

        function daysIn(y, m) { if (!m) return 31; return new Date(Date.UTC(y || 2000, m, 0)).getUTCDate(); }

        function fillSel(id, items, cur) {
            var s = el(id);
            if (!s) return;
            var h = '';
            items.forEach(function (it) {
                h += '<option value=\'' + it[0] + '\'' + (String(it[0]) === String(cur) ? ' selected' : '') + '>' + esc(it[1]) + '</option>';
            });
            s.innerHTML = h;
            s.classList.toggle('is-active', +cur > 0 && !todayOn);
        }

        function renderDate() {
            var years = [], seen = {};
            DATA.forEach(function (r) { if (r.y && !seen[r.y]) { seen[r.y] = 1; years.push(r.y); } });
            if (DSEL.y && !seen[DSEL.y]) years.push(DSEL.y);
            years.sort(function (a, b) { return b - a; });
            var nd = daysIn(DSEL.y, DSEL.m);
            if (DSEL.d > nd) DSEL.d = 0;
            fillSel('sbYr', [[0, 'All']].concat(years.map(function (y) { return [y, y]; })), DSEL.y);
            fillSel('sbMo', [[0, 'All']].concat(MON.map(function (n, i) { return [i + 1, n]; })), DSEL.m);
            var di = [[0, 'All']];
            for (var d = 1; d <= nd; d++) di.push([d, d]);
            fillSel('sbDy', di, DSEL.d);
        }

        function onDateChange() {
            if (todayOn) setTodayBtn(false);
            DSEL = { y: +el('sbYr').value || 0, m: +el('sbMo').value || 0, d: +el('sbDy').value || 0 };
            renderDate();
            applyFilters();
        }

        function setTodayBtn(on) {
            todayOn = on;
            var btn = el('btnToday');
            if (!btn) return;
            btn.classList.toggle('is-active', on);
            btn.textContent = on ? 'On' : 'Off';
        }

        function toggleToday() {
            if (todayOn) {
                setTodayBtn(false);
                DSEL = cachedDate || { y: 0, m: 0, d: 0 };
            } else {
                cachedDate = { y: DSEL.y, m: DSEL.m, d: DSEL.d };
                var n = new Date();
                DSEL = { y: n.getFullYear(), m: n.getMonth() + 1, d: n.getDate() };
                setTodayBtn(true);
            }
            renderDate();
            applyFilters();
        }

        function inPeriod(r, p) {
            if (p.y && r.y !== p.y) return false;
            if (p.m && r.m !== p.m) return false;
            if (p.d && r.d !== p.d) return false;
            return true;
        }

        function prevPeriod(p) {
            var refY = p.y, refM = p.m;
            if (!refY || !refM) {
                var n = new Date();
                refY = refY || n.getFullYear();
                refM = refM || (n.getMonth() + 1);
            }
            var m = refM - 1, y = refY;
            if (m < 1) { m = 12; y--; }
            return { y: y, m: m, d: 0, lbl: 'vs Last Month (' + MON[m - 1] + ')' };
        }

        // Label periode aktif (dipakai di subjudul grafik)
        function periodLabel() {
            if (!DSEL.y && !DSEL.m && !DSEL.d) return 'All Period';
            var parts = [];
            if (DSEL.d) parts.push(DSEL.d);
            if (DSEL.m) parts.push(MON[DSEL.m - 1]);
            parts.push(DSEL.y ? DSEL.y : 'All Years');
            return parts.join(' ');
        }

        var CHART_STATUS = [
            ['Picking Slip printed',   '#f59e0b'],
            ['Backorder',              '#8b5cf6'],
            ['Ready for Picking',      '#10b981'],
            ['On Hold',                '#ef4444'],
            ['Rdy to Print Invoice',   '#0ea5e9'],
            ['Transfer backorder',     '#c4b5fd'],
            ['Transfer Pick Slip P',   '#fcd34d'],
            ['Entered',                '#64748b'],
            ['Credit Hold Entered',    '#b91c1c'],
            ['Transfer rdy to pick',   '#6ee7b7'],
            ['Quotation',              '#cbd5e1'],
            ['Being Entered',          '#334155'],
            ['C/N Ready to Print',     '#fb923c'],
            ['Finished',               '#1d4ed8'],
            ['Ready to Update',        '#38bdf8'],
            ['C/N Ready to Update',    '#7dd3fc'],
            ['Transfer Entered',       '#14b8a6'],
            ['Being Purchased',        '#ec4899'],
            ['Credit Note on Hold',    '#fca5a5'],
            ['Assem. Pick Slip Prt',   '#b45309'],
            ['Credit Note Entered',    '#a8a29e'],
            ['C/N ready. for picking', '#047857'],
            ['RMA in Progress',        '#9d174d']
        ];
        var EXTRA_COLORS = ['#0f766e', '#7c3aed', '#a16207', '#4d7c0f', '#be123c', '#0369a1'];
        function normSt(v) { return String(v == null ? '' : v).toLowerCase().replace(/\s+/g, ' ').trim(); }
        var CS_KNOWN = Object.create(null);
        CHART_STATUS.forEach(function (s) { CS_KNOWN[normSt(s[0])] = 1; });

        function chartList(res) {
            var out = CHART_STATUS.map(function (s) { return { key: normSt(s[0]), label: s[0], color: s[1] }; });
            var ex = 0;
            for (var k in res.rs) {
                if (CS_KNOWN[k]) continue;
                out.push({ key: k, label: res.rsLabel[k] || '(Blank)', color: EXTRA_COLORS[ex++ % EXTRA_COLORS.length] });
            }
            return out;
        }
        function rsVal(map, k) { return map[k] ? map[k].v : 0; }
        function rsAdd(map, r) { (map[r.csk] || (map[r.csk] = new Agg())).add(r); }

        function inPeriodKpi(r, p) {
            if (p.y && r.y !== p.y) return false;
            if (p.m && r.m !== p.m) return false;
            if (p.d && r.d > p.d) return false;
            return true;
        }

        function compute(p, full, isKpi) {
            var res = { tot: new Agg(), st: newSt(), rs: Object.create(null), rsLabel: Object.create(null), items: Object.create(null), base: [], maxKey: 0 };
            for (var i = 0; i < DATA.length; i++) {
                var r = DATA[i];
                if (!passSlicers(r)) continue;
                if (r.csk === undefined) r.csk = normSt(r.pss);
                if (full) res.base.push(r);

                var matchDate = isKpi ? inPeriodKpi(r, p) : inPeriod(r, p);
                if (!matchDate) continue;

                res.tot.add(r);
                res.st[r.st].add(r);
                if (full) {
                    rsAdd(res.rs, r);
                    if (!(r.csk in res.rsLabel)) res.rsLabel[r.csk] = r.pss;
                    var it = res.items[r.psi];
                    if (!it) it = res.items[r.psi] = { name: r.inm, a: new Agg() };
                    if (!it.name && r.inm) it.name = r.inm;
                    it.a.add(r);
                    if (r.d) { var dk = r.y * 10000 + r.m * 100 + r.d; if (dk > res.maxKey) res.maxKey = dk; }
                }
            }
            return res;
        }

        function applyFilters() {
            var cur = compute(DSEL, true, false);
            var curKpi = compute(DSEL, false, true);
            var pp = prevPeriod(DSEL);
            var prev = pp ? compute(pp, false, false) : null;

            renderKpi(curKpi, prev, pp);
            renderTrend(cur);
            renderDonut(cur);
            renderTop5(cur);
            renderBars(cur);
            renderHeader();
        }

        function setKpi(key, label, cv, pv, pp, inv) {
            var n = el('kpi-n-' + key); if (n) n.textContent = label;
            var v = el('kpi-v-' + key); if (v) { v.textContent = fmtVal(cv); v.title = fmtFull(cv); }
            var t = el('kpi-t-' + key), vs = el('kpi-vs-' + key);
            if (!t) return;
            var dir = 'flat', tone = 'flat', txt = '-', note = 'Select Year & Month to compare';
            if (pp) {
                var prevValStr = fmtVal(pv);
                note = pp.lbl + ': ' + prevValStr;

                if (pv > 0) {
                    var ch = (cv - pv) / pv * 100;
                    txt = (ch >= 0 ? '+' : '') + ch.toFixed(1) + '%';
                    if (ch !== 0) { dir = ch > 0 ? 'up' : 'down'; tone = (inv ? ch < 0 : ch > 0) ? 'good' : 'bad'; }
                } else {
                    txt = cv > 0 ? 'New' : '0.0%';
                }
            }
            t.className = 'kpi-trend ' + (dir === 'flat' ? 'flat' : dir + ' ' + tone);
            t.querySelector('.txt').textContent = txt;
            if (vs) {
                vs.textContent = note;
                if (pp) vs.title = 'Full Month Total: ' + fmtFull(pv);
            }
        }

        function renderKpi(cur, prev, pp) {
            setKpi('tot', MODE === 'amt' ? 'Total PS Amount' : 'Total Picking Slip', cur.tot.v, prev ? prev.tot.v : 0, pp, false);
            STATUS.forEach(function (s) {
                setKpi(s.key, s.label, cur.st[s.key].v, prev ? prev.st[s.key].v : 0, pp, s.key === 'back');
            });
        }

        // ================= CHART 1: PICKING SLIP BY STATUS (combo bar + line) =================
        // Sumbu X  = sales_order_line[dax_so_order_status_category] (semua kategori yang ada di data, termasuk amount 0 / negatif)
        // Bar      = SUM ( sales_order_line[dax_total_ps_amount] )            -> sumbu kiri
        // Line     = [dax_so_order_status_category_count]                     -> sumbu kanan
        // Mengikuti semua slicer + periode (Year / Month / Day / Today). Diurutkan dari amount terbesar.
        // ================= FORMAT ANGKA 0.000.000 (titik sebagai pemisah ribuan, tanpa K/M/B) =================
        function fmtID(n) {
            n = Math.round(Number(n) || 0);
            var neg = n < 0, s = String(Math.abs(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
            return (neg ? '-' : '') + s;
        }
        function fmtAuto(n) { return fmtID(n); }

        // Pecah label kategori menjadi beberapa baris (tanpa dipotong)
        function wrapWords(txt, maxCh) {
            var words = String(txt).split(/\s+/), lines = [], cur = '';
            words.forEach(function (w) {
                if (!cur) cur = w;
                else if ((cur + ' ' + w).length <= maxCh) cur += ' ' + w;
                else { lines.push(cur); cur = w; }
            });
            if (cur) lines.push(cur);
            return lines;
        }

        function renderTrend(res) {
            if (!window.__trRs) {
                window.__trRs = 1;
                window.addEventListener('resize', function () {
                    clearTimeout(window.__trT);
                    window.__trT = setTimeout(function () { if (window.__lastRes) renderTrend(window.__lastRes); }, 150);
                });
            }
            window.__lastRes = res;
            var box = el('tr-box'), sub = el('tr-sub'), leg = el('tr-leg');
            if (!box) return;

            var agg = Object.create(null), colorOf = Object.create(null), ex = 0;
            CHART_STATUS.forEach(function (s) { colorOf[normSt(s[0])] = s[1]; });
            res.base.forEach(function (r) {
                if (!inPeriod(r, DSEL)) return;
                var k = r.csk;
                var a = agg[k] || (agg[k] = { key: k, label: r.pss === '' ? '(Blank)' : r.pss, amt: 0, cnt: 0 });
                a.amt += r.amt; a.cnt += r.cnt;
            });
            var cats = [];
            for (var k in agg) {
                if (!colorOf[k]) colorOf[k] = EXTRA_COLORS[ex++ % EXTRA_COLORS.length];
                agg[k].color = colorOf[k];
                cats.push(agg[k]);
            }
            cats.sort(function (a, b) { return b.amt - a.amt || b.cnt - a.cnt; });

            if (!cats.length) {
                box.innerHTML = '<div class=\'empty\'>No data available for this filter</div>';
                if (sub) sub.textContent = 'No data';
                if (leg) leg.innerHTML = '';
                return;
            }

            var maxA = 0, minA = 0, maxC = 0;
            cats.forEach(function (c) { maxA = Math.max(maxA, c.amt); minA = Math.min(minA, c.amt); maxC = Math.max(maxC, c.cnt); });
            var topA = niceMax(maxA * 1.25), botA = minA < 0 ? -niceMax(-minA * 1.25) : 0;
            var topC = niceMax(maxC * 1.25);
            var N = cats.length;

            // lebar sumbu kiri menyesuaikan panjang angka terbesar (format 0.000.000)
            var yLblLen = Math.max(fmtID(topA).length, fmtID(botA).length);
            var W = Math.max(520, Math.round(box.clientWidth || 600));
            var L = 16 + yLblLen * 7, R = W - (16 + fmtID(topC).length * 7), T = 28, B = 220;
            var gw = (R - L) / N, bw = Math.max(8, Math.min(46, gw * 0.55));

            // label kategori dibungkus per kata, tidak dipotong
            var maxCh = Math.max(6, Math.floor(gw / 6.2));
            var wrapped = cats.map(function (c) { return wrapWords(c.label, maxCh); });
            var maxLines = 1;
            wrapped.forEach(function (w) { maxLines = Math.max(maxLines, w.length); });
            var H = B + 22 + maxLines * 13 + 8, ph = B - T;

            function yA(v) { return T + (topA - v) / (topA - botA) * ph; }
            function yC(v) { return T + (topC - v) / topC * ph; }
            var y0 = yA(0);

            var s = '<svg class=\'tr-svg\' viewBox=\'0 0 ' + W + ' ' + H + '\'>';
            for (var g = 0; g <= 4; g++) {
                var gy = T + ph * g / 4, va = topA - (topA - botA) * g / 4, vc = topC - topC * g / 4;
                s += '<line x1=\'' + L + '\' y1=\'' + gy + '\' x2=\'' + R + '\' y2=\'' + gy + '\' class=\'ax-line\'/>';
                s += '<text x=\'' + (L - 8) + '\' y=\'' + (gy + 4) + '\' class=\'ax-y\'>' + fmtID(va) + '</text>';
                s += '<text x=\'' + (R + 8) + '\' y=\'' + (gy + 4) + '\' class=\'ax-y\' style=\'text-anchor:start;fill:#ea580c\'>' + fmtID(vc) + '</text>';
            }
            s += '<line x1=\'' + L + '\' y1=\'' + y0 + '\' x2=\'' + R + '\' y2=\'' + y0 + '\' class=\'ax-base\'/>';

            var pts = [], amtLblY = [];
            cats.forEach(function (c, i) {
                var cx = L + gw * (i + 0.5), ya = yA(c.amt), yTop = Math.min(ya, y0), h = Math.max(1, Math.abs(ya - y0));
                var tip = fxSw(c.color) + '<b>' + esc(c.label) + '</b><br>Amount: ' + esc(fmtID(c.amt)) + '<br>Count: ' + esc(fmtID(c.cnt));
                s += '<rect class=\'fx-bar\' x=\'' + (cx - bw / 2) + '\' y=\'' + yTop + '\' width=\'' + bw + '\' height=\'' + h + '\' rx=\'3\' fill=\'' + c.color + '\'' +
                     ' data-st=\'' + esc(c.label) + '\' data-tip=\'' + esc(tip) + '\' style=\'animation-delay:' + (i * 0.04) + 's\'></rect>';
                amtLblY.push(c.amt >= 0 ? yTop - 6 : y0 - 6);
                pts.push([cx, yC(c.cnt), c]);

                // label sumbu X: multi-baris, rata tengah, utuh
                var lines = wrapped[i], ty = B + 18;
                s += '<text class=\'ax-cat\' x=\'' + cx + '\' y=\'' + ty + '\' style=\'text-anchor:middle\'><title>' + esc(c.label) + '</title>';
                lines.forEach(function (ln, j) {
                    s += '<tspan x=\'' + cx + '\' dy=\'' + (j ? 13 : 0) + '\'>' + esc(ln) + '</tspan>';
                });
                s += '</text>';
            });

            s += '<path class=\'tr-line cnt-line\' d=\'M' + pts.map(function (p) { return p[0] + ' ' + p[1]; }).join(' L') + '\'/>';

            // label amount (biru) & count (oranye): geser bila bertabrakan
            pts.forEach(function (p, i) {
                var c = p[2], aY = amtLblY[i], cY = p[1] - 9;
                // label count selalu di atas titik; bila label amount berdekatan dengan titik/label count,
                // label amount ditumpuk di atas label count sehingga tidak saling menimpa
                if (aY > p[1] - 26 && aY < p[1] + 14) aY = p[1] - 24;
                if (aY < 10) aY = 10;
                s += '<text class=\'v-lbl fx-late\' style=\'paint-order:stroke;stroke:#ffffff;stroke-width:3px\' x=\'' + p[0] + '\' y=\'' + aY + '\'>' + fmtID(c.amt) + '</text>';
                var tip = '<b>' + esc(c.label) + '</b><br>Count: ' + esc(fmtID(c.cnt)) + '<br>Amount: ' + esc(fmtID(c.amt));
                s += '<circle class=\'tr-dot cnt-dot fx-late\' cx=\'' + p[0] + '\' cy=\'' + p[1] + '\' r=\'3.5\' data-tip=\'' + esc(tip) + '\'/>';
                s += '<text class=\'c-lbl fx-late\' x=\'' + p[0] + '\' y=\'' + cY + '\'>' + fmtID(c.cnt) + '</text>';
            });
            s += '</svg>';
            box.innerHTML = s;

            if (sub) sub.textContent = 'Amount (bar) & PS line count (line) per status category · ' + periodLabel();
            if (leg) {
                leg.innerHTML = '<div class=\'leg-item\'><div class=\'leg-dot\' style=\'background:#1e3a8a;border-radius:2px\'></div>Order Amount</div>' +
                                '<div class=\'leg-item\'><div class=\'leg-line\' style=\'background:#ea580c\'></div>Status Category Count</div>';
            }
        }

        function renderDonut(res) {
            var segs = chartList(res), sum = 0, acc = 0, g = [], lh = '';
            segs.forEach(function (s) { sum += Math.max(0, rsVal(res.rs, s.key)); });
            segs.forEach(function (s) {
                var v = rsVal(res.rs, s.key), p = sum && v > 0 ? v / sum * 100 : 0;
                if (p > 0) { g.push(s.color + ' ' + acc + '% ' + (acc + p) + '%'); acc += p; }
                lh += '<div class=\'d-leg-item' + (v ? '' : ' zero') + '\'><div class=\'d-dot\' style=\'background:' + s.color + '\'></div>' +
                      '<div class=\'d-lbl\' title=\'' + esc(s.label) + '\'>' + esc(s.label) + '</div>' +
                      '<div class=\'d-val\' data-full=\'' + fmtFull(v) + '\' title=\'' + fmtFull(v) + '\'>' + fmtVal(v) + '</div>' +
                      '<div class=\'d-pct\'>' + p.toFixed(1) + '%</div></div>';
            });
            var ch = el('dn-chart');
            if (ch) ch.style.background = g.length ? 'conic-gradient(' + g.join(',') + ')' : '#e2e8f0';
            if (el('dn-cap')) el('dn-cap').textContent = MODE === 'amt' ? 'Total Amount' : 'Total PS';
            if (el('dn-tot')) {
                var dt = el('dn-tot');
                dt.textContent = fmtVal(res.tot.v); dt.title = fmtFull(res.tot.v);
                // kecilkan font otomatis supaya angka tetap di dalam lubang donut
                var fs = 13; dt.style.fontSize = fs + 'px';
                while (dt.scrollWidth > 86 && fs > 8) { fs -= 0.5; dt.style.fontSize = fs + 'px'; }
            }
            if (el('dn-leg')) el('dn-leg').innerHTML = lh;
        }

        function renderTop5(res) {
            var arr = [];
            for (var c in res.items) arr.push({ c: c, n: res.items[c].name, a: res.items[c].a.v });
            arr.sort(function (a, b) { return b.a - a.a; });
            var mx = arr.length ? arr[0].a : 0;
            var h = '<colgroup><col style=\'width:34px\'><col style=\'width:22%\'><col><col style=\'width:22%\'><col style=\'width:100px\'></colgroup>' +
                    '<tr><th>No</th><th>Item Code</th><th>Item Name</th><th></th><th class=\'r\'>' + (MODE === 'amt' ? 'Amount' : 'PS Count') + '</th></tr>';
            for (var i = 0; i < 5; i++) {
                if (i < arr.length) {
                    var it = arr[i], pct = mx > 0 ? Math.max(0, it.a / mx * 100) : 0;
                    h += '<tr><td>' + (i + 1) + '</td><td title=\'' + esc(it.c) + '\'>' + esc(it.c || '(Blank)') + '</td>' +
                         '<td title=\'' + esc(it.n) + '\'>' + esc(it.n || '-') + '</td>' +
                         '<td><div class=\'t-bar-wrap\'><div class=\'t-bar\' style=\'width:' + pct + '%\'></div></div></td>' +
                         '<td class=\'r\' title=\'' + fmtFull(it.a) + '\'>' + fmtVal(it.a) + '</td></tr>';
                } else {
                    h += '<tr><td>' + (i + 1) + '</td><td>-</td><td>-</td><td></td><td class=\'r\'>-</td></tr>';
                }
            }
            if (el('t5-table')) el('t5-table').innerHTML = h;
            if (el('t5-sub')) el('t5-sub').textContent = 'Top items by ' + (MODE === 'amt' ? 'highest amount' : 'highest PS count');
        }

        function renderBars(res) {
            var box = el('bc-box');
            if (!box) return;
            var segs = chartList(res).map(function (s) { s.v = rsVal(res.rs, s.key); return s; });
            segs.sort(function (a, b) { return b.v - a.v; });
            var mx = 0;
            segs.forEach(function (s) { mx = Math.max(mx, s.v); });
            var h = '';
            segs.forEach(function (s) {
                var w = mx > 0 && s.v > 0 ? s.v / mx * 100 : 0;
                h += '<div class=\'hb-row' + (s.v ? '' : ' zero') + '\' title=\'' + esc(s.label + ': ' + Math.round(s.v)) + '\'>' +
                     '<div class=\'hb-lbl\'>' + esc(s.label) + '</div>' +
                     '<div class=\'hb-track\'><div class=\'hb-bar\' style=\'width:' + w + '%;background:' + s.color + '\'></div></div>' +
                     '<div class=\'hb-val\'>' + fmtVal(s.v) + '</div></div>';
            });
            box.className = 'hb-wrap';
            box.innerHTML = h;
        }

        // ================= RENDER LOGO & HEADER DINAMIS =================
        // ================= MAPPING LOGO HOLDING =================
        var HOLDING_LOGOS = {
            'MCG': 'https://i.ibb.co.com/C1HHKQS/MCG.png',
            'MBM': 'https://i.ibb.co.com/7nwFp7Z/MBMA.png',
            'MGR': 'https://i.ibb.co.com/VpCH8NKK/MGR.png'
        };

        // Mapping Kode / Nama Perusahaan ke Grup Holding
        var COMPANY_TO_HOLDING = {
            // --- HOLDING MBM ---
            'mtu': 'MBM',
            'mti': 'MBM',
            'merdeka tsingshan indonesia': 'MBM',
            'pt merdeka tsingshan indonesia': 'MBM',
            'mtib': 'MBM',
            'mtibi': 'MBM',
            'ikip': 'MBM',
            'csid': 'MBM',
            'zhn': 'MBM',
            'bsid': 'MBM',
            'abp': 'MBM',
            'hnmi': 'MBM',
            'sci': 'MBM',
            'scm': 'MBM',
            'mbm': 'MBM',
            'mbma': 'MBM',
            'jim': 'MBM',
            'jpi': 'MBM',
            'mim': 'MBM',
            'deg': 'MBM',
            'gar': 'MBM',
            'cbm': 'MBM',
            'apk': 'MBM',
            'wim': 'MBM',
            'ham': 'MBM',
            'tsp': 'MBM',

            // --- HOLDING MCG ---
            'b00': 'MCG',
            'mcg': 'MCG',
            'merdeka copper gold': 'MCG',
            'pt merdeka copper gold tbk': 'MCG',
            'b02': 'MCG',
            'bsi': 'MCG',
            'bumi suksesindo': 'MCG',
            'pt bumi suksesindo': 'MCG',
            'btr': 'MCG',
            'bkp': 'MCG',
            'mms': 'MCG',
            'mts': 'MCG',
            'motl': 'MCG',
            'mosl': 'MCG',
            'sgt': 'MCG',
            'alf': 'MCG',
            'sjs': 'MCG',
            'isc': 'MCG',

            // --- HOLDING MGR ---
            'mgr': 'MGR',
            'merdeka gold resource': 'MGR',
            'pt merdeka gold resource tbk': 'MGR',
            'mmn': 'MGR',
            'gsm': 'MGR',
            'p08': 'MGR',
            'pets': 'MGR',
            'p06': 'MGR',
            'pbt': 'MGR',
            'p09': 'MGR',
            'pbj': 'MGR',
            'pin': 'MGR',
            'btp': 'MGR',
            'mmi': 'MGR',
            'ela': 'MGR',
            'pbl': 'MGR',
            'hilcon': 'MGR',
            'sss': 'MGR'
        };

        function getHoldingLogoUrl(companyStr) {
            if (!companyStr) return '';
            var raw = String(companyStr).toLowerCase().trim();
            var clean = raw.replace(/^pt\s+/i, '').trim();

            // 1. Cek langsung dari nama perusahaan
            var holding = COMPANY_TO_HOLDING[clean] || COMPANY_TO_HOLDING[raw];

            // 2. Jika belum cocok, cari berdasarkan kode perusahaan dari master
            if (!holding) {
                var code = (COMP_NAME_TO_CODE[clean] || COMP_NAME_TO_CODE[raw] || '').toLowerCase();
                if (code) holding = COMPANY_TO_HOLDING[code];
            }

            // 3. Pencocokan parsial kata kunci nama anak perusahaan
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

            // Jika tidak ada filter atau lebih dari 1 company terpilih, tampilkan 3 holding logo
            if (!ks || ks.length === 0 || ks.length > 1) {
                box.innerHTML =
                    '<div class=\'hd-logos even\'>' +
                        '<img src=\'https://i.ibb.co.com/C1HHKQS/MCG.png\' title=\'MCG\' />' +
                        '<img src=\'https://i.ibb.co.com/7nwFp7Z/MBMA.png\' title=\'MBM\' />' +
                        '<img src=\'https://i.ibb.co.com/VpCH8NKK/MGR.png\' title=\'MGR\' />' +
                    '</div>';
            } else {
                // Tepat 1 company dipilih: ambil logo group holding-nya
                var singleName = ks[0];
                var imgUrl = getHoldingLogoUrl(singleName);

                box.innerHTML =
                    '<div class=\'hd-logos\'>' +
                        '<img src=\'' + imgUrl + '\' title=\'' + esc(singleName) + '\' />' +
                    '</div>';
            }
        }

        function renderHeader() {
            var e = el('hdEntity');
            if (!e) return;
            var sel = FS.sbCompany;

            var isAll = (!sel || !sel.n || (TOTAL_MASTER_COMP > 0 && sel.n >= TOTAL_MASTER_COMP));
            var t = 'All Companies', ks = [];

            if (!isAll && sel && sel.n) {
                ks = Object.keys(sel.v);
                t = ks.length === 1 ? ks[0] : (ks.length === 2 ? ks.join(', ') : ks.length + ' Companies');
                e.title = ks.join(', ');
            } else {
                e.title = t;
            }

            e.textContent = t;
            setHeaderColor(ks);
            renderHeaderLogo(ks);
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

        function setMode(m) {
            MODE = m;
            el('btnModeAmt').classList.toggle('is-active', m === 'amt');
            el('btnModeCnt').classList.toggle('is-active', m === 'cnt');
            applyFilters();
        }

        function resetFilters() {
            FS = {};
            SLICERS.forEach(function (s) {
                var box = el(s.id), inp = box && box.querySelector('.ms-search');
                if (inp) inp.value = '';
                renderOpts(s); updateBtn(s);
            });
            DSEL = { y: 0, m: 0, d: 0 };
            cachedDate = null;
            setTodayBtn(false);
            renderDate();
            applyFilters();
        }

        function fxTip() {
            var t = el('fxTip');
            if (!t) { t = document.createElement('div'); t.id = 'fxTip'; document.body.appendChild(t); }
            return t;
        }
        function fxShow(html, e) {
            var t = fxTip();
            t.innerHTML = html;
            t.classList.add('on');
            var x = e.clientX + 14, y = e.clientY + 14, w = t.offsetWidth, h = t.offsetHeight;
            if (x + w > window.innerWidth - 8) x = e.clientX - w - 14;
            if (y + h > window.innerHeight - 8) y = e.clientY - h - 14;
            t.style.left = Math.max(4, x) + 'px'; t.style.top = Math.max(4, y) + 'px';
        }
        function fxHide() { var t = el('fxTip'); if (t) t.classList.remove('on'); }
        function fxSw(c) { return '<span class=\'sw\' style=\'background:' + c + '\'></span>'; }
        function fxNum(s) { var n = +String(s).replace(/,/g, ''); if (s === '' || isNaN(n)) return esc(s); return esc(fmtFull(n)); }

        function fxCount(node) {
            var target = node.textContent, m = /^(-?[\d,]*\.?\d+)(\s*[KMB]|\s*Million)?$/.exec(target);
            var prev = node.getAttribute('data-prev'); node.setAttribute('data-prev', target);
            if (!m || prev === target) return;
            var to = parseFloat(m[1].replace(/,/g, '')), suf = m[2] || '', dec = (m[1].split('.')[1] || '').length;
            var pm = prev ? /^(-?[\d,]*\.?\d+)(\s*[KMB]|\s*Million)?$/.exec(prev) : null;
            var from = pm && (pm[2] || '') === suf ? parseFloat(pm[1].replace(/,/g, '')) : 0;
            var t0 = null, dur = 600;
            function step(ts) {
                if (!t0) t0 = ts;
                var k = Math.min(1, (ts - t0) / dur), e = 1 - Math.pow(1 - k, 3), v = from + (to - from) * e;
                node.textContent = (k < 1 ? v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + suf : target);
                if (k < 1) requestAnimationFrame(step);
            }
            requestAnimationFrame(step);
        }

        function fxBars(sel) {
            var bars = document.querySelectorAll(sel), ws = [];
            for (var i = 0; i < bars.length; i++) { ws.push(bars[i].style.width); bars[i].style.width = '0%'; }
            void document.body.offsetWidth;
            requestAnimationFrame(function () { for (var j = 0; j < bars.length; j++) bars[j].style.width = ws[j]; });
        }

        // Batang & tooltip grafik status sudah dibuat langsung di renderTrend; di sini hanya efek animasi.
        function fxTrend() {
            var svg = document.querySelector('#tr-box .tr-svg');
            if (!svg) return;
            var vl = svg.querySelectorAll('text.v-lbl');
            for (var q = 0; q < vl.length; q++) vl[q].classList.add('fx-late');
        }

        var FX_DN = [];
        function fxDonut() {
            var ch = el('dn-chart');
            if (ch) { ch.classList.remove('fx-in'); void ch.offsetWidth; ch.classList.add('fx-in'); }
            FX_DN = []; var acc = 0;
            var items = document.querySelectorAll('#dn-leg .d-leg-item');
            for (var i = 0; i < items.length; i++) {
                var it = items[i], pct = parseFloat((it.querySelector('.d-pct') || {}).textContent) || 0;
                var lbl = (it.querySelector('.d-lbl') || {}).textContent || '', dv = it.querySelector('.d-val'), val = dv ? (dv.getAttribute('data-full') || dv.textContent) : '';
                var col = (it.querySelector('.d-dot') || { style: {} }).style.background;
                it.setAttribute('data-tip', fxSw(col) + '<b>' + esc(lbl) + '</b><br>' + esc(val) + ' <span class=\'mut\'>(' + pct.toFixed(1) + '%)</span>');
                if (pct > 0) { FX_DN.push({ a: acc, b: acc + pct, el: it }); acc += pct; }
            }
        }
        function fxDonutAt(e) {
            var ch = el('dn-chart'), r = ch.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
            var dx = e.clientX - cx, dy = e.clientY - cy, d = Math.sqrt(dx * dx + dy * dy), R = r.width / 2;
            if (d > R || d < R * 0.62) return null;
            var ang = (Math.atan2(dx, -dy) * 180 / Math.PI + 360) % 360, p = ang / 3.6;
            for (var i = 0; i < FX_DN.length; i++) if (p >= FX_DN[i].a && p < FX_DN[i].b) return FX_DN[i].el;
            return null;
        }

        function fxAfter() {
            var hb = document.querySelectorAll('#bc-box .hb-row');
            for (var i = 0; i < hb.length; i++) {
                var t = hb[i].getAttribute('title');
                if (t) { hb[i].removeAttribute('title'); var p = t.lastIndexOf(': '); hb[i].setAttribute('data-tip', fxSw(hb[i].querySelector('.hb-bar').style.background) + '<b>' + esc(t.slice(0, p)) + '</b><br>' + fxNum(t.slice(p + 2))); }
            }
        }

        var _fxKpi = renderKpi, _fxTrend = renderTrend, _fxDonut = renderDonut, _fxTop5 = renderTop5, _fxBars = renderBars;
        renderKpi = function (a, b, c) { _fxKpi(a, b, c); var ks = document.querySelectorAll('.kpi-val'); for (var i = 0; i < ks.length; i++) fxCount(ks[i]); };
        renderTrend = function (res) { _fxTrend(res); fxTrend(); };
        renderDonut = function (res) { _fxDonut(res); fxDonut(); };
        renderTop5 = function (res) { _fxTop5(res); fxBars('#t5-table .t-bar'); };
        renderBars = function (res) { _fxBars(res); fxAfter(); fxBars('#bc-box .hb-bar'); };

        document.onmousemove = function (e) {
            var t = e.target;
            if (!t || !t.closest) return;
            var hl = document.querySelectorAll('.d-leg-item.fx-hl');
            for (var i = 0; i < hl.length; i++) hl[i].classList.remove('fx-hl');
            if (t.closest('#dn-chart')) {
                var seg = fxDonutAt(e);
                if (seg) { seg.classList.add('fx-hl'); fxShow(seg.getAttribute('data-tip'), e); } else fxHide();
                return;
            }
            var tipEl = t.closest('[data-tip]');
            if (tipEl) { if (tipEl.classList.contains('d-leg-item')) tipEl.classList.add('fx-hl'); fxShow(tipEl.getAttribute('data-tip'), e); }
            else fxHide();
            var svg = document.querySelector('#tr-box .tr-svg');
            if (svg) {
                var li = t.closest('#tr-leg .leg-item');
                var on = svg.querySelectorAll('rect.fx-on');
                for (var j = 0; j < on.length; j++) on[j].classList.remove('fx-on');
                if (li && !li.classList.contains('zero')) {
                    var name = li.textContent, rs = svg.querySelectorAll('rect.fx-bar');
                    svg.classList.add('fx-dim');
                    for (var k = 0; k < rs.length; k++) if (rs[k].getAttribute('data-st') === name) rs[k].classList.add('fx-on');
                } else svg.classList.remove('fx-dim');
            }
        };
        document.onmouseleave = fxHide;

        // ================= INIT =================
        function init() {
            if (INITED) return;
            INITED = true;
            parseData();
            buildSlicers();

            applyPbiFilters();

            // Default: semua periode (Year / Month / Day = All) dan tombol Today = Off
            DSEL = { y: 0, m: 0, d: 0 };
            setTodayBtn(false);

            renderDate();

            document.onclick = function (e) {
                var t = e.target;
                if (!t || !t.closest) return;
                var b = t.closest('.ms-btn'); if (b) { msToggleOpen(b.getAttribute('data-sl')); return; }
                var c = t.closest('.ms-clear'); if (c) { clearSlicer(c.getAttribute('data-sl')); return; }
                var o = t.closest('.ms-opt'); if (o) { toggleOpt(o.getAttribute('data-sl'), +o.getAttribute('data-i')); return; }
                if (MS_OPEN && !t.closest('.ms')) msToggleOpen(MS_OPEN);
            };
            document.oninput = function (e) {
                var t = e.target;
                if (t && t.classList && t.classList.contains('ms-search')) { var s = getSl(t.getAttribute('data-sl')); if (s) renderOpts(s); }
            };
            ['sbYr', 'sbMo', 'sbDy'].forEach(function (id) { el(id).addEventListener('change', onDateChange); });
            el('btnToday').addEventListener('click', toggleToday);
            el('btnReset').addEventListener('click', resetFilters);

            applyFilters();
        }

        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
        else init();
    }

    /* ======================================================= Halaman Detail */
    function detailPage(PS) {
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
    }
})();
