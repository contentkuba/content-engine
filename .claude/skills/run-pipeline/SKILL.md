---
name: run-pipeline
description: "Daily orchestrator — for every active client run write-article, then infographics, then publish, and report a per-client summary. Use for the scheduled daily run or 'run the pipeline'."
---

# Daily Pipeline

**Concurrency & identity:** `scripts/run_daily.sh` takes an exclusive `flock` on `work/.pipeline.lock` before launching you and exports `CONTENT_ENGINE_SCHEDULED_RUN`. If that variable is set in your environment (`echo $CONTENT_ENGINE_SCHEDULED_RUN`), you ARE the scheduled pipeline and you hold the lock — proceed. Do NOT stand down because other claude processes appear in `ps`; a previous run misidentified itself that way and silently skipped a day. The lock, not process-table inference, is the arbiter.

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
