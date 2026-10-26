"""Akun, hak akses dashboard, dan audit log (tabel users, dashboards, user_dashboard_access, audit_log di mantra.db).

Aturan akses (dipakai core/auth.py):
- super_admin: semua dashboard yang aktif di katalog.
- user: hanya dashboard aktif yang punya baris di user_dashboard_access (default deny).
- Akun nonaktif tidak bisa login, dan sesinya langsung tidak berlaku.
Role super_admin hanya bisa diberikan lewat scripts/manage_users.py (butuh akses ke server), tidak lewat halaman web.
"""
import json
import re
import secrets
from datetime import datetime, timedelta

from flask import has_request_context, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

ROLES = {"super_admin": "Super Admin", "user": "User"}
MAX_FAILED_LOGINS = 5                 # gagal berturut-turut sebelum akun dikunci sementara
LOCK_MINUTES = 15
PASSWORD_MIN_LENGTH = 10
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Hash pembanding untuk email yang tidak terdaftar, supaya waktu respons login sama (tidak membocorkan email valid)
_DUMMY_HASH = generate_password_hash(secrets.token_hex(16))


class AccountError(ValueError):
    """Input tidak valid; pesannya aman ditampilkan ke user."""


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_email(email):
    return (email or "").strip().lower()


def validate_email(email):
    email = normalize_email(email)
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise AccountError("Format email tidak valid.")
    return email


def password_problem(password, email=""):
    """Kebijakan password baru. Mengembalikan pesan masalah, atau None kalau password boleh dipakai."""
    if len(password or "") < PASSWORD_MIN_LENGTH:
        return f"Password minimal {PASSWORD_MIN_LENGTH} karakter."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password harus berisi huruf dan angka."
    local = normalize_email(email).split("@")[0]
    if local and local in password.lower():
        return "Password tidak boleh mengandung nama email."
    return None


def temporary_password():
    """Password sementara acak (dipakai saat buat user / reset). User wajib menggantinya saat login."""
    return secrets.token_urlsafe(9)


# ------------------------------------------------------------------ users

def get_user(user_id):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_email(email):
    return get_db().execute("SELECT * FROM users WHERE email = ?", (normalize_email(email),)).fetchone()


def list_users():
    """Semua user + slug dashboard yang diizinkan (untuk halaman admin)."""
    users = get_db().execute("SELECT * FROM users ORDER BY role = 'super_admin' DESC, email").fetchall()
    grants = {}
    for r in get_db().execute(
            """SELECT a.user_id, d.slug, d.name FROM user_dashboard_access a
               JOIN dashboards d ON d.id = a.dashboard_id ORDER BY d.name"""):
        grants.setdefault(r["user_id"], []).append({"slug": r["slug"], "name": r["name"]})
    return [{"user": u, "dashboards": grants.get(u["id"], [])} for u in users]


def create_user(email, name="", password=None, role="user", must_change_password=True, actor=None):
    """Buat user baru. Mengembalikan id. Gagal (AccountError) kalau email sudah terdaftar."""
    email = validate_email(email)
    if role not in ROLES:
        raise AccountError("Role tidak dikenal.")
    if not password:
        raise AccountError("Password awal wajib diisi.")
    conn = get_db()
    if get_user_by_email(email):
        raise AccountError("Email sudah terdaftar.")
    cur = conn.execute(
        """INSERT INTO users (email, name, password_hash, role, must_change_password)
           VALUES (?, ?, ?, ?, ?)""",
        (email, (name or "").strip()[:120], generate_password_hash(password), role, int(must_change_password)))
    conn.commit()
    audit("user_created", "user", cur.lastrowid, actor=actor, email=email, role=role)
    return cur.lastrowid


