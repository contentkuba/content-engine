---
name: write-article
description: "Agent 2 — pick the next planned article from a client's content calendar, research the live SERP, write the article in the client's voice, run the AI-writing-filter editing pass, save to work/, mark the row written. Args: path to clients/<client>.yaml"
---

# Agent 2 — Article Writer + AI-Filter Editor

Input: client config path. Read it, then claim work:

```
.venv/bin/python scripts/sheets.py next --client clients/<client>.yaml --status planned
```

If no row is `planned`, say so and stop (suggest re-running /seo-audit if the calendar is exhausted). Otherwise you get the row: date, title, primary_keyword, secondary_keywords, intent, outline.

## 1. Research (don't skip)

- `serp_organic_live_advanced` for the primary keyword (client's market) — read the top 10 titles/descriptions. Headless runs without the dfs-mcp server: `.venv/bin/python scripts/dfs.py serp/google/organic/live/advanced '{"keyword":"...","location_name":"...","language_code":"en","depth":10}'`. Fetch the top 2-3 ranking pages with `on_page_content_parsing` or WebFetch. Note: angle, depth, what they all miss.
- The article must match the dominant SERP intent even if it differs from the calendar's `intent` guess — update the row's notes if so.
- Pull 2-4 verifiable facts/stats with sources; never invent statistics.

## 2. Write

Target: 1,200-1,800 words (informational) or 800-1,200 (commercial), markdown.

Structure: H1 = title (may refine the calendar title; keep primary keyword near the front) → direct-answer opening paragraph (2-3 sentences that would survive as a featured snippet / LLM citation) → H2s per outline (adjust freely based on research) → conclusion with the client's CTA.

SEO/LLM mechanics: primary keyword in H1, first 100 words, one H2, and naturally ~3-5×; secondaries each once in a heading or body; add one short FAQ section (3 questions) when informational — it doubles as LLM-quotable material. **Every FAQ question must be an H3 heading** (`### Question?`), never bold text — this is required for FAQ schema and AI extraction. Internal links: link 1-2 previously published articles from the Calendar tab (published_url column) where genuinely relevant.

### BRAND VOICE / DUST PROMPT
<!-- Per-client `voice:` in the yaml extends/overrides this section. -->

Follow these blog writing rules while writing the sections:

- Craft a precise, benefit-driven headline. Promise a clear outcome, avoid vagueness, and make the value immediately understandable.
- Deliver value early in the introduction. State the core insight, answer, or framework within the first section so readers gain immediate clarity even if they skim.
- Structure for scannability. Use short paragraphs, descriptive subheadings, bullet points, numbered lists, and clear section breaks to improve readability on mobile and desktop.
- Prioritize clarity over cleverness. Write in simple, direct language. Avoid filler, jargon, and unnecessary complexity.
- Add original insight. Include real examples, case observations, frameworks, data, or lived experience to differentiate the content from generic summaries.
- Demonstrate expertise and credibility. Reference reputable sources when needed, explain reasoning clearly, and show depth of understanding rather than repeating surface-level information. Use your search capability if needed.
- Optimize for both humans and AI systems. Use natural keyword placement, clear semantic structure, concise definitions, and answer-focused sections that are easy to extract and summarize.
- Follow core SEO fundamentals. Include the primary keyword in the headers.
- Maintain strong formatting standards. Use consistent heading hierarchy and accessible language.
- Keep paragraphs concise. Aim for tight, focused sections that communicate one idea at a time.

Formatting rules (apply to every article):

- Do not use en-dashes or em-dashes anywhere. Rewrite the sentence or use a comma, colon, or parentheses instead.
- Use only standard ASCII punctuation (hyphens, commas, periods, colons, semicolons, parentheses).
- Do not use smart quotes or curly quotes. Use only straight quotes (" and ').

Voice on top of the rules: write like a sharp practitioner explaining to a peer — first person plural for the brand, second person for the reader, concrete examples over abstractions, no filler intros.

## 3. AI-writing-filter editing pass (mandatory, separate pass)

First, invoke the AI writing filter skill (Skill tool: `anthropic-skills:linkedin-ai-writing-filter`) and apply its full workflow to the draft. If that skill is unavailable in this session, fall back to the checklist below — never skip the pass entirely.

Then (or as the fallback), re-read the full draft and rewrite every violation:

- **Kill AI tells**: "delve", "leverage", "crucial", "landscape", "in the realm of", "it's important to note", "furthermore/moreover" chains, "whether you're X or Y", rule-of-three adjective triplets, em-dash overuse, every paragraph ending in a summary sentence.
- **Kill symmetry**: vary paragraph lengths (1-sentence paragraphs are allowed), vary sentence openings, no parallel-structured H2s throughout ("Understanding X / Exploring Y / Navigating Z").
- **Add fingerprints of a human author**: one specific opinion or judgment call per major section, at least one concrete number/example per section, occasional colloquial aside.
- **Cut 10%**: remove every sentence that doesn't inform or persuade.
- Verify facts kept their sources (link them).

Finish with the mechanical punctuation gate (hard requirement, not stylistic):

```
grep -nE '—|–|"|"|'\''|'\''' <work_dir>/article.md
```

Any hit = fix and re-run until clean. No em/en dashes, no curly quotes, ASCII punctuation only. FAQ questions must be `###` headings.

## 4. Save + hand off

Create `work/<client>/<date>-<slug>/`:
- `article.md` — final article
- `meta.yaml` — `title`, `slug`, `meta_description` (150-158 chars, includes primary keyword), `tags` (3-5), `primary_keyword`, `infographic_ideas` (list of 1-3: for each, the specific data/process/comparison from the article worth visualizing — Agent 3 consumes this)

Then update the row:
```
.venv/bin/python scripts/sheets.py update --client clients/<client>.yaml --row <n> --set status=written work_dir=work/<client>/<date>-<slug>
```
On any unrecoverable failure set `status=error:<short reason>` instead so the pipeline surfaces it.
