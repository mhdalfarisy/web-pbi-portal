"""Data milik portal (instance/mantra.db): Favorites dan History per user.

Data dashboard TIDAK disimpan di sini; semuanya dibaca langsung dari semantic model Power BI.
"""
import sqlite3

from flask import current_app, g

SCHEMA = """
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
"""

HISTORY_KEEP = 100  # riwayat per user yang disimpan


def init_app(app):
    app.config["INSTANCE_DIR"].mkdir(exist_ok=True)
    conn = sqlite3.connect(app.config["APP_DB"])
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()
    app.teardown_appcontext(_close_db)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["APP_DB"])
        g.db.row_factory = sqlite3.Row
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