def set_password(user_id, password, must_change=False, actor=None, action="password_changed"):
    """Simpan password baru (hash). Menaikkan session_version, jadi sesi lain user ini otomatis logout."""
    conn = get_db()
    conn.execute(
        """UPDATE users SET password_hash = ?, must_change_password = ?, password_changed_at = ?,
               session_version = session_version + 1, failed_logins = 0, locked_until = NULL, updated_at = ?
           WHERE id = ?""",
        (generate_password_hash(password), int(must_change), _now(), _now(), user_id))
    conn.commit()
    audit(action, "user", user_id, actor=actor)
    return get_user(user_id)["session_version"]


def set_active(user_id, active, actor=None):
    user = get_user(user_id)
    if user is None:
        raise AccountError("User tidak ditemukan.")
    if not active and user["role"] == "super_admin" and _active_admins() <= 1:
        raise AccountError("Tidak bisa menonaktifkan satu-satunya Super Admin yang aktif.")
    conn = get_db()
    conn.execute("UPDATE users SET is_active = ?, session_version = session_version + 1, updated_at = ? WHERE id = ?",
                 (int(active), _now(), user_id))
    conn.commit()
    audit("user_activated" if active else "user_deactivated", "user", user_id, actor=actor, email=user["email"])


def set_role(user_id, role, actor=None):
    """Ganti role. HANYA dipanggil dari scripts/manage_users.py, tidak ada route web yang memanggil ini."""
    if role not in ROLES:
        raise AccountError("Role tidak dikenal.")
    user = get_user(user_id)
    if user is None:
        raise AccountError("User tidak ditemukan.")
    if user["role"] == "super_admin" and role != "super_admin" and user["is_active"] and _active_admins() <= 1:
        raise AccountError("Tidak bisa menurunkan satu-satunya Super Admin yang aktif.")
    conn = get_db()
    conn.execute("UPDATE users SET role = ?, session_version = session_version + 1, updated_at = ? WHERE id = ?",
                 (role, _now(), user_id))
    conn.commit()
    audit("role_changed", "user", user_id, actor=actor, email=user["email"], old=user["role"], new=role)


def _active_admins():
    return get_db().execute("SELECT count(*) FROM users WHERE role = 'super_admin' AND is_active = 1").fetchone()[0]


def authenticate(email, password):
    """Cek email + password. Mengembalikan (row_user, None) kalau berhasil, atau (None, alasan) kalau gagal.

    Alasan: "invalid" (email/password salah, termasuk email tidak terdaftar), "locked", "inactive".
    Pesan ke user dibuat sama untuk "invalid" supaya tidak bisa dipakai menebak email yang terdaftar.
    """
    email = normalize_email(email)
    user = get_user_by_email(email) if email else None
    if user is None or not user["password_hash"]:
        check_password_hash(_DUMMY_HASH, password or "")
        audit("login_failed", "user", user["id"] if user else None, email=email, reason="invalid")
        return None, "invalid"
    if user["locked_until"] and user["locked_until"] > _now():
        audit("login_failed", "user", user["id"], email=email, reason="locked")
        return None, "locked"
    if not check_password_hash(user["password_hash"], password or ""):
        failed = user["failed_logins"] + 1
        locked = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).strftime("%Y-%m-%d %H:%M:%S") \
            if failed >= MAX_FAILED_LOGINS else None
        conn = get_db()
        conn.execute("UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?",
                     (0 if locked else failed, locked, user["id"]))
        conn.commit()
        audit("login_failed", "user", user["id"], email=email, reason="invalid", attempt=failed)
        if locked:
            audit("account_locked", "user", user["id"], email=email, minutes=LOCK_MINUTES)
        return None, "invalid"
    if not user["is_active"]:
        audit("login_failed", "user", user["id"], email=email, reason="inactive")
        return None, "inactive"
    record_login(user, method="password")
    return get_user(user["id"]), None


def record_login(user, method):
    conn = get_db()
    conn.execute("UPDATE users SET failed_logins = 0, locked_until = NULL, last_login_at = ? WHERE id = ?",
                 (_now(), user["id"]))
    conn.commit()
    audit("login_success", "user", user["id"], actor={"id": user["id"], "email": user["email"]}, method=method)


