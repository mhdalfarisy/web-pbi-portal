"""Data milik portal (instance/mantra.db): akun & hak akses, Favorites, History, audit log.

Data dashboard TIDAK disimpan di sini; semuanya dibaca langsung dari semantic model Power BI.

Skema dikelola lewat MIGRATIONS (nomor versi disimpan di PRAGMA user_version). Saat start, migrasi yang belum jalan
dipasang otomatis, dan database yang sudah berisi data di-backup dulu ke instance/backups/. Migrasi hanya boleh
MENAMBAH (tabel/kolom/index baru); jangan ubah migrasi yang sudah ada, tambahkan yang baru di akhir list.
Fungsi akun, hak akses dashboard, dan audit log ada di core/accounts.py.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import current_app, g

NOW = "(datetime('now', 'localtime'))"

MIGRATIONS = [
    # 1: Favorites & History (skema awal portal)
    """
    CREATE TABLE IF NOT EXISTS favorites (
        user_id    TEXT NOT NULL,
        slug       TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        PRIMARY KEY (user_id, slug)
    );
    CREATE TABLE IF NOT EXISTS history (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    TEXT NOT NULL,
        slug       TEXT NOT NULL,
        title      TEXT NOT NULL,
        url        TEXT NOT NULL,
        visited_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    );
    CREATE INDEX IF NOT EXISTS ix_history_user ON history (user_id, visited_at DESC);
    """,
    # 2: akun (login email + password), katalog dashboard, hak akses per dashboard, audit log
    f"""
    CREATE TABLE IF NOT EXISTS users (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        email                TEXT NOT NULL UNIQUE COLLATE NOCASE,
        name                 TEXT NOT NULL DEFAULT '',
        password_hash        TEXT,
        role                 TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('super_admin', 'user')),
        is_active            INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
        must_change_password INTEGER NOT NULL DEFAULT 1 CHECK (must_change_password IN (0, 1)),
        session_version      INTEGER NOT NULL DEFAULT 1,
        failed_logins        INTEGER NOT NULL DEFAULT 0,
        locked_until         TEXT,
        last_login_at        TEXT,
        password_changed_at  TEXT,
        created_at           TEXT NOT NULL DEFAULT {NOW},
        updated_at           TEXT NOT NULL DEFAULT {NOW}
    );
    CREATE TABLE IF NOT EXISTS dashboards (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        slug         TEXT NOT NULL UNIQUE,
        name         TEXT NOT NULL,
        workspace_id TEXT,
        dataset_id   TEXT,
        report_id    TEXT,
        is_active    INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
        created_at   TEXT NOT NULL DEFAULT {NOW},
        updated_at   TEXT NOT NULL DEFAULT {NOW}
    );
    CREATE TABLE IF NOT EXISTS user_dashboard_access (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
        dashboard_id INTEGER NOT NULL REFERENCES dashboards (id) ON DELETE CASCADE,
        granted_by   INTEGER REFERENCES users (id) ON DELETE SET NULL,
        granted_at   TEXT NOT NULL DEFAULT {NOW},
        UNIQUE (user_id, dashboard_id)
    );
    CREATE INDEX IF NOT EXISTS ix_access_dashboard ON user_dashboard_access (dashboard_id);
    CREATE TABLE IF NOT EXISTS audit_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        at          TEXT NOT NULL DEFAULT {NOW},
        actor_id    INTEGER,
        actor_email TEXT,
        action      TEXT NOT NULL,
        target_type TEXT,
        target_id   TEXT,
        detail      TEXT,
        ip          TEXT
    );
    CREATE INDEX IF NOT EXISTS ix_audit_at ON audit_log (at DESC, id DESC);
    CREATE INDEX IF NOT EXISTS ix_audit_action ON audit_log (action, at DESC);
    """,
    # 3: permintaan "Forgot password" dari halaman login, ditangani Super Admin (diisi waktu permintaan terakhir;
    #    kosong lagi setelah password di-reset / permintaan diabaikan)
    """
    ALTER TABLE users ADD COLUMN reset_requested_at TEXT;
    """,
]

HISTORY_KEEP = 100  # riwayat per user yang disimpan


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def backup(conn, backup_dir, label):
    """Salinan konsisten database (SQLite backup API) ke backup_dir. Mengembalikan path file backup."""
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"mantra-{datetime.now():%Y%m%d-%H%M%S}-{label}.db"
    dest = sqlite3.connect(target)
    try:
        conn.backup(dest)
    finally:
        dest.close()
    return target


def migrate(path, backup_dir):
    """Pasang migrasi yang belum jalan. Mengembalikan (versi_awal, versi_akhir, path_backup_atau_None)."""
    conn = connect(path)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > len(MIGRATIONS):
            raise RuntimeError(f"Database versi {version} lebih baru dari kode (versi {len(MIGRATIONS)}). "
                               "Pakai kode terbaru, atau pulihkan backup yang sesuai.")
        if version == len(MIGRATIONS):
            return version, version, None
        has_data = conn.execute("SELECT count(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0] > 0
        saved = backup(conn, backup_dir, f"before-v{len(MIGRATIONS)}") if has_data else None
        for number, sql in enumerate(MIGRATIONS[version:], start=version + 1):
            try:
                conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        return version, len(MIGRATIONS), saved
    finally:
        conn.close()


def init_app(app):
    app.config["INSTANCE_DIR"].mkdir(exist_ok=True)
    before, after, saved = migrate(app.config["APP_DB"], app.config["INSTANCE_DIR"] / "backups")
    if after != before:
        app.logger.warning("Database dimigrasi dari versi %s ke %s%s", before, after,
                           f" (backup: {saved})" if saved else "")
    app.teardown_appcontext(_close_db)


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["APP_DB"])
    return g.db


def _close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def favorites(user_id):
    rows = get_db().execute("SELECT slug FROM favorites WHERE user_id = ? ORDER BY created_at", (user_id,))
    return [r["slug"] for r in rows]


def toggle_favorite(user_id, slug):
    """Tambah / hapus favorit. Mengembalikan True kalau sekarang menjadi favorit."""
    conn = get_db()
    removed = conn.execute("DELETE FROM favorites WHERE user_id = ? AND slug = ?", (user_id, slug)).rowcount
    if not removed:
        conn.execute("INSERT INTO favorites (user_id, slug) VALUES (?, ?)", (user_id, slug))
    conn.commit()
    return not removed


def add_history(user_id, slug, title, url):
    conn = get_db()
    # Membuka halaman yang sama berulang kali dalam 30 menit cukup memperbarui waktunya
    updated = conn.execute(
        """UPDATE history SET visited_at = datetime('now', 'localtime')
           WHERE id = (SELECT id FROM history WHERE user_id = ? ORDER BY visited_at DESC, id DESC LIMIT 1)
             AND url = ? AND visited_at >= datetime('now', 'localtime', '-30 minutes')""",
        (user_id, url)).rowcount
    if not updated:
        conn.execute("INSERT INTO history (user_id, slug, title, url) VALUES (?, ?, ?, ?)", (user_id, slug, title, url))
        conn.execute(
            """DELETE FROM history WHERE user_id = ? AND id NOT IN
               (SELECT id FROM history WHERE user_id = ? ORDER BY visited_at DESC, id DESC LIMIT ?)""",
            (user_id, user_id, HISTORY_KEEP))
    conn.commit()


def history(user_id, limit=50):
    return get_db().execute(
        "SELECT slug, title, url, visited_at FROM history WHERE user_id = ? ORDER BY visited_at DESC, id DESC LIMIT ?",
        (user_id, limit)).fetchall()
