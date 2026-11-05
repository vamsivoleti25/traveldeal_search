#!/usr/bin/env bash
# docker compose, with the profiles chosen in deploy/.env applied.
#   COMPOSE_PROFILES=          private: app only, reach it through an SSH tunnel
#   COMPOSE_PROFILES=public    also start Caddy for HTTPS on your domain
# Usage (from anywhere):  deploy/compose.sh up -d --build
set -euo pipefail
cd "$(dirname "$0")/.."
PROFILES=$( (grep -E '^COMPOSE_PROFILES=' deploy/.env 2>/dev/null || true) | tail -n1 | cut -d= -f2- )
COMPOSE_PROFILES="$PROFILES" exec docker compose "$@"