# ------------------------------------------------------------------ katalog dashboard

def sync_dashboards(conn, manifests):
    """Samakan katalog dashboard dengan dashboard yang terdaftar di kode (dipanggil saat start).

    Nama, workspace_id, dan dataset_id selalu mengikuti kode/.env. is_active hanya diisi untuk dashboard baru;
    setelah itu diatur Super Admin dari halaman Admin > Dashboards dan tidak ditimpa lagi.
    """
    for d in manifests:
        workspace_id, dataset_id = d.dataset.ids if d.dataset else (None, None)
        conn.execute(
            """INSERT INTO dashboards (slug, name, workspace_id, dataset_id) VALUES (?, ?, ?, ?)
               ON CONFLICT (slug) DO UPDATE SET name = excluded.name, workspace_id = excluded.workspace_id,
                   dataset_id = excluded.dataset_id,
                   updated_at = CASE WHEN dashboards.name IS NOT excluded.name
                                       OR dashboards.workspace_id IS NOT excluded.workspace_id
                                       OR dashboards.dataset_id IS NOT excluded.dataset_id
                                     THEN datetime('now', 'localtime') ELSE dashboards.updated_at END""",
            (d.slug, d.title, workspace_id, dataset_id))
    conn.commit()


def list_dashboards():
    return get_db().execute(
        """SELECT d.*, (SELECT count(*) FROM user_dashboard_access a WHERE a.dashboard_id = d.id) AS users
           FROM dashboards d ORDER BY d.name""").fetchall()


def get_dashboard(dashboard_id):
    return get_db().execute("SELECT * FROM dashboards WHERE id = ?", (dashboard_id,)).fetchone()


def set_dashboard_active(dashboard_id, active, actor=None):
    row = get_dashboard(dashboard_id)
    if row is None:
        raise AccountError("Dashboard tidak ditemukan.")
    conn = get_db()
    conn.execute("UPDATE dashboards SET is_active = ?, updated_at = ? WHERE id = ?", (int(active), _now(), dashboard_id))
    conn.commit()
    audit("dashboard_activated" if active else "dashboard_deactivated", "dashboard", row["slug"], actor=actor)


# ------------------------------------------------------------------ hak akses

def allowed_slugs(user_id, is_super_admin):
    """Slug dashboard yang boleh dibuka: semua yang aktif untuk Super Admin, atau yang diberi akses untuk user."""
    if is_super_admin:
        rows = get_db().execute("SELECT slug FROM dashboards WHERE is_active = 1")
    else:
        rows = get_db().execute(
            """SELECT d.slug FROM user_dashboard_access a
               JOIN dashboards d ON d.id = a.dashboard_id
               JOIN users u ON u.id = a.user_id
               WHERE a.user_id = ? AND d.is_active = 1 AND u.is_active = 1""", (user_id,))
    return {r["slug"] for r in rows}


def granted_ids(user_id):
    return {r["dashboard_id"] for r in get_db().execute(
        "SELECT dashboard_id FROM user_dashboard_access WHERE user_id = ?", (user_id,))}


def set_access(user_id, dashboard_ids, actor=None):
    """Simpan daftar dashboard yang boleh dibuka user (menggantikan daftar lama). Mengembalikan (diberi, dicabut)."""
    user = get_user(user_id)
    if user is None:
        raise AccountError("User tidak ditemukan.")
    if user["role"] == "super_admin":
        raise AccountError("Super Admin otomatis bisa membuka semua dashboard aktif; akses per dashboard tidak dipakai.")
    known = {r["id"]: r["slug"] for r in get_db().execute("SELECT id, slug FROM dashboards")}
    wanted = set(dashboard_ids)
    unknown = wanted - known.keys()
    if unknown:
        raise AccountError("Dashboard tidak dikenal.")
    current = granted_ids(user_id)
    grant, revoke = wanted - current, current - wanted
    conn = get_db()
    actor_id = actor.get("db_id") if actor else None
    for dashboard_id in sorted(grant):
        conn.execute("INSERT OR IGNORE INTO user_dashboard_access (user_id, dashboard_id, granted_by) VALUES (?, ?, ?)",
                     (user_id, dashboard_id, actor_id))
    for dashboard_id in sorted(revoke):
        conn.execute("DELETE FROM user_dashboard_access WHERE user_id = ? AND dashboard_id = ?", (user_id, dashboard_id))
    conn.commit()
    for dashboard_id in sorted(grant):
        audit("access_granted", "user", user_id, actor=actor, email=user["email"], dashboard=known[dashboard_id])
    for dashboard_id in sorted(revoke):
        audit("access_revoked", "user", user_id, actor=actor, email=user["email"], dashboard=known[dashboard_id])
    return [known[i] for i in sorted(grant)], [known[i] for i in sorted(revoke)]


