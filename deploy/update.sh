#!/usr/bin/env bash
# Pull-based deploy, run every 5 minutes by traveldeal-update.timer.
# Deploys the newest commit on main only after its GitHub checks have passed,
# so nothing needs inbound SSH from GitHub and a broken commit never goes live.
set -euo pipefail

APP_DIR=/opt/traveldeal
cd "$APP_DIR"
# shellcheck disable=SC1091
REPO=$(grep -E '^GITHUB_REPO=' deploy/.env | cut -d= -f2)

git fetch --quiet origin main
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)
[ "$LOCAL" = "$REMOTE" ] && exit 0

# Every check run for the commit must have finished successfully (or been skipped).
CHECKS=$(curl -fsS -H "Accept: application/vnd.github+json" "https://api.github.com/repos/$REPO/commits/$REMOTE/check-runs")
TOTAL=$(echo "$CHECKS" | jq '.total_count')
PENDING=$(echo "$CHECKS" | jq '[.check_runs[] | select(.status != "completed")] | length')
FAILED=$(echo "$CHECKS" | jq '[.check_runs[] | select(.status == "completed" and (.conclusion | IN("success","skipped","neutral") | not))] | length')
if [ "$TOTAL" -eq 0 ] || [ "$PENDING" -gt 0 ]; then
  echo "Commit $REMOTE: checks not finished yet; will retry."
  exit 0
fi
if [ "$FAILED" -gt 0 ]; then
  echo "Commit $REMOTE: $FAILED check(s) failed; not deploying."
  exit 0
fi

echo "Deploying $REMOTE (was $LOCAL)"
git reset --hard --quiet "$REMOTE"
deploy/compose.sh up -d --build --remove-orphans
docker image prune -f >/dev/null
echo "Deployed $REMOTE"
