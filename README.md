# Content Engine

Automated SEO content pipeline for clients. Four agents, one shared Google Sheet per client:

| Agent | Skill | What it does | Cadence |
|---|---|---|---|
| 1. Strategist | `/seo-audit` | DataForSEO audit (search + LLM visibility), prioritized keyword list, 30-day content calendar → Google Sheet | On onboarding + monthly |
| 2. Writer | `/write-article` | Picks next `planned` calendar row, researches the live SERP, writes the article, runs the AI-writing-filter editing pass | Daily |
| 3. Designer | `/infographics` | Authors branded HTML/SVG infographics for the article, renders to PNG | Daily (after 2) |
| 4. Publisher | `/publish` | Uploads images + article to the client's WordPress or Wix as a draft (or live), writes the URL back to the Sheet | Daily (after 3) |
| 5. Linker | `/internal-links` | Edits 2-3 existing live articles to add contextual links to the new one (+ backfills outbound links); exact-match edits only, all changes logged | Daily (after 4, live posts only) |

`/run-pipeline` chains 2 → 3 → 4 → 5 for every active client. Agent 1 runs standalone.

## State model

Each client has one Google Spreadsheet with two tabs:

- **Keywords** — `keyword, volume, difficulty, intent, cpc, priority_score, source, notes`
- **Calendar** — `date, title, primary_keyword, secondary_keywords, intent, outline, status, work_dir, published_url, notes`

`status` flows: `planned → written → designed → published → linked` (or `error:<note>`). Every agent claims work by status, so agents are idempotent and re-runnable.

Working files live in `work/<client>/<YYYY-MM-DD>-<slug>/`: `article.md`, `meta.yaml` (title, description, slug, tags), `images/*.png`.

## Setup (one-time)

1. **Python deps**: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
2. **Google Sheets service account**:
   - In Google Cloud Console create a project → enable *Google Sheets API* and *Google Drive API* → create a **service account** → download its JSON key.
   - Save it as `secrets/service-account.json` (gitignored).
   - Share each client spreadsheet with the service account's email (Editor).
3. **DataForSEO**: already wired via the `dfs-mcp` MCP server. Also put the same login/password in `.env` (`DATAFORSEO_LOGIN/PASSWORD`) so scripts can call the REST API directly in headless runs.
4. **Per-client credentials**: copy `clients/_template.yaml` → `clients/<client>.yaml`, fill it in, and add the referenced secrets to `.env`.
   - WordPress: create an **Application Password** for a user with Editor role (WP Admin → Users → Profile → Application Passwords).
   - Wix: create an **API key** with Blog + Media permissions (https://manage.wix.com/account/api-keys) and note the **Site ID** (Dashboard URL contains it).
5. **Copy `.env.example` → `.env`** and fill in every secret referenced by client configs.

## Onboarding a new client

```
claude "Onboard clients/acme.yaml: run /seo-audit for it, create the spreadsheet if missing"
```

Agent 1 creates/fills the Keywords + Calendar tabs and writes an audit report to `work/<client>/audit-<date>.md`. Review the calendar with the client, adjust rows freely in the Sheet — agents only touch rows by status.

## Daily run

Manual: `claude "/run-pipeline"` from this directory.

Scheduled (macOS cron, 7am daily):
```
crontab -e
0 7 * * * cd /Users/your-name/content-engine && /usr/local/bin/claude -p "/run-pipeline" --permission-mode acceptEdits >> work/cron.log 2>&1
```
Note: headless runs need the MCP servers configured at user scope (`claude mcp list` to verify dfs-mcp is available outside this app session) and pre-approved tool permissions — see `.claude/settings.json`.

## Safety defaults

- Publisher posts as **draft** unless `publishing.mode: live` in the client yaml.
- Every sheet write is scoped to one row + status transition; nothing is deleted.
- All secrets live in `.env` / `secrets/`, never in client yamls or the Sheet.

## Migrating Agent 2 from Dust

Open `.claude/skills/write-article/SKILL.md` and paste your Dust agent's instructions into the marked **BRAND VOICE / DUST PROMPT** section (per-client overrides go in `clients/<client>.yaml` under `voice:`). The skill already handles calendar I/O, SERP research, and the AI-filter editing pass around it.