def dashboard_ids_for(slugs):
    if not slugs:
        return []
    marks = ",".join("?" * len(slugs))
    rows = get_db().execute(f"SELECT id, slug FROM dashboards WHERE slug IN ({marks})", tuple(slugs)).fetchall()
    missing = set(slugs) - {r["slug"] for r in rows}
    if missing:
        raise AccountError(f"Dashboard belum ada di katalog: {', '.join(sorted(missing))}")
    return [r["id"] for r in rows]


# ------------------------------------------------------------------ audit log

def audit(action, target_type=None, target_id=None, actor=None, **detail):
    """Catat aktivitas penting. JANGAN pernah memasukkan password, hash, token, atau secret ke detail."""
    actor_id = actor_email = None
    if actor:
        actor_id, actor_email = actor.get("db_id", actor.get("id")), actor.get("email")
        actor_id = actor_id if isinstance(actor_id, int) else None
    ip = request.remote_addr if has_request_context() else None
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_log (actor_id, actor_email, action, target_type, target_id, detail, ip) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (actor_id, actor_email, action, target_type, None if target_id is None else str(target_id),
         json.dumps(detail, ensure_ascii=False, default=str) if detail else None, ip))
    conn.commit()


def audit_entries(limit=200, action=None):
    if action:
        return get_db().execute("SELECT * FROM audit_log WHERE action = ? ORDER BY at DESC, id DESC LIMIT ?",
                                (action, limit)).fetchall()
    return get_db().execute("SELECT * FROM audit_log ORDER BY at DESC, id DESC LIMIT ?", (limit,)).fetchall()


def audit_for_user(user_id, limit=30):
    """Aktivitas yang menyangkut satu user (sebagai pelaku atau target), untuk halaman detail user."""
    return get_db().execute(
        """SELECT * FROM audit_log WHERE actor_id = ? OR (target_type = 'user' AND target_id = ?)
           ORDER BY at DESC, id DESC LIMIT ?""", (user_id, str(user_id), limit)).fetchall()


def audit_actions():
    """[(kode aktivitas, label)] yang pernah tercatat, untuk filter di halaman Audit Log."""
    codes = [r["action"] for r in get_db().execute("SELECT DISTINCT action FROM audit_log")]
    return sorted(((c, AUDIT_LABELS.get(c, c)) for c in codes), key=lambda item: item[1])


AUDIT_LABELS = {
    "login_success": "Login berhasil", "login_failed": "Login gagal", "account_locked": "Akun dikunci",
    "login_throttled": "Login dibatasi", "logout": "Logout", "password_changed": "Ganti password",
    "password_reset": "Reset password", "user_created": "User dibuat", "user_activated": "User diaktifkan",
    "user_deactivated": "User dinonaktifkan", "role_changed": "Role diubah", "access_granted": "Akses diberikan",
    "access_revoked": "Akses dicabut", "dashboard_activated": "Dashboard diaktifkan",
    "dashboard_deactivated": "Dashboard dinonaktifkan", "access_denied": "Akses ditolak",
}
_AUDIT_BAD = {"login_failed", "account_locked", "login_throttled", "access_denied", "user_deactivated",
              "access_revoked", "dashboard_deactivated"}
