#!/usr/bin/env bash
# scripts/deploy_vps.sh
# One-shot deploy for a fresh Ubuntu 22.04 NYC VPS.
# Run as a sudoer: ./scripts/deploy_vps.sh

set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/asklivermore-trading-bot}"
SERVICE_NAME="asklivermore-bot"

echo "==> installing docker + compose"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi
if ! docker compose version >/dev/null 2>&1; then
  sudo apt-get update && sudo apt-get install -y docker-compose-plugin
fi

echo "==> ensuring repo at $REPO_DIR"
if [ ! -d "$REPO_DIR" ]; then
  sudo git clone https://github.com/BuckeyeBizHub/asklivermore-trading-bot.git "$REPO_DIR"
  sudo chown -R "$USER":"$USER" "$REPO_DIR"
fi
cd "$REPO_DIR"

echo "==> .env check"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "EDIT $REPO_DIR/.env with your API keys, then re-run this script."
  exit 1
fi

echo "==> installing systemd unit"
sudo tee /etc/systemd/system/${SERVICE_NAME}.service >/dev/null <<EOF
[Unit]
Description=AskLivermore Trading Bot
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=simple
WorkingDirectory=${REPO_DIR}
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now ${SERVICE_NAME}.service
sudo systemctl status ${SERVICE_NAME}.service --no-pager

echo "==> log rotation"
sudo tee /etc/logrotate.d/${SERVICE_NAME} >/dev/null <<EOF
${REPO_DIR}/data/journal/*.jsonl {
  weekly
  rotate 12
  compress
  missingok
  notifempty
}
EOF

echo "==> done. live logs: journalctl -u ${SERVICE_NAME} -f"
