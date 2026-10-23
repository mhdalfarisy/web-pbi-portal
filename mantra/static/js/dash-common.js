/* Fungsi bersama halaman Summary & Detail. */
window.Dash = (function () {
    'use strict';

    function esc(s) {
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
    function fmt(n) { return Math.round(n || 0).toLocaleString('en-US'); }

    /* Urutan status: Approval -> In Progress -> Not Ready -> Ready */
    function statusRank(s) {
        var l = String(s).toLowerCase();
        if (l.indexOf('approv') > -1) { return 1; }
        if (l.indexOf('progress') > -1) { return 2; }
        if (l.indexOf('not') > -1) { return 3; }
        if (l.indexOf('ready') > -1) { return 4; }
        return 9;
    }
    var BADGE = { 1: '#2563eb', 2: '#f59e0b', 3: '#dc2626', 4: '#16a34a' };
    function badgeColor(s) { return BADGE[statusRank(s)] || '#64748b'; }

    /* Warna header: biru default, atau mengikuti warna group company yang dipilih */
    function shade(hex, p) {
        hex = String(hex || '').replace('#', '');
        if (hex.length !== 6) { return null; }
        var n = parseInt(hex, 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
        function f(c) { return Math.max(0, Math.min(255, Math.round(c * (1 + p)))); }
        return '#' + [f(r), f(g), f(b)].map(function (c) { return ('0' + c.toString(16)).slice(-2); }).join('');
    }
    function setHdColor(hex) {
        var hd = document.getElementById('hd'), base = shade(hex, 0);
        hd.style.setProperty('--hd1', base ? shade(hex, -0.45) : '#1e3a8a');
        hd.style.setProperty('--hd2', base || '#2563eb');
    }

    /* Header: logo, nama entity & warna ikut filter Company. logo = {company: [logo group, logo company, warna]} */
    var INIT = null;
    function setHeaderCompany(name, logo) {
        var box = document.getElementById('hdLogoBox'), ent = document.getElementById('hdEntity');
        if (INIT === null) { INIT = { logo: box.innerHTML, entity: ent.textContent }; }
        var key = name || '';
        if (box.getAttribute('data-k') === key) { return; }
        box.setAttribute('data-k', key);
        var lg = key ? logo[key] : null;
        if (lg && lg[1]) {
            box.innerHTML = '<div class="hd-logos">'
                + (lg[0] ? '<img src="' + esc(lg[0]) + '" alt="" /><div class="hd-logo-sep"></div>' : '')
                + '<img src="' + esc(lg[1]) + '" alt="' + esc(key) + '" title="' + esc(key) + '" /></div>';
            setHdColor(lg[2]);
        } else {
            box.innerHTML = INIT.logo;
            setHdColor('');
        }
        ent.textContent = key || INIT.entity;
    }

    var MON = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    function moName(m) { return +m === 0 ? 'No Date' : MON[+m - 1]; }

    return { esc: esc, fmt: fmt, statusRank: statusRank, badgeColor: badgeColor, setHeaderCompany: setHeaderCompany, moName: moName };
})();
