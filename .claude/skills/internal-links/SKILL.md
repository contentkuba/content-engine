---
name: internal-links
description: "Agent 5 — after an article goes live, edit 2-3 existing live articles on the client's site to add contextual internal links pointing at it (and backfill outbound links in the new article). Args: path to clients/<client>.yaml"
---

# Agent 5 — Internal Linker

**This agent edits LIVE client content.** It only ever adds one `<a>` tag per edit via
`scripts/internal_links.py add-link`, which refuses ambiguous matches and duplicate links,
and logs every change to `work/<client>/link-changelog.jsonl`. Never edit posts any other way.

Skip entirely if `internal_linking.enabled` is false in the client yaml.

Input: client config path. Claim work:

```
.venv/bin/python scripts/sheets.py next --client clients/<client>.yaml --status published
```

If none, stop — but first run the **go-live sweep**: scan the Calendar for rows with
`status=linked` whose notes contain `pending go-live`. For each, check the post via the CMS API;
if it is now live (status `publish`), run the inbound-linking pass below for it and update its
notes to `inbound: <n> links added`. This catches articles that were drafts when first processed.

If the claimed row's `notes` say `draft` (article not live yet), set `status=linked`
with `notes=draft — inbound links pending go-live` and stop — there is no live URL to link to.

## 1. Refresh the link inventory

```
.venv/bin/python scripts/internal_links.py inventory --client clients/<client>.yaml
```

Read `work/<client>/linkmap.json`: every live post with post_id, url, title, headings, outbound_urls.

## 2. Choose host articles (inbound links → the new article)

Pick up to `internal_linking.max_inbound` (default 3) posts where a link to the new article
helps the *reader*, judged by title/heading overlap with the new article's primary keyword and topic.
Hard rules:
- Skip any post whose `outbound_urls` already contains the new URL.
- Max ONE new link per host article per day (re-runs must not pile links into the same post).
- No relevant host found beats a forced irrelevant link — linking is optional per candidate.

## 3. Place each link

For each chosen host:
1. `get-post --post-id <id>` and read the content.
2. Find an EXISTING sentence where the new article is a natural next step. Do not write new
   sentences into the client's article; you are only linking text that is already there.
3. Choose anchor text inside that sentence: 2-6 words, descriptive of the target
   (vary anchors across hosts; never bare "click here", never the same exact-match keyword 3×).
4. ```
   .venv/bin/python scripts/internal_links.py add-link --client <yaml> --post-id <id> \
     --find "<the full sentence, verbatim>" --url <new article url> --anchor "<anchor words>"
   ```
5. If the script refuses (ambiguous match, duplicate, formatting boundary), pick a different
   sentence or host — never force it by shortening `--find` below a full clause.

## 4. Backfill outbound links (new article → older posts)

If the new article has fewer than 2 internal links, find 1-2 linkmap posts genuinely relevant
to its sections and add links inside the new article the same way (`add-link` against the new
article's own post-id).

## 5. Hand off

```
.venv/bin/python scripts/sheets.py update --client clients/<client>.yaml --row <n> \
  --set status=linked notes="inbound: <n> links added"
```

Report which posts were edited and the anchors used. On failure of an individual link, continue
with the others; only set `status=error:...` if the inventory itself is unavailable.
