/* Dashboard PANI: header (logika sama dengan Material Readiness), sparkline, dan chart kombinasi bar + garis (SVG). */
window.Pani = (function () {
    'use strict';
    var P = window.PANI || {};
    var esc = Dash.esc;
    var NS = 'http://www.w3.org/2000/svg';

    function fmtN(v, d) {
        if (v === null || v === undefined || isNaN(v)) { return '-'; }
        return Number(v).toLocaleString('en-US', { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 });
    }
    function short(v) {
        var a = Math.abs(v);
        if (a >= 1e6) { return (v / 1e6).toFixed(1) + 'M'; }
        if (a >= 1e3) { return (v / 1e3).toFixed(a >= 1e4 ? 0 : 1) + 'K'; }
        return String(Math.round(v * 10) / 10);
    }
    function niceMax(v) {
        if (!(v > 0)) { return 1; }
        var p = Math.pow(10, Math.floor(Math.log(v) / Math.LN10)), f = v / p;
        return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
    }

    /* Header: logo, entity, dan warna mengikuti company data halaman ini (Dash.setHeaderCompany = Material Readiness) */
    if (P.company) { Dash.setHeaderCompany(P.company, P.logo || {}); }

    /* Filter aktif untuk AI agent: halaman + rentang tanggal */
    var page = (document.querySelector('.hd-main-title') || {}).textContent || '';
    var data = P.data || {};
    window.DashContext = function () {
        return 'Page ' + page + '; range ' + (data.start || '-') + ' to ' + (data.end || '-') + '; company ' + (P.company || '-');
    };
    window.DashFilters = function () { return { page: page, start: data.start, end: data.end }; };

    function spark(el, values, color) {
        if (!el) { return; }
        var pts = [], w = el.clientWidth || 140, h = el.clientHeight || 32;
        var vals = values.filter(function (v) { return v !== null && v !== undefined; });
        if (vals.length < 2) { el.innerHTML = ''; return; }
        var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals), rg = (mx - mn) || 1, n = values.length - 1;
        values.forEach(function (v, i) {
            if (v === null || v === undefined) { return; }
            pts.push([(i / n) * w, h - 2 - ((v - mn) / rg) * (h - 4)]);
        });
        var line = pts.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' ');
        var area = 'M' + pts[0][0].toFixed(1) + ',' + h + ' L' + line.replace(/ /g, ' L') + ' L' + pts[pts.length - 1][0].toFixed(1) + ',' + h + ' Z';
        el.innerHTML = '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '">'
            + '<path d="' + area + '" fill="' + color + '" opacity="0.12"/>'
            + '<polyline points="' + line + '" fill="none" stroke="' + color + '" stroke-width="2" stroke-linejoin="round"/></svg>';
    }

    /* cfg: {labels, bars:[{name,values,color}], lines:[{name,values,color,axis,dash}], refs:[{value,axis,color}],
             minBand, rightFmt} — sumbu kanan dipakai garis/ref dengan axis:'right' */
    function combo(el, cfg) {
        if (!el) { return; }
        var labels = cfg.labels, n = labels.length;
        if (!n) { el.innerHTML = '<div class="note" style="margin:auto">No data</div>'; return; }
        var H = el.clientHeight || 260, mT = 10, mB = 24, ph = H - mT - mB;
        var hasRight = (cfg.lines || []).concat(cfg.bars || []).some(function (l) { return l.axis === 'right'; }) || (cfg.refs || []).length;
        var axisW = 46, availW = Math.max(60, el.clientWidth - axisW - (hasRight ? axisW : 0));
        var band = Math.max(cfg.minBand || 40, availW / n), W = band * n;
        var leftVals = [], rightVals = [];
        (cfg.bars || []).forEach(function (b) {
            if (b.axis === 'right') { rightVals = rightVals.concat(b.values); } else { leftVals = leftVals.concat(b.values); }
        });
        (cfg.lines || []).forEach(function (l) { (l.axis === 'right' ? rightVals : leftVals).push.apply(l.axis === 'right' ? rightVals : leftVals, l.values); });
        (cfg.refs || []).forEach(function (r) { rightVals.push(r.value); });
        function maxOf(a) { return Math.max.apply(null, a.filter(function (v) { return v !== null && v !== undefined && !isNaN(v); }).concat([0])); }
        function minOf(a) { return Math.min.apply(null, a.filter(function (v) { return v !== null && v !== undefined && !isNaN(v); }).concat([0])); }
        var lMax = niceMax(maxOf(leftVals) * 1.08), lMin = minOf(leftVals) < 0 ? -niceMax(-minOf(leftVals) * 1.08) : 0;
        var rMax = niceMax(maxOf(rightVals) * 1.08);
        if (cfg.rightMax) { rMax = Math.min(rMax, cfg.rightMax); }  /* outlier (mis. target hampir 0) tidak menggepengkan garis */
        function yL(v) { return mT + ph - ((v - lMin) / (lMax - lMin)) * ph; }
        function yR(v) { return mT + ph - (Math.min(v, rMax) / rMax) * ph; }

        var ax = '', ax2 = '', s = '', i, k;
        for (k = 0; k <= 4; k++) {
            var lv = lMin + (lMax - lMin) * k / 4, rv = rMax * k / 4, yy = yL(lv).toFixed(1);
            ax += '<text x="' + (axisW - 6) + '" y="' + yy + '" dy="0.32em" text-anchor="end">' + short(lv) + '</text>';
            if (hasRight) { ax2 += '<text x="6" y="' + yR(rv).toFixed(1) + '" dy="0.32em">' + (cfg.rightFmt ? cfg.rightFmt(rv) : short(rv)) + '</text>'; }
            s += '<line class="gl" x1="0" x2="' + W + '" y1="' + yy + '" y2="' + yy + '"/>';
        }
        var bars = cfg.bars || [], nb = bars.length, bw = Math.min(band * 0.72 / Math.max(nb, 1), 26);
        for (i = 0; i < n; i++) {
            var x0 = band * i + (band - bw * nb) / 2, tip = esc(labels[i]);
            bars.forEach(function (b, j) {
                var v = b.values[i], yb = b.axis === 'right' ? yR : yL;
                if (v === null || v === undefined) { return; }
                var y1 = yb(Math.max(v, 0)), y0 = yb(Math.min(v, 0));
                s += '<rect x="' + (x0 + j * bw).toFixed(1) + '" y="' + y1.toFixed(1) + '" width="' + (bw - 1).toFixed(1) + '" height="'
                    + Math.max(1, y0 - y1).toFixed(1) + '" rx="2" fill="' + b.color + '"><title>' + tip + ' · ' + esc(b.name) + ': ' + fmtN(v, cfg.dec || 0) + '</title></rect>';
            });
            s += '<text x="' + (band * i + band / 2).toFixed(1) + '" y="' + (H - 8) + '" text-anchor="middle">' + esc(labels[i]) + '</text>';
        }
        (cfg.refs || []).forEach(function (r) {
            var yy = yR(r.value).toFixed(1);
            s += '<line x1="0" x2="' + W + '" y1="' + yy + '" y2="' + yy + '" stroke="' + r.color + '" stroke-width="1.5" stroke-dasharray="5 4"/>';
        });
        (cfg.lines || []).forEach(function (l) {
            var y = l.axis === 'right' ? yR : yL, pts = [], dots = '';
            l.values.forEach(function (v, j) {
                if (v === null || v === undefined || isNaN(v)) { return; }
                var px = (band * j + band / 2).toFixed(1), py = y(v).toFixed(1);
                pts.push(px + ',' + py);
                if (l.dots !== false) {
                    dots += '<circle cx="' + px + '" cy="' + py + '" r="3" fill="' + l.color + '"><title>' + esc(labels[j]) + ' · ' + esc(l.name) + ': '
                        + (l.fmt ? l.fmt(v) : fmtN(v, cfg.dec || 0)) + '</title></circle>';
                }
            });
            s += '<polyline points="' + pts.join(' ') + '" fill="none" stroke="' + l.color + '" stroke-width="2"'
                + (l.dash ? ' stroke-dasharray="6 4"' : '') + '/>' + dots;
        });
        el.innerHTML = '<div class="cc-y"><svg width="' + axisW + '" height="' + H + '">' + ax + '</svg></div>'
            + '<div class="cc-x"><svg width="' + W.toFixed(0) + '" height="' + H + '">' + s + '</svg></div>'
            + (hasRight ? '<div class="cc-y2"><svg width="' + axisW + '" height="' + H + '">' + ax2 + '</svg></div>' : '');
        if (cfg.scrollEnd) { var xs = el.querySelector('.cc-x'); xs.scrollLeft = xs.scrollWidth; }
    }

    /* Gambar ulang chart saat ukuran layar berubah */
    var renders = [];
    function onResize(fn) { renders.push(fn); fn(); }
    var t = 0;
    window.addEventListener('resize', function () { clearTimeout(t); t = setTimeout(function () { renders.forEach(function (f) { f(); }); }, 150); });

    return { P: P, fmtN: fmtN, spark: spark, combo: combo, onResize: onResize };
})();
