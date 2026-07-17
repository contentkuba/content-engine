---
name: publish
description: "Agent 4 — publish a designed article to the client's WordPress or Wix (draft by default), write the URL back to the calendar, mark the row published. Args: path to clients/<client>.yaml"
---

# Agent 4 — Publisher

Input: client config path. Claim work:

```
.venv/bin/python scripts/sheets.py next --client clients/<client>.yaml --status designed
```

If none, stop. Otherwise publish `<work_dir>` per `publishing.cms`:

**WordPress:**
```
.venv/bin/python scripts/publish_wordpress.py --client clients/<client>.yaml --work-dir <work_dir>
```

**Wix:**
```
.venv/bin/python scripts/publish_wix.py --client clients/<client>.yaml --work-dir <work_dir>
```

Both scripts: upload `images/*.png` to the CMS media library, rewrite image refs, convert markdown, create the post with title/slug/meta description/tags from `meta.yaml`, honor `publishing.mode` (draft|live), and print a JSON result with `url` (and `edit_url` for drafts).

## Verify + hand off

- If the script fails, read its stderr, fix what's fixable (auth env vars missing → tell the user exactly which; transient 5xx → retry once), else set `status=error:<reason>`.
- On success, spot-check: WebFetch the returned URL (live mode) and confirm the H1 matches. For drafts just trust the API response.
- Update the row:
```
.venv/bin/python scripts/sheets.py update --client clients/<client>.yaml --row <n> --set status=published published_url=<url>
```
(For drafts, still `published`; the URL is the draft/edit URL and the mode is visible in notes — set `notes=draft` too.)

Never flip `publishing.mode` yourself; going live is the user's/client's call in the yaml.
