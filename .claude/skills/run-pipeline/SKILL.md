---
name: run-pipeline
description: "Daily orchestrator — for every active client run write-article, then infographics, then publish, and report a per-client summary. Use for the scheduled daily run or 'run the pipeline'."
---

# Daily Pipeline

**Concurrency & identity — decision table, not judgment call.** Two scheduled runs have now been lost to self-misidentification (2026-07-17: the agent thought it was a leftover interactive session; 2026-08-03: it saw its own process in `ps` and stood down deferring to itself). Therefore:

1. If your invocation includes `scheduled=<token>` (the wrapper passes it in the prompt), you ARE the scheduled run and `run_daily.sh` already holds the exclusive `flock` for you. **Proceed unconditionally.** Never inspect `ps` for other claude processes; any `claude -p /run-pipeline` you would find there is you.
2. If invoked without `scheduled=` (a human ran /run-pipeline): try `flock -n work/.pipeline.lock true`. If that fails, a real run is active — report that and stop. If it succeeds, proceed (your own stages don't hold the lock; that's acceptable for supervised manual runs).
3. Process-table inference is FORBIDDEN as an identity or concurrency signal in both cases. The lock and the prompt token are the only arbiters.

1. List `clients/*.yaml` (skip `_template.yaml` and any with `active: false`).
2. For each active client, run the three stages **in order**, each stage only if the previous succeeded for that client:
   1. `/write-article clients/<client>.yaml`
   2. `/infographics clients/<client>.yaml`
   3. `/publish clients/<client>.yaml`
   4. `/internal-links clients/<client>.yaml` (skipped if `internal_linking.enabled: false`)

   Stages are status-driven, so this also drains any backlog left by earlier failed runs: e.g. if yesterday's article got stuck at `written`, infographics picks it up today before the publish stage runs.

   **Backlog drain pass:** after the main sequence, check the Calendar: if any rows remain at `written` or `designed`, run the corresponding stages (infographics/publish/internal-links) one more round — at most one extra pass per day — so the backlog shrinks by one daily instead of holding steady.
3. A failure for one client never blocks the others — record it and continue.
4. Finish with a summary table: client | article title | final status | URL or error.
5. **Auto-refresh:** if any client's calendar has < 5 `planned` rows left, run `/seo-audit clients/<client>.yaml` for that client now, at the end of the run — do not just flag it. (Keep it lean: skip the technical spot-check and LLM-response sampling on auto-refreshes; keyword expansion + calendar extension + a short report are enough. A full audit still runs monthly or on demand.) Note the refresh in the summary.

Run stages for one client sequentially; different clients may be processed one after another (context is cheaper than debugging interleaved sheet writes).
