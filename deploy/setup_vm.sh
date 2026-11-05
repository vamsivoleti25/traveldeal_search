#!/usr/bin/env bash
# One-time setup of the OCI Always Free VM (Ubuntu 24.04, Ampere A1 / arm64).
# Run as the default "ubuntu" user:  bash deploy/setup_vm.sh
set -euo pipefail

APP_DIR=/opt/traveldeal

echo "==> Installing Docker, Compose, git, jq"
sudo apt-get update -y
sudo apt-get install -y docker.io docker-compose-v2 git jq netfilter-persistent
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

echo "==> Opening ports 80 and 443 in the host firewall"
# OCI's Ubuntu images ship iptables rules that only allow SSH. The VCN security list
# must ALSO allow 80/443 (see docs/DEPLOY_OCI.md).
for port in 80 443; do
  if ! sudo iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT 6 -p tcp --dport "$port" -m state --state NEW -j ACCEPT
  fi
done
sudo netfilter-persistent save

echo "==> Placing the app in $APP_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
  sudo mkdir -p "$APP_DIR"
  sudo chown "$USER":"$USER" "$APP_DIR"
  git clone https://github.com/vamsivoleti25/traveldeal_search.git "$APP_DIR"
fi

echo "==> Installing systemd timers (auto-deploy every 5 min, nightly backup)"
sudo cp "$APP_DIR"/deploy/systemd/*.service "$APP_DIR"/deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now traveldeal-update.timer traveldeal-backup.timer

cat <<MSG

Done. Next:
  1. cp $APP_DIR/deploy/env.example $APP_DIR/deploy/.env && chmod 600 $APP_DIR/deploy/.env   (fill it in)
  2. cp $APP_DIR/.streamlit/secrets.toml.example $APP_DIR/.streamlit/secrets.toml && chmod 600 $APP_DIR/.streamlit/secrets.toml
  3. Log out and back in (for the docker group), then:  cd $APP_DIR && docker compose up -d --build
MSG
