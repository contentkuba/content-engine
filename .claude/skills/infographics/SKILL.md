---
name: infographics
description: "Agent 3 — create branded infographics for a written article: author self-contained HTML/SVG, render to PNG headlessly, save into the article's work dir, mark the row designed. Args: path to clients/<client>.yaml"
---

# Agent 3 — Infographic Designer

Input: client config path. Claim work:

```
.venv/bin/python scripts/sheets.py next --client clients/<client>.yaml --status written
```

If none, stop. Otherwise read `<work_dir>/article.md` and `<work_dir>/meta.yaml` — `infographic_ideas` lists what to visualize. Produce `infographics.per_article` images (client yaml); if `per_article: 0`, just flip status to `designed` and stop.

## Design rules

- One idea per graphic: a process (numbered steps), a comparison (two columns), a stat cluster (3-4 big numbers), or a checklist. Never paragraphs of prose in an image.
- Use ONLY content from the article — every number must appear in the article text.
- Brand: colors and font from `infographics.brand` in the client yaml. Light background (`light`), headings in `dark`, one `primary` + one `accent` — nothing else. Generous whitespace, 40px+ padding.
- Canvas: size the height to the CONTENT, not a fixed number — a fixed tall canvas leaves a dead-space band (recurring issue). Start near 1200×1200 (portrait) or 1600×650 (wide comparison), render, and shrink until the footer sits ~40px under the last element.
- Footer strip: client domain in small type — these get shared/screenshotted.
- Self-contained HTML: inline CSS only, no external fonts/scripts/images (system font fallback stack after the brand font).

## Produce

For each idea `i`:
1. Write `<work_dir>/images/infographic-<i>.html`
2. Render: `.venv/bin/python scripts/render_infographic.py <html> --width 1200 --height 1500`
3. Read the PNG back (Read tool renders images) and CHECK IT: no clipped text, no overflow, hierarchy readable at 50% zoom. Fix HTML and re-render until clean — max 3 iterations, then simplify the design.

Also insert image references into `article.md` at the natural point (after the section each visualizes):
`![<descriptive alt with keyword if natural>](images/infographic-<i>.png)`

## Hand off

```
.venv/bin/python scripts/sheets.py update --client clients/<client>.yaml --row <n> --set status=designed
```
On unrecoverable failure: `status=error:<reason>`. A rendering problem is not unrecoverable — publishing without images is worse than a simpler graphic, but if all ideas fail, remove the image refs and still mark `designed` with a note.
