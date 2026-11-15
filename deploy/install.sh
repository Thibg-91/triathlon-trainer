#!/usr/bin/env bash
# Installe (ou met à jour) Triathlon Trainer sur un Raspberry Pi / Debian.
#
# À lancer depuis le dépôt cloné, avec un utilisateur qui a sudo :
#     ./deploy/install.sh            # installation / mise à jour
#     ./deploy/install.sh --serve    # + publication HTTPS via Tailscale Serve
#
# Le script est idempotent : relance-le après chaque `git pull`.
set -euo pipefail

APP_NAME="triathlon-trainer"
APP_USER="triathlon"
APP_DIR="/opt/${APP_NAME}"
DATA_DIR="/var/lib/${APP_NAME}"
PORT="${TRI_PORT:-8000}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SERVE=0
for arg in "$@"; do
    case "$arg" in
        --serve) SERVE=1 ;;
        -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
        *) echo "Option inconnue : $arg" >&2; exit 2 ;;
    esac
done

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }

[[ $EUID -eq 0 ]] && SUDO="" || SUDO="sudo"

step "Vérifications"
arch="$(uname -m)"
if [[ "$arch" != "aarch64" && "$arch" != "x86_64" ]]; then
    warn "Architecture $arch : un OS 64 bits (Raspberry Pi OS 64-bit) est recommandé."
fi
python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    sys.exit(f"Python 3.11+ requis (trouvé {sys.version.split()[0]}). Utilise Raspberry Pi OS Bookworm ou plus récent.")
print(f"Python {sys.version.split()[0]} OK")
PY

step "Paquets système"
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq python3-venv rsync curl >/dev/null

step "Utilisateur système '${APP_USER}'"
if ! id "$APP_USER" &>/dev/null; then
    $SUDO useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi
$SUDO install -d -o "$APP_USER" -g "$APP_USER" -m 750 "$DATA_DIR" "$DATA_DIR/backups"

step "Copie de l'application dans ${APP_DIR}"
$SUDO install -d -m 755 "$APP_DIR"
# .venv est exclu : il est conservé entre deux mises à jour
$SUDO rsync -a --delete \
    --exclude '.git' --exclude '.venv' --exclude 'data' --exclude '*.egg-info' \
    --exclude '__pycache__' --exclude '.pytest_cache' \
    "$REPO_DIR"/ "$APP_DIR"/
$SUDO chmod 755 "$APP_DIR/deploy/backup.sh" "$APP_DIR/deploy/restore.sh"

step "Environnement Python"
[[ -x "$APP_DIR/.venv/bin/python" ]] || $SUDO python3 -m venv "$APP_DIR/.venv"
$SUDO "$APP_DIR/.venv/bin/pip" install -q --upgrade pip
$SUDO "$APP_DIR/.venv/bin/pip" install -q -e "$APP_DIR"

step "Services systemd"
for unit in "$APP_NAME.service" "$APP_NAME-backup.service" "$APP_NAME-backup.timer"; do
    $SUDO install -m 644 "$APP_DIR/deploy/systemd/$unit" "/etc/systemd/system/$unit"
done
if [[ ! -f "/etc/default/$APP_NAME" ]]; then
    $SUDO install -m 644 "$APP_DIR/deploy/triathlon-trainer.env" "/etc/default/$APP_NAME"
fi
# Le port réellement utilisé est celui de /etc/default/triathlon-trainer
# shellcheck source=/dev/null
PORT="$( (set +u; . "/etc/default/$APP_NAME"; echo "${TRI_PORT:-$PORT}") )"
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now "$APP_NAME-backup.timer" >/dev/null
$SUDO systemctl enable "$APP_NAME.service" >/dev/null
$SUDO systemctl restart "$APP_NAME.service"

step "Vérification du démarrage"
for _ in $(seq 1 20); do
    if curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
        echo "L'appli répond sur http://127.0.0.1:${PORT}"
        break
    fi
    sleep 1
done
if ! curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
    warn "L'appli ne répond pas. Logs : sudo journalctl -u ${APP_NAME} -n 50"
    exit 1
fi

if [[ $SERVE -eq 1 ]]; then
    step "Publication HTTPS via Tailscale Serve"
    if ! command -v tailscale >/dev/null; then
        warn "Tailscale n'est pas installé : curl -fsSL https://tailscale.com/install.sh | sh"
        exit 1
    fi
    # --bg : persiste après redémarrage du Pi
    $SUDO tailscale serve --bg "http://127.0.0.1:${PORT}"
    $SUDO tailscale serve status
fi

step "Terminé"
cat <<EOF
- Logs          : sudo journalctl -u ${APP_NAME} -f
- Redémarrer    : sudo systemctl restart ${APP_NAME}
- Sauvegardes   : ${DATA_DIR}/backups (chaque nuit, 30 jours)
- Mise à jour   : git pull && ./deploy/install.sh
EOF
if [[ $SERVE -eq 0 ]]; then
    echo "- Accès distant : voir docs/raspberry-pi.md (Tailscale), puis ./deploy/install.sh --serve"
fi
