/* Panel AI agent dashboard: kirim pertanyaan ke /d/<slug>/api/chat, tampilkan jawaban (markdown sederhana) dan data
   yang dipakai. URL, judul, dan contoh pertanyaan datang dari manifest dashboard (window.CHAT). */
(function () {
'use strict';

const el = (id) => document.getElementById(id);
const esc = Dash.esc;
const CSRF = document.querySelector('meta[name="csrf-token"]').content;
const CFG = window.CHAT || {};
const HISTORY = [];
const SUGGESTIONS = CFG.suggestions || [];
let busy = false;

/* ---------- markdown sederhana: tabel, list, bold, italic, code ---------- */
function inline(s) {
    return s.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
        .replace(/(^|[\s(])_(.+?)_(?=$|[\s).,])/g, '$1<i>$2</i>')
        .replace(/(^|[\s(])\*(?!\s)(.+?)\*(?=$|[\s).,])/g, '$1<i>$2</i>')
        .replace(/`([^`]+)`/g, '<code>$1</code>');
}
function markdown(text) {
    const lines = esc(text).split('\n');
    let html = '', i = 0;
    while (i < lines.length) {
        const line = lines[i].trim();
        if (line.startsWith('|')) {
            const rows = [];
            while (i < lines.length && lines[i].trim().startsWith('|')) { rows.push(lines[i].trim()); i++; }
            const cells = (r) => r.replace(/^\||\|$/g, '').split('|').map((c) => inline(c.trim()));
            const body = rows.filter((r) => !/^\|[\s:|-]+\|$/.test(r));
            html += '<div class="chat-table"><table><thead><tr>' + cells(body[0]).map((c) => '<th>' + c + '</th>').join('')
                + '</tr></thead><tbody>' + body.slice(1).map((r) => '<tr>' + cells(r).map((c) => '<td>' + c + '</td>').join('') + '</tr>').join('')
                + '</tbody></table></div>';
            continue;
        }
        const bullet = /^[-*•]\s+/, numbered = /^\d+[.)]\s+/;
        if (bullet.test(line) || numbered.test(line)) {
            const re = bullet.test(line) ? bullet : numbered, tag = re === bullet ? 'ul' : 'ol';
            html += '<' + tag + '>';
            while (i < lines.length && re.test(lines[i].trim())) { html += '<li>' + inline(lines[i].trim().replace(re, '')) + '</li>'; i++; }
            html += '</' + tag + '>';
            continue;
        }
        if (/^#{1,6}\s+/.test(line)) { html += '<p><b>' + inline(line.replace(/^#+\s+/, '')) + '</b></p>'; }
        else if (line) { html += '<p>' + inline(line) + '</p>'; }
        i++;
    }
    return html;
}

/* ---------- tampilan ---------- */
function scroll() { el('chatBody').scrollTop = el('chatBody').scrollHeight; }

function bubble(role, html) {
    const div = document.createElement('div');
    div.className = 'chat-msg ' + role;
    div.innerHTML = html;
    el('chatBody').appendChild(div);
    scroll();
    return div;
}

function toolSummary(tools) {
    if (!tools || !tools.length) { return ''; }
    const items = tools.map((t) => {
        const args = Object.entries(t.args || {}).map(([k, v]) => k + '=' + v).join(', ');
        return '<li><b>' + esc(t.label || t.name) + '</b>' + (args ? ' · ' + esc(args) : '') + '</li>';
    }).join('');
    return '<details class="chat-tools"><summary>Data yang dipakai (' + tools.length + ' query)</summary><ul>' + items + '</ul></details>';
}

function welcome() {
    el('chatBody').innerHTML = '';
    bubble('bot', '<p>Halo! Saya AI agent ' + esc(CFG.title || 'dashboard ini') + '. Saya menjawab langsung dari semantic model Power BI.</p>'
        + '<div class="chat-suggest">' + SUGGESTIONS.map((s) => '<button type="button">' + esc(s) + '</button>').join('') + '</div>');
}

/* ---------- kirim ---------- */
async function send(text) {
    text = text.trim();
    if (!text || busy) { return; }
    busy = true;
    el('chatSend').disabled = true;
    el('chatInput').value = '';
    autosize();
    bubble('user', '<p>' + esc(text) + '</p>');
    const wait = bubble('bot loading', '<span class="dots"><i></i><i></i><i></i></span> Mengambil data dari Power BI...');
    try {
        const r = await fetch(CFG.url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': CSRF },
            body: JSON.stringify({
                message: text,
                history: HISTORY.slice(-20),
                context: window.DashContext ? window.DashContext() : '',
                filters: window.DashFilters ? window.DashFilters() : null,
            }),
        });
        const data = await r.json().catch(() => ({ error: 'Respons server tidak valid (HTTP ' + r.status + ')' }));
        if (!r.ok || data.error) { throw new Error(data.error || 'HTTP ' + r.status); }
        wait.className = 'chat-msg bot';
        wait.innerHTML = markdown(data.answer) + toolSummary(data.tools);
        HISTORY.push({ role: 'user', text: text }, { role: 'model', text: data.answer });
    } catch (e) {
        wait.className = 'chat-msg bot error';
        wait.textContent = e.message;
    }
    busy = false;
    el('chatSend').disabled = false;
    el('chatInput').focus();
    scroll();
}

function autosize() {
    const t = el('chatInput');
    t.style.height = 'auto';
    t.style.height = Math.min(t.scrollHeight, 120) + 'px';
}

/* ---------- events ---------- */
el('chatFab').addEventListener('click', () => {
    const panel = el('chatPanel');
    panel.hidden = !panel.hidden;
    el('chatFab').classList.toggle('open', !panel.hidden);
    if (!panel.hidden) {
        if (!el('chatBody').children.length) { welcome(); }
        el('chatInput').focus();
    }
});
el('chatClose').addEventListener('click', () => { el('chatPanel').hidden = true; el('chatFab').classList.remove('open'); });
el('chatReset').addEventListener('click', () => { if (!busy) { HISTORY.length = 0; welcome(); } });
el('chatForm').addEventListener('submit', (e) => { e.preventDefault(); send(el('chatInput').value); });
el('chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(el('chatInput').value); }
});
el('chatInput').addEventListener('input', autosize);
el('chatBody').addEventListener('click', (e) => {
    const b = e.target.closest('.chat-suggest button');
    if (b) { send(b.textContent); }
});
})();
