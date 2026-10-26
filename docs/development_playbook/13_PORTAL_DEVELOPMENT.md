# 13 — Portal Development

## 1. Peta halaman (Verified)

| Halaman | Route | Handler | Template | Data / DB | Otorisasi | CSS/JS | Test |
|---|---|---|---|---|---|---|---|
| Login | `/login` | `auth.login` | `portal/login.html` (`_auth_layout`) | `users`, `audit_log` | publik, CSRF, throttle | `shell.css`, `portal.css` | `test_login_and_access` |
| Lupa password | `/forgot-password` | `auth.forgot_password` | `portal/forgot_password.html` | `users.reset_requested_at` | publik | idem | `test_forgot_password` |
| Ganti password | `/account/password` | `auth.change_password` | `portal/change_password.html` (`bare` jika wajib) | `users` | login | idem | `test_new_user_must_change_temporary_password` |
| Home | `/` | `portal.home` | `portal/home.html` | favorites + dashboard visible (Quick Access 5) | login | `portal.css/js` | `test_login_and_access` |
| Reports | `/reports` | `portal.reports` | `portal/reports.html` | visible + favorites; `?q=&category=` | login | `portal.js` (filter di browser) | `test_user_sees_only_granted_dashboards` |
| Favorites | `/favorites` | `portal.favorites` | `portal/favorites.html` | `favorites` ∩ visible | login | `shell.js` (toggle) | — |
| History | `/history` | `portal.history` | `portal/history.html` | `history` ∩ visible (50 terakhir) | login | — | — |
| Settings | `/settings` | `portal.settings` | `portal/settings.html` | status konfigurasi (Super Admin saja) | login | — | — |
| Admin Users | `/admin/users`, `/new`, `/<id>` | `admin.*` | `admin/users.html`, `user_new.html`, `user_detail.html`, `temp_password.html` | `users`, akses, audit | `admin_required` | `portal.css` | `test_login_and_access` |
| Admin Dashboards | `/admin/dashboards` | `admin.dashboards` | `admin/dashboards.html` | `dashboards` | `admin_required` | — | `test_inactive_dashboard_is_blocked_for_everyone` |
| Audit Log | `/admin/audit` | `admin.audit` | `admin/audit.html` + `_audit_table.html` | `audit_log` (300 terakhir, filter `?action=`) | `admin_required` | — | `test_audit_log_is_human_readable` |
| Access denied | — | `registry._guard`, `role_required` | `portal/denied.html` | — | — | — | `test_direct_url_to_other_dashboard_is_403` |
| Error 400/404/500 | — | handler di `create_app` | `portal/error.html` | — | — | — | `test_404_page_is_english` |

Favorit dan History hanya menampilkan dashboard yang **masih** boleh dibuka user (`registry.visible_for`).

## 2. Prosedur: menambah halaman portal

### A. Objective
Menambah halaman baru di portal (bukan halaman report).
### B. When to use
Misalnya halaman "Help" atau "Announcements".
### C. Prerequisites
Paham dok 08 (inheritance) dan dok 12 (otorisasi).
### D. Architecture context
Halaman portal = route di blueprint `portal` (`mantra/portal.py`) + template yang `extends "portal/base.html"`.
### E. Files involved
| File | Wajib? | Perubahan |
|---|---|---|
| `mantra/portal.py` | Wajib | Route baru + `@login_required` |
| `templates/portal/<baru>.html` | Wajib | Extend `portal/base.html` |
| `templates/components/sidebar.html` | Opsional | Item menu |
| `templates/portal/_ui.html` | Opsional | Ikon baru |
| `static/css/portal.css` | Opsional | Gaya |
| `tests/test_login_and_access.py` | Wajib | Anonim → redirect; login → 200 |
### F. Step-by-step instructions
1. Tambah route (G).
2. Buat template.
3. (Opsional) tambah menu di sidebar.
4. Tambah test, jalankan `python -m pytest`.
5. Cek manual di 1280 / 1000 / 800 px.
### G. Code or patch (`Proposed`, contoh)
```python
# mantra/portal.py
@bp.get("/help")
@login_required
def help_page():
    return render_template("portal/help.html")
```
```jinja
{# mantra/templates/portal/help.html #}
{% extends "portal/base.html" %}
{% block title %}Help{% endblock %}
{% block content %}
<div class="page-head">
  <div>
    <h1>Help</h1>
    <p class="muted">How to use Power BI Portal</p>
  </div>
</div>
{% endblock %}
```
Pola `page-head` + `muted` sama dengan `favorites.html` dan `history.html` (Verified).
### H. Code explanation
`@login_required` me-redirect anonim ke `/login?next=/help`. `portal/base.html` menyediakan flash message & CSS portal.
### I. Commands
`python -m pytest` · `python run.py`
### J. Expected result
`/help` tampil dengan sidebar & top bar.
### K. Validation
Anonim: `curl -I http://localhost:5001/help` → 302 ke login.
### L. Troubleshooting
`TemplateNotFound` → path template relatif terhadap `mantra/templates/`.
### M. Regression impact
Sidebar (jika diubah) memengaruhi semua halaman.
### N. Acceptance criteria
Route terlindungi, test ditambahkan, tampilan konsisten.
### O. Documentation updates
Tabel bagian 1 dokumen ini, dok 10.
### P. Actual status
Prosedur: NOT RUN (contoh). Halaman portal existing: PASS (test).
