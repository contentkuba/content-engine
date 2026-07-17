#!/bin/bash
# Daily pipeline wrapper (macOS launchd + Linux cron compatible):
# wait for network, keep machine awake if possible, run, retry once on failure.
cd "$(dirname "$0")/.." || exit 1
LOG=work/cron.log

# concurrency guard: never allow two pipeline runs against the same sheet/work dir
exec 9>"work/.pipeline.lock"
if ! flock -n 9; then
  echo "--- run_daily $(date '+%Y-%m-%d %H:%M:%S'): another run holds the lock, exiting" >> "$LOG"
  exit 0
fi

echo "--- run_daily $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG"

CLAUDE_BIN=$(command -v claude || echo "$HOME/.local/bin/claude")
KEEPAWAKE=""
command -v caffeinate >/dev/null 2>&1 && KEEPAWAKE="caffeinate -is"

# wait up to 10 minutes for the API to be reachable (machine may have just woken up)
for i in $(seq 1 60); do
  curl -s -o /dev/null -m 5 https://api.anthropic.com && break
  sleep 10
done

# identity for the agent: you were launched by the scheduler and you hold the lock
export CONTENT_ENGINE_SCHEDULED_RUN="$(date '+%Y-%m-%dT%H:%M:%S')-pid$$"

for attempt in 1 2; do
  $KEEPAWAKE "$CLAUDE_BIN" -p "/run-pipeline" --permission-mode acceptEdits >> "$LOG" 2>&1 && exit 0
  echo "attempt $attempt failed ($(date '+%H:%M:%S')), retrying in 5 min" >> "$LOG"
  sleep 300
done
echo "run_daily: both attempts failed $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG"
exit 1
