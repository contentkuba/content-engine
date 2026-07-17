---
name: seo-audit
description: "Agent 1 — audit a client's search + LLM visibility via DataForSEO, build a prioritized keyword list and a content calendar in their Google Sheet. Use on client onboarding or for the monthly refresh. Args: path to clients/<client>.yaml"
---

# Agent 1 — SEO & LLM Visibility Audit → Keyword List → Content Calendar

Input: a client config (`clients/<client>.yaml`). Read it first. All DataForSEO calls use the client's `market.location_name` / `language_code`. If the dfs-mcp MCP tools are unavailable (headless run), call the DataForSEO REST API directly with `DATAFORSEO_LOGIN/PASSWORD` from `.env` (basic auth, `https://api.dataforseo.com/v3/...` — same endpoint names as the tools).

## Phase 1 — Baseline audit

1. **Domain overview**: `dataforseo_labs_google_domain_rank_overview` + `dataforseo_labs_google_ranked_keywords` (limit 300, organic) — what they already rank for, and where (positions 1-3 / 4-10 / 11-30 buckets).
2. **Technical spot-check**: `on_page_instant_pages` on the homepage and blog index; `on_page_lighthouse` on the homepage. Note only blocking issues (noindex, broken canonicals, catastrophic CWV) — this is not a full tech audit.
3. **Backlink position**: `backlinks_summary` for the domain and each competitor — establishes realistic difficulty ceiling.
4. **LLM visibility** (the differentiator — always include):
   - `ai_opt_llm_ment_search` for the brand name and domain — where do LLMs mention them today?
   - `ai_optimization_llm_response`: ask 5-8 buyer-intent questions ("best <category> for <audience>", "how to <core job>") across available models; record whether client vs competitors are cited.
   - `ai_optimization_keyword_data_search_volume` on the seed topics — AI-search demand signal.

## Phase 2 — Keyword universe

1. Expand `business.seed_topics` with `dataforseo_labs_google_keyword_suggestions` (full-text match) per seed cluster — limit ≤50, filter search_volume > 30, order by volume desc. Do NOT rely on `keyword_ideas` for niche technical topics: it matches by product category and returns garbage for generic seeds (verified 2026-07-12 — "end of life" seeds returned song lyrics). If you do try it, sanity-check the first 10 results before using any of them.
2. Competitor gaps: `dataforseo_labs_google_domain_intersection` (competitor vs client, `intersections: false`) for each competitor — keywords they rank for, client doesn't.
3. Enrich the merged deduped set: `dataforseo_labs_bulk_keyword_difficulty` (batches of ≤1000) and `dataforseo_labs_search_intent`.

## Phase 3 — Prioritize

Score each keyword 0-100:
- **Opportunity** = normalized `volume × intent_weight` (transactional/commercial 1.0, informational 0.7, navigational 0.1)
- **Winnability** = inverse difficulty, shifted by domain strength (if client backlink rank is far below the top-10 median, penalize KD > 40 hard)
- **Relevance** = your judgment against `business.what/audience/goals` (0/0.5/1 — be strict; kill anything the client couldn't credibly write)
- `priority_score = 0.4·opportunity + 0.35·winnability + 0.25·relevance·100`

Keep the top ~60. Write ALL of them to the **Keywords** tab (sorted desc) via `scripts/sheets.py`.

## Phase 4 — Content calendar

Build `articles_per_week × ~6 weeks` rows for the **Calendar** tab:
- Cluster keywords into articles (1 primary + 2-4 secondaries each). One intent per article.
- Sequence: quick wins (high winnability) first two weeks, then pillar pieces, interleave intents.
- Weekday dates starting `calendar.start_date` (default next Monday).
- Each row: proposed `title` (compelling, keyword-natural), `outline` (4-6 H2s, one sentence each, informed by what currently ranks — spot-check 2-3 SERPs with `serp_organic_live_advanced` for the biggest clusters), `status=planned`.

## Phase 5 — Deliverables

1. Sheet writes (create spreadsheet + tabs first if `sheet.spreadsheet_id` is empty — use `scripts/sheets.py create`, then tell the user to paste the new ID into the client yaml and share it with the client).
2. Audit report at `work/<client>/audit-<YYYY-MM-DD>.md`: current rankings snapshot, technical flags, backlink position vs competitors, **LLM visibility findings** (which models mention them, for what, vs competitors), keyword strategy rationale, and the calendar summary. Written for the client — plain language, no tool names.

Sheet I/O is always through `scripts/sheets.py` (see `--help`). Never restructure existing tabs; append/update only.