_AUDIT_GOOD = {"login_success", "user_created", "user_activated", "access_granted", "dashboard_activated"}
_LOGIN_REASONS = {"invalid": "email atau password salah", "locked": "akun sedang terkunci",
                  "inactive": "akun nonaktif", "not_registered": "akun Microsoft belum terdaftar di MANTRA"}


def describe_audit(rows):
    """Baris audit_log -> kalimat yang mudah dibaca admin. Mengembalikan list dict:
    {e: baris asli, label, tone: bad|good|"", text, actor}."""
    emails = {str(r["id"]): r["email"] for r in get_db().execute("SELECT id, email FROM users")}
    names = {r["slug"]: r["name"] for r in get_db().execute("SELECT slug, name FROM dashboards")}
    out = []
    for e in rows:
        try:
            d = json.loads(e["detail"]) if e["detail"] else {}
        except ValueError:
            d = {}
        action = e["action"]
        target_user = d.get("email") or (emails.get(e["target_id"]) if e["target_type"] == "user" else None) or "-"
        slug = d.get("dashboard") or (e["target_id"] if e["target_type"] == "dashboard" else "")
        dash = names.get(slug, slug)
        actor = e["actor_email"] or ""
        if actor.startswith("cli:"):
            actor = f"Script server ({actor[4:]})"
        self_action = bool(e["actor_email"]) and e["actor_email"] == target_user

        if action == "login_success":
            text = f"Login berhasil lewat {'akun Microsoft' if d.get('method') == 'entra' else 'email + password'}"
        elif action == "login_failed":
            text = f"Login gagal untuk {target_user}: {_LOGIN_REASONS.get(d.get('reason'), d.get('reason') or '-')}"
            if d.get("attempt"):
                text += f" (percobaan ke-{d['attempt']})"
            if d.get("method") == "entra":
                text += ", lewat akun Microsoft"
        elif action == "account_locked":
            text = f"Akun {target_user} dikunci {d.get('minutes', LOCK_MINUTES)} menit karena terlalu banyak percobaan gagal"
        elif action == "login_throttled":
            text = f"Login dari IP {e['target_id']} dibatasi sementara karena terlalu banyak percobaan gagal"
        elif action == "logout":
            text = "Logout"
        elif action == "password_changed":
            text = "Mengganti password sendiri" if self_action else f"Password {target_user} diganti"
        elif action == "password_reset":
            text = f"Password {target_user} di-reset; user wajib membuat password baru saat login"
        elif action == "user_created":
            text = f"User {target_user} dibuat sebagai {ROLES.get(d.get('role'), d.get('role') or 'User')}"
        elif action in ("user_activated", "user_deactivated"):
            text = f"Akun {target_user} {'diaktifkan' if action == 'user_activated' else 'dinonaktifkan'}"
        elif action == "role_changed":
            text = (f"Role {target_user} diubah dari {ROLES.get(d.get('old'), d.get('old'))} "
                    f"menjadi {ROLES.get(d.get('new'), d.get('new'))}")
        elif action == "access_granted":
            text = f"{target_user} diberi akses ke {dash}"
        elif action == "access_revoked":
            text = f"Akses {target_user} ke {dash} dicabut"
        elif action in ("dashboard_activated", "dashboard_deactivated"):
            text = f"Dashboard {dash} {'diaktifkan' if action == 'dashboard_activated' else 'dinonaktifkan'}"
        elif action == "access_denied":
            text = (f"Mencoba membuka {dash} tanpa izin" if e["target_type"] == "dashboard"
                    else f"Mencoba membuka halaman khusus Super Admin ({e['target_id']})")
        else:
            text = e["detail"] or ""
        out.append({"e": e, "label": AUDIT_LABELS.get(action, action), "text": text, "actor": actor,
                    "tone": "bad" if action in _AUDIT_BAD else "good" if action in _AUDIT_GOOD else ""})
    return out
