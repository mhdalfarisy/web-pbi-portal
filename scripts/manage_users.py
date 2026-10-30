"""Kelola akun MANTRA dari server (butuh akses ke folder aplikasi). Semua perubahan tercatat di audit log.

Pemakaian:
    python scripts/manage_users.py seed                       akun awal (Super Admin, User A, User B); aman dijalankan ulang
    python scripts/manage_users.py seed --generate            sama, tapi password sementara acak & unik per akun
    python scripts/manage_users.py list
    python scripts/manage_users.py create --email x@merdeka.com --dashboard material-readiness
    python scripts/manage_users.py set-access --email x@merdeka.com --dashboard pani-processing
    python scripts/manage_users.py reset-password --email x@merdeka.com
    python scripts/manage_users.py set-active --email x@merdeka.com --inactive
    python scripts/manage_users.py set-role --email x@merdeka.com --role super_admin
    python scripts/manage_users.py backup                     salin instance/mantra.db ke instance/backups/

Password awal `seed` diambil dari environment variable MANTRA_SEED_PASSWORD (atau ditanyakan di terminal), tidak
pernah ditulis ke file atau log. Semua password awal/reset bersifat sementara: user wajib menggantinya saat login.
Role super_admin hanya bisa diberikan lewat script ini (tidak ada tombolnya di halaman web).
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mantra import create_app  # noqa: E402
from mantra.core import accounts, db  # noqa: E402

# Akun awal. Hak akses dashboard hanya diberikan saat akun DIBUAT; seed ulang tidak mengubah akun yang sudah ada.
SEED = [
    ("pbi_premium@merdeka.com", "Super Admin", "super_admin", []),
    ("pbi_pro_a@merdeka.com", "User A", "user", ["material-readiness"]),
    ("pbi_pro_b@merdeka.com", "User B", "user", ["pani-processing"]),
]
SEED_MIN_LENGTH = 6  # password sementara (tetap wajib diganti); password permanen mengikuti accounts.password_problem


def _actor():
    return {"db_id": None, "email": f"cli:{getpass.getuser()}"}


def _user(email):
    row = accounts.get_user_by_email(email)
    if row is None:
        sys.exit(f"User {email} tidak ditemukan.")
    return row


def _seed_password():
    password = os.environ.get("MANTRA_SEED_PASSWORD")
    if not password and sys.stdin.isatty():
        password = getpass.getpass("Password sementara untuk akun awal: ")
        if password != getpass.getpass("Ulangi: "):
            sys.exit("Password tidak sama.")
    if not password:
        sys.exit("Isi MANTRA_SEED_PASSWORD, jalankan di terminal interaktif, atau pakai --generate.")
    if len(password) < SEED_MIN_LENGTH:
        sys.exit(f"Password sementara minimal {SEED_MIN_LENGTH} karakter.")
    return password


def cmd_seed(args):
    shared = None if args.generate else _seed_password()
    for email, name, role, slugs in SEED:
        row = accounts.get_user_by_email(email)
        if row is not None:
            note = "" if row["role"] == role else f" (role sekarang {row['role']}, seed menyarankan {role}; tidak diubah)"
            print(f"  ada     {email}: tidak diubah{note}")
            continue
        password = shared or accounts.temporary_password()
        user_id = accounts.create_user(email, name, password, role=role, actor=_actor())
        if slugs:
            accounts.set_access(user_id, accounts.dashboard_ids_for(slugs), actor=_actor())
        shown = f", password sementara: {password}" if args.generate else ""
        print(f"  dibuat  {email} [{role}] akses: {', '.join(slugs) or 'semua dashboard aktif'}{shown}")
    print("Password awal bersifat sementara; setiap akun wajib menggantinya saat login pertama.")


def cmd_list(args):
    for r in accounts.list_users():
        u = r["user"]
        access = "semua dashboard aktif" if u["role"] == "super_admin" else ", ".join(d["slug"] for d in r["dashboards"]) or "-"
        status = "aktif" if u["is_active"] else "NONAKTIF"
        flag = " | wajib ganti password" if u["must_change_password"] else ""
        print(f"  {u['id']:>3}  {u['email']:<32} {u['role']:<12} {status:<9} {access}{flag}")


def cmd_create(args):
    password = accounts.temporary_password()
    user_id = accounts.create_user(args.email, args.name, password, role="user", actor=_actor())
    accounts.set_access(user_id, accounts.dashboard_ids_for(args.dashboard), actor=_actor())
    print(f"Dibuat {accounts.normalize_email(args.email)}, password sementara: {password}")


def cmd_set_access(args):
    row = _user(args.email)
    granted, revoked = accounts.set_access(row["id"], accounts.dashboard_ids_for(args.dashboard), actor=_actor())
    print(f"Diberi: {', '.join(granted) or '-'} | dicabut: {', '.join(revoked) or '-'}")


def cmd_reset_password(args):
    row = _user(args.email)
    password = accounts.temporary_password()
    accounts.set_password(row["id"], password, must_change=True, actor=_actor(), action="password_reset")
    print(f"Password sementara {row['email']}: {password}  (semua sesinya sudah logout)")


def cmd_set_active(args):
    row = _user(args.email)
    accounts.set_active(row["id"], not args.inactive, actor=_actor())
    print(f"{row['email']} sekarang {'nonaktif' if args.inactive else 'aktif'}.")


def cmd_set_role(args):
    row = _user(args.email)
    if args.role == "super_admin" and not args.yes:
        answer = input(f"Jadikan {row['email']} Super Admin (akses penuh ke semua dashboard & akun)? Ketik 'ya': ")
        if answer.strip().lower() != "ya":
            sys.exit("Dibatalkan.")
    accounts.set_role(row["id"], args.role, actor=_actor())
    print(f"Role {row['email']}: {row['role']} -> {args.role} (sesinya sudah logout)")


def cmd_backup(args, app):
    conn = db.connect(app.config["APP_DB"])
    try:
        print(f"Backup: {db.backup(conn, app.config['INSTANCE_DIR'] / 'backups', 'manual')}")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Kelola akun MANTRA")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("seed")
    p.add_argument("--generate", action="store_true", help="password sementara acak & unik per akun (dicetak sekali)")
    sub.add_parser("list")
    p = sub.add_parser("create")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--dashboard", action="append", default=[], help="slug dashboard, boleh diulang")
    p = sub.add_parser("set-access")
    p.add_argument("--email", required=True)
    p.add_argument("--dashboard", action="append", default=[], help="daftar akses BARU (menggantikan yang lama)")
    p = sub.add_parser("reset-password")
    p.add_argument("--email", required=True)
    p = sub.add_parser("set-active")
    p.add_argument("--email", required=True)
    p.add_argument("--inactive", action="store_true", help="nonaktifkan (tanpa flag ini = aktifkan)")
    p = sub.add_parser("set-role")
    p.add_argument("--email", required=True)
    p.add_argument("--role", required=True, choices=sorted(accounts.ROLES))
    p.add_argument("--yes", action="store_true", help="lewati konfirmasi")
    sub.add_parser("backup")
    args = parser.parse_args()

    app = create_app()  # memasang migrasi yang belum jalan (dengan backup) dan menyamakan katalog dashboard
    with app.app_context():
        try:
            if args.cmd == "backup":
                cmd_backup(args, app)
            else:
                globals()["cmd_" + args.cmd.replace("-", "_")](args)
        except accounts.AccountError as exc:
            sys.exit(f"Gagal: {exc}")


if __name__ == "__main__":
    main()
