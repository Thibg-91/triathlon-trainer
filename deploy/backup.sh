#!/usr/bin/env bash
# Sauvegarde à chaud de la base SQLite (cohérente même si l'appli tourne),
# compressée, avec rotation.
#
# Variables :
#   TRI_DATA_DIR          dossier de données (défaut /var/lib/triathlon-trainer)
#   TRI_BACKUP_KEEP_DAYS  durée de conservation en jours (défaut 30)
set -euo pipefail

DATA_DIR="${TRI_DATA_DIR:-/var/lib/triathlon-trainer}"
DB="${DATA_DIR}/triathlon.db"
BACKUP_DIR="${DATA_DIR}/backups"
KEEP_DAYS="${TRI_BACKUP_KEEP_DAYS:-30}"

if [[ ! -f "$DB" ]]; then
    echo "Aucune base à sauvegarder ($DB)."
    exit 0
fi

mkdir -p "$BACKUP_DIR"
stamp="$(date +%Y-%m-%d_%H%M%S)"
target="${BACKUP_DIR}/triathlon-${stamp}.db"

# API de sauvegarde en ligne de SQLite via Python (pas besoin du binaire sqlite3)
python3 - "$DB" "$target" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
    s.backup(d)
with sqlite3.connect(dst) as d:
    ok = d.execute("PRAGMA integrity_check").fetchone()[0]
if ok != "ok":
    sys.exit(f"Sauvegarde corrompue : {ok}")
PY

gzip -f "$target"
find "$BACKUP_DIR" -name 'triathlon-*.db.gz' -type f -mtime +"$KEEP_DAYS" -delete

echo "Sauvegarde OK : ${target}.gz"
