"""Hash password, seed idempotent, migrasi aman, audit log tanpa rahasia (acceptance criteria 11-13, 15)."""
import json
import logging
import os
import sqlite3
import subprocess
import sys

from conftest import EMAILS, PASSWORD, ROOT

from mantra.core import db


def test_passwords_are_hashed(query):
    rows = query("SELECT password_hash FROM users")
    assert rows
    for r in rows:
        assert PASSWORD not in r["password_hash"]
        assert r["password_hash"].startswith(("scrypt:", "pbkdf2:"))


def _run_seed(db_dir, password="Seed-Tmp-777", extra=()):
    """Jalankan scripts/manage_users.py seed terhadap database sementara (bukan instance/mantra.db)."""
    code = f"""
import sys, runpy
from pathlib import Path
sys.argv = ["manage_users.py", "seed", *{list(extra)!r}]
import mantra.config as cfg
cfg.Config.INSTANCE_DIR = Path({str(db_dir)!r}); cfg.Config.APP_DB = Path({str(db_dir)!r}) / "mantra.db"
runpy.run_path({str(ROOT / "scripts" / "manage_users.py")!r}, run_name="__main__")
"""
    env = {**os.environ, "MANTRA_SEED_PASSWORD": password, "AUTH_DISABLED": "0"}
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)


def test_seed_is_idempotent_and_secret_free(tmp_path):
    first = _run_seed(tmp_path)
    assert first.returncode == 0, first.stderr
    second = _run_seed(tmp_path)
    assert second.returncode == 0, second.stderr
    assert "Seed-Tmp-777" not in first.stdout + first.stderr + second.stdout + second.stderr

    conn = sqlite3.connect(tmp_path / "mantra.db")
    conn.row_factory = sqlite3.Row
    users = {r["email"]: r for r in conn.execute("SELECT * FROM users")}
    assert set(users) == set(EMAILS.values())
    assert users[EMAILS["admin"]]["role"] == "super_admin"
    assert users[EMAILS["a"]]["role"] == users[EMAILS["b"]]["role"] == "user"
    assert all(u["must_change_password"] == 1 and "Seed-Tmp-777" not in u["password_hash"] for u in users.values())
    access = conn.execute("""SELECT u.email, d.slug FROM user_dashboard_access a JOIN users u ON u.id = a.user_id
                             JOIN dashboards d ON d.id = a.dashboard_id""").fetchall()
    assert sorted(tuple(r) for r in access) == [(EMAILS["a"], "material-readiness"), (EMAILS["b"], "pani-processing")]
    assert conn.execute("SELECT count(*) FROM dashboards").fetchone()[0] == 2
    audit = " ".join(str(tuple(r)) for r in conn.execute("SELECT * FROM audit_log"))
    assert "Seed-Tmp-777" not in audit


def test_seed_does_not_overwrite_existing_account(tmp_path):
    assert _run_seed(tmp_path, "pertama1").returncode == 0
    conn = sqlite3.connect(tmp_path / "mantra.db")
    before = conn.execute("SELECT email, password_hash, role FROM users ORDER BY email").fetchall()
    conn.execute("DELETE FROM user_dashboard_access")  # admin mencabut semua akses
    conn.commit()
    assert _run_seed(tmp_path, "kedua222").returncode == 0
    assert conn.execute("SELECT email, password_hash, role FROM users ORDER BY email").fetchall() == before
    assert conn.execute("SELECT count(*) FROM user_dashboard_access").fetchone()[0] == 0  # tidak diberi ulang diam-diam


