#!/usr/bin/env bash
# Restaure une sauvegarde de la base.
#     sudo ./deploy/restore.sh /var/lib/triathlon-trainer/backups/triathlon-2026-11-20_033012.db.gz
set -euo pipefail

APP_NAME="triathlon-trainer"
APP_USER="triathlon"
DATA_DIR="${TRI_DATA_DIR:-/var/lib/${APP_NAME}}"
DB="${DATA_DIR}/triathlon.db"
BACKUP="${1:-}"

if [[ -z "$BACKUP" || ! -f "$BACKUP" ]]; then
    echo "Usage : sudo $0 <fichier .db ou .db.gz>" >&2
    echo "Sauvegardes disponibles :" >&2
    # shellcheck disable=SC2012
    ls -1t "${DATA_DIR}/backups" 2>/dev/null | head -10 >&2 || true
    exit 2
fi
if [[ $EUID -ne 0 ]]; then
    echo "À lancer avec sudo." >&2
    exit 1
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
if [[ "$BACKUP" == *.gz ]]; then gunzip -c "$BACKUP" > "$tmp"; else cp "$BACKUP" "$tmp"; fi

systemctl stop "$APP_NAME"
# Garde une copie de la base actuelle avant de l'écraser
[[ -f "$DB" ]] && cp -p "$DB" "${DB}.avant-restauration"
install -o "$APP_USER" -g "$APP_USER" -m 640 "$tmp" "$DB"
systemctl start "$APP_NAME"

echo "Base restaurée depuis $BACKUP (ancienne base : ${DB}.avant-restauration)"
