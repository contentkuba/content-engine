#!/bin/bash
# Sync the content engine from this Mac to the VPS. Usage:
#   bash deploy/deploy.sh <ssh-host>          # e.g. bash deploy/deploy.sh ovh
# Includes .env and secrets/ (the VPS needs them) — transfer is over SSH.
set -e
HOST="${1:?usage: deploy.sh <ssh-host>}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"

# work/ is included: `written` backlog rows point at article files that must travel
# with the state. Logs stay machine-local.
rsync -az --delete \
  --exclude '.venv/' \
  --exclude 'site/' \
  --exclude '__pycache__/' \
  --exclude 'work/cron.log' \
  --exclude 'work/launchd-stderr.log' \
  "$SRC/" "$HOST:content-engine/"

echo "synced to $HOST:content-engine/"
echo "first time? now run:  ssh $HOST 'bash content-engine/deploy/vps-setup.sh'"
