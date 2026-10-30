# 24 — Security & Secrets

## 1. Kontrol keamanan yang ada (Verified; kolom Test = bukti otomatis)

| Area | Kontrol | Lokasi | Test |
|---|---|---|---|
| Secret | `.env` di `.gitignore`; `check_setup.py` tidak mencetak secret; audit/log tanpa secret | `.gitignore`, scripts | `test_audit_log_and_app_log_contain_no_secrets` |
| Password | Hash Werkzeug; kebijakan ≥10, huruf+angka, tanpa nama email; dummy hash untuk email tak terdaftar (cegah timing) | `accounts.py` | `test_passwords_are_hashed` |
| Brute force | Lockout akun 5x/15 mnt (dikunci di kegagalan ke-5; pesan "locked" baru tampil di percobaan ke-6, kegagalan ke-5 tetap berpesan generik); throttle IP login 20/15 mnt, reset 5/15 mnt | `accounts.py`, `auth.py` | `test_account_locks_after_repeated_failures`, `test_ip_throttle` |
| Enumerasi email | Pesan login generik; lupa password respons sama | `auth.py`, `accounts.py` | `test_wrong_password_rejected_with_generic_message`, `test_unknown_and_inactive_emails_get_the_same_response` |
| Session | Cookie ditandatangani, `HttpOnly`, `SameSite=Lax`, opsional `Secure`; `session.clear()` saat login (anti fixation); `session_version` (invalidasi) | `config.py`, `auth.py` | `test_session_cookie_cannot_be_forged`, `test_reset_password_logs_out_user` |
| CSRF | Token per session, wajib di semua POST (form & fetch) | `__init__.py` | `test_post_without_csrf_is_rejected`, `test_non_ascii_csrf_token_is_400_not_500` |
| Open redirect | `_safe_next` hanya path lokal | `auth.py` | — (Verified) |
| Otorisasi | Default deny; `_guard` di halaman, API, **static** dashboard; `admin_required`; cek di chat | `registry.py`, `auth.py`, `chat/routes.py` | `test_direct_url_to_other_dashboard_is_403`, `test_data_api_static_and_chat_are_protected` |
| Eskalasi role | Tidak ada route web yang memberi `super_admin`; Super Admin tidak bisa menonaktifkan diri | `admin.py`, `accounts.py` | `test_no_web_route_can_promote_to_super_admin`, `test_admin_cannot_deactivate_self` |
| Manipulasi request | ID dashboard dari form divalidasi | `admin.py`, `accounts.set_access` | `test_user_cannot_change_access_by_manipulating_requests`, `test_admin_rejects_unknown_dashboard_id` |
| Password sementara | Tampil sekali, `Cache-Control: no-store`, tidak disimpan di session/log | `admin.py` | `test_new_user_must_change_temporary_password` |
| Clickjacking / sniffing / referrer | `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin` | `__init__.py` | `test_security_headers`; Tested di localhost |
| Kebocoran error | User melihat pesan umum + kode ref; ID workspace/dataset & isi respons hanya di log | `errors.py` | `test_power_bi_error_details_are_not_shown` |
| DAX injection | `dax_str()` untuk literal; angka/tanggal dikonversi | `common.py`, `queries.py` | — (Verified) |
| AI | Tool allowlist per dashboard; AI tidak menulis DAX; parameter divalidasi; detail error tidak dikirim ke AI; rate limit per user | `chat/*` | `test_chat_is_rate_limited_per_user`, `test_invalid_tool_argument_returns_valid_options` |
| Debugger | `FLASK_DEBUG=0` default (debugger Werkzeug bisa eksekusi kode) | `config.py`, `run.py` | — |
| Mode tanpa login | `AUTH_DISABLED` hanya dari file `.env`, banner peringatan + log | `config.py` | `test_auth_disabled_is_read_only_from_env_file` |
| XSS | Jinja autoescape; payload JSON via `|tojson`; `chat.js` escape (`Dash.esc`) sebelum markdown | template, JS | — (Verified) |

## 2. Aturan secret

1. Jangan commit `.env`, jangan tempel isinya di chat/issue/dokumen. Cek: `git status` tidak boleh menampilkan `.env`.
2. Secret yang terlanjur terekspos → **rotasi** (buat secret baru di Entra / API key baru), bukan sekadar hapus file.
3. `MANTRA_SEED_PASSWORD` hanya di environment saat seed, lalu `unset MANTRA_SEED_PASSWORD`.
4. Mengganti `FLASK_SECRET_KEY` me-logout semua user (cookie lama tidak valid).
5. Secret tidak boleh masuk prompt AI (prompt dikirim ke Gemini).

## 3. Risiko yang diketahui (lihat juga dok 28)

| Risiko | Dampak | Status |
|---|---|---|
| Throttle IP, rate limit chat & Power BI di memori per proses | Reset saat restart; tidak berlaku lintas proses | Diketahui, memadai untuk dev server 1 proses |
| `request.remote_addr` di balik reverse proxy = IP proxy | Throttle IP bisa memblokir semua user sekaligus | Not Applicable (localhost); perlu ditangani bila di-deploy |
| Logo dimuat dari `i.ibb.co.com` (header & data model) | Ketergantungan host luar | Belum ditangani (sumber di data Power BI) |
| Pertanyaan chat tidak dicatat di audit log | Tidak ada jejak penggunaan AI per user | `Proposed`: tambah audit `chat_question` (tanpa isi sensitif) |
| `history` chat dikirim browser | User bisa memalsukan riwayat percakapannya sendiri | Dampak terbatas (tidak memberi akses data baru; tools tetap dibatasi dashboard) |
| Tool `lookup` Material Readiness mencari di **semua branch** (termasuk yang tidak tampil di dashboard) | Data di luar tampilan dashboard bisa dibaca lewat AI oleh user yang punya akses dashboard | By design (deskripsi tool & prompt); perlu keputusan pemilik data |
| Dev server Werkzeug | Bukan server produksi | Not Applicable (scope localhost) |
