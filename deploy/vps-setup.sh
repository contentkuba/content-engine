#!/bin/bash
# One-time VPS setup for the content engine (Debian/Ubuntu).
# Run ON THE VPS as your normal user (not root), from inside ~/content-engine:
#   bash deploy/vps-setup.sh
set -e

echo "== 1/5 system packages =="
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip curl chromium-browser 2>/dev/null \
  || sudo apt-get install -y -qq python3-venv python3-pip curl chromium

echo "== 2/5 timezone (cron runs at 07:00 local) =="
sudo timedatectl set-timezone Europe/Warsaw

echo "== 3/5 claude cli =="
if ! command -v claude >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/claude" ]; then
  curl -fsSL https://claude.ai/install.sh | bash
fi
export PATH="$HOME/.local/bin:$PATH"
claude --version

echo "== 4/5 python venv =="
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
chmod +x scripts/run_daily.sh

echo "== 5/5 cron (weekdays 07:00) =="
{ crontab -l 2>/dev/null | grep -v "content-engine/scripts/run_daily.sh" || true ; \
  echo "0 7 * * 1-5 $HOME/content-engine/scripts/run_daily.sh" ; } | crontab -
crontab -l

cat <<'EOF'

Setup done. Two manual steps remain (one-time):

1. Authenticate Claude Code on this box (credentials persist in a file on Linux):
     claude login
   (or `claude setup-token` for a long-lived headless token)

2. Smoke test:
     cd ~/content-engine && .venv/bin/python scripts/dfs.py dataforseo_labs/google/keyword_overview/live \
       '{"keywords":["test"],"location_name":"United States","language_code":"en"}' | head -c 200
     ~/content-engine/scripts/run_daily.sh    # full pipeline test run

Note: DataForSEO runs through the REST fallback (scripts/dfs.py) on this box —
no MCP server needed; the skills fall back automatically.
EOF