def test_migration_keeps_existing_data_and_backs_up(tmp_path):
    path = tmp_path / "mantra.db"
    old = sqlite3.connect(path)
    old.executescript(db.MIGRATIONS[0])  # skema lama (versi 0, sebelum ada akun)
    old.execute("INSERT INTO favorites (user_id, slug) VALUES ('oid-1', 'material-readiness')")
    old.executemany("INSERT INTO history (user_id, slug, title, url) VALUES (?, ?, ?, ?)",
                    [("oid-1", "pani-processing", f"t{i}", f"/d/pani-processing/?i={i}") for i in range(25)])
    old.commit()
    old.close()

    before, after, backup = db.migrate(path, tmp_path / "backups")
    assert (before, after) == (0, len(db.MIGRATIONS))
    assert backup is not None and backup.exists()
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT count(*) FROM favorites").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM history").fetchone()[0] == 25
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"users", "dashboards", "user_dashboard_access", "audit_log"} <= tables
    assert sqlite3.connect(backup).execute("SELECT count(*) FROM history").fetchone()[0] == 25
    assert sqlite3.connect(backup).execute("PRAGMA user_version").fetchone()[0] == 0

    assert db.migrate(path, tmp_path / "backups") == (after, after, None)  # dijalankan ulang: tidak ada apa-apa
    assert len(list((tmp_path / "backups").iterdir())) == 1


def test_access_table_constraints(query, app, fresh_data):
    import pytest
    with app.app_context():
        conn = db.get_db()
        mr = conn.execute("SELECT id FROM dashboards WHERE slug = 'material-readiness'").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):  # unique (user_id, dashboard_id)
            conn.execute("INSERT INTO user_dashboard_access (user_id, dashboard_id) VALUES (?, ?)", (fresh_data["a"], mr))
        with pytest.raises(sqlite3.IntegrityError):  # foreign key
            conn.execute("INSERT INTO user_dashboard_access (user_id, dashboard_id) VALUES (999, ?)", (mr,))
        with pytest.raises(sqlite3.IntegrityError):  # role hanya super_admin / user
            conn.execute("UPDATE users SET role = 'owner' WHERE id = ?", (fresh_data["a"],))
        conn.rollback()


def test_audit_log_and_app_log_contain_no_secrets(client, login_as, fresh_data, query, caplog):
    caplog.set_level(logging.DEBUG)
    wrong = "TebakanSalah-987"
    client.login(EMAILS["a"], wrong)
    login_as("a")
    admin = login_as("admin")
    r = admin.post(f"/admin/users/{fresh_data['b']}/reset-password")
    temp = r.get_data(as_text=True).split('id="tempPass">')[1].split("<")[0]
    dump = json.dumps([dict(r) for r in query("SELECT * FROM audit_log")]) + caplog.text
    for secret in (wrong, PASSWORD, temp, "test-secret"):
        assert secret not in dump
    hashes = [r["password_hash"] for r in query("SELECT password_hash FROM users")]
    assert not any(h in dump for h in hashes)
    actions = {r["action"] for r in query("SELECT action FROM audit_log")}
    assert {"login_failed", "login_success", "password_reset"} <= actions



def test_auth_disabled_is_read_only_from_env_file():
    """`AUTH_DISABLED=1` yang tertinggal di terminal tidak boleh mematikan login; hanya file .env yang dihitung."""
    code = ("from dotenv import dotenv_values; from mantra.config import Config, BASE_DIR; "
            "expected = (dotenv_values(BASE_DIR / '.env').get('AUTH_DISABLED') or '').strip() == '1'; "
            "assert Config.AUTH_DISABLED is expected, Config.AUTH_DISABLED; print('ok')")
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env={**os.environ, "AUTH_DISABLED": "1"},
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0 and "ok" in result.stdout, result.stderr


def test_env_file_wins_over_inherited_terminal_variables():
    """Terminal VS Code bisa membawa .env project lain (python.terminal.useEnvFile). Kredensial service principal dari
    sana tidak boleh dipakai MANTRA; yang dipakai selalu .env MANTRA."""
    code = ("from dotenv import dotenv_values; from mantra.config import Config, BASE_DIR, ENV_OVERRIDDEN; "
            "env = dotenv_values(BASE_DIR / '.env'); "
            "assert Config.PBI_CLIENT_ID == (env.get('PBI_CLIENT_ID') or None), 'PBI_CLIENT_ID dari terminal terpakai'; "
            "assert ('PBI_CLIENT_ID' in ENV_OVERRIDDEN) == ('PBI_CLIENT_ID' in env); print('ok')")
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                            env={**os.environ, "PBI_CLIENT_ID": "service-principal-project-lain"},
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0 and "ok" in result.stdout, result.stderr
