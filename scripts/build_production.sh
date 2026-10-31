#!/usr/bin/env bash
# Buat paket production (hanya file yang dibutuhkan website jalan; tanpa docs, tests, alat developer, .env, database).
#
#   scripts/build_production.sh ../web-pbi-portal-dashboard
#
# Folder tujuan DIHAPUS lalu dibuat ulang setiap kali script ini dijalankan: jangan mengedit isinya dengan tangan.
# Perbaikan selalu di web-pbi-portal, tes di localhost, lalu jalankan script ini lagi.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:?Pakai: scripts/build_production.sh <folder-tujuan>}"
mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

case "$TARGET" in
  "$ROOT"|"$ROOT"/*) echo "Folder tujuan tidak boleh di dalam $ROOT" >&2; exit 1 ;;
esac

# Isi folder tujuan dihapus dulu supaya file yang sudah dihapus di web-pbi-portal tidak tertinggal. .git dipertahankan:
# folder tujuan boleh berupa repo git paket production (riwayat rilis), commit & push dilakukan setelah build.
find "$TARGET" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +

# 1. Kode aplikasi, tanpa bahan generator dashboard (_template) dan pertanyaan acuan AI (chat_cases.py, hanya untuk
#    scripts/check_ai_agent.py). prompts/*.md TETAP ikut: dibaca AI agent saat aplikasi jalan.
rsync -a "$ROOT/mantra" "$TARGET/" \
  --exclude "__pycache__/" --exclude "*.pyc" --exclude ".DS_Store" \
  --exclude "dashboards/_template/" --exclude "chat_cases.py"

# 2. Entry point server, daftar library, dan 2 script yang dibutuhkan di server
cp "$ROOT/wsgi.py" "$ROOT/gunicorn.conf.py" "$ROOT/requirements.txt" "$TARGET/"
mkdir -p "$TARGET/scripts"
cp "$ROOT/scripts/manage_users.py" "$ROOT/scripts/check_setup.py" "$TARGET/scripts/"

# .gitignore untuk repo paket: secret, database, dan cache yang muncul saat paket dites tidak boleh ikut ter-commit
printf '.env\n.venv/\ninstance/\n__pycache__/\n*.pyc\n.DS_Store\n' > "$TARGET/.gitignore"

# 3. Contoh .env untuk server (nilai rahasia diisi tim infra di server, file asli di /etc/mantra/mantra.env)
cat > "$TARGET/.env.example" <<'EOF'
# Pengaturan server MANTRA. Salin ke /etc/mantra/mantra.env (izin 600), isi nilai yang kosong.
# systemd: Environment=MANTRA_ENV_FILE=/etc/mantra/mantra.env
APP_ENV=production
FLASK_SECRET_KEY=
SESSION_COOKIE_SECURE=1
TRUST_PROXY=1
DASHBOARD_STRICT=0
MANTRA_INSTANCE_DIR=/var/lib/mantra
SESSION_HOURS=8
PORT=5001
GUNICORN_THREADS=16
LOG_LEVEL=INFO

ENTRA_TENANT_ID=
ENTRA_CLIENT_ID=
ENTRA_CLIENT_SECRET=

PBI_TENANT_ID=
PBI_CLIENT_ID=
PBI_CLIENT_SECRET=
PBI_MAX_QUERIES_PER_MINUTE=100
PBI_TIMEOUT_SECONDS=120
CACHE_MINUTES=10

AI_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
GEMINI_FALLBACK_MODELS=gemini-3.1-flash-lite,gemini-flash-latest
CHAT_MAX_PER_MINUTE=10
EOF

# 4. Versi: commit asal paket. "-belum-commit" = ada perubahan yang belum di-commit ikut terbawa (jangan dirilis)
cd "$ROOT"
VERSION="$(git describe --tags --always 2>/dev/null || echo tanpa-git)"
[ -n "$(git status --porcelain 2>/dev/null)" ] && VERSION="$VERSION-belum-commit"
# Tanpa jam build: kode yang sama menghasilkan paket yang sama persis (tidak ada commit rilis kosong)
printf '%s  %s\n' "$VERSION" "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" > "$TARGET/VERSION"

# 5. Pengaman: tidak boleh ada secret, database, dokumentasi, atau test di paket
bad="$(cd "$TARGET" && find . -path ./.git -prune -o \( -name ".env"-o -name "*.db" -o -name "*.db-wal" -o -name "docs" -o -name "tests" \
  -o -name "README*" -o -name "run.py" -o -name ".venv" -o -name "instance" \) -print)"
if [ -n "$bad" ]; then
  echo "Paket berisi file yang tidak boleh ikut:" >&2; echo "$bad" >&2; exit 1
fi

echo "Paket production: $TARGET"
echo "Versi: $(cat "$TARGET/VERSION")"
echo "Isi: $(find "$TARGET" -type f | wc -l | tr -d ' ') file, $(du -sh "$TARGET" | cut -f1)"
