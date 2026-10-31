#!/usr/bin/env bash
# Rilis MANTRA ke server (staging dulu, baru live):
#
#   scripts/release.sh staging   build paket dari commit terakhir web-pbi-portal, push ke branch staging
#                                repo test-prod-pbi-apps, lalu update https://staging.43-173-42-175.sslip.io
#   scripts/release.sh live      naikkan versi yang SAMA PERSIS dengan staging ke branch main, lalu update
#                                https://43-173-42-175.sslip.io
#
# Server bisa diganti lewat MANTRA_SERVER=ubuntu@<ip>. Butuh SSH key laptop sudah terpasang di server.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG="$(cd "$ROOT/.." && pwd)/web-pbi-portal-dashboard"
SERVER="${MANTRA_SERVER:-ubuntu@43.173.42.175}"

case "${1:-}" in
  staging)
    if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
      echo "Ada perubahan yang belum di-commit di web-pbi-portal. Tes, commit, dan push dulu." >&2
      exit 1
    fi
    COMMIT="$(git -C "$ROOT" rev-parse --short HEAD)"
    "$ROOT/scripts/build_production.sh" "$PKG" >/dev/null
    cd "$PKG"
    git add -A
    if git diff --cached --quiet; then
      echo "Paket tidak berubah dari rilis sebelumnya."
    else
      git commit -q -m "Release $COMMIT"
      echo "Paket baru: Release $COMMIT"
    fi
    git push -q origin HEAD:staging
    ssh "$SERVER" mantra-update staging
    echo "Coba di https://staging.43-173-42-175.sslip.io lalu, kalau aman: scripts/release.sh live"
    ;;
  live)
    cd "$PKG"
    git fetch -q origin
    echo "Naik ke live: $(git log --oneline -1 origin/staging)"
    # Push tanpa --force: ditolak kalau main punya commit yang tidak ada di staging (live hanya menerima versi
    # yang sudah lewat staging)
    git push -q origin origin/staging:main
    ssh "$SERVER" mantra-update live
    ;;
  *)
    echo "Pakai: scripts/release.sh staging | scripts/release.sh live" >&2
    exit 1
    ;;
esac
