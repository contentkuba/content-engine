#!/usr/bin/env python3
"""Publish a work-dir article to WordPress via the REST API (Application Password auth).

Usage: publish_wordpress.py --client clients/<c>.yaml --work-dir work/<c>/<date>-<slug>
Prints JSON: {"url": ..., "edit_url": ..., "post_id": ..., "status": ...}
"""
import argparse, json, os, re, sys, time
from pathlib import Path

import markdown
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    envfile = ROOT / ".env"
    if envfile.exists():
        for line in envfile.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def env(name):
    v = os.environ.get(name, "")
    if not v:
        sys.exit(f"missing env var {name} — add it to .env")
    return v


def api(cfg):
    wp = cfg["publishing"]["wordpress"]
    base = wp["base_url"].rstrip("/") + "/wp-json/wp/v2"
    auth = (env(wp["user_env"]), env(wp["app_password_env"]))
    return base, auth


def upload_media(base, auth, path: Path, alt: str):
    # shared hosts intermittently 503 the first media POST; retry with backoff
    for attempt in range(4):
        with open(path, "rb") as f:
            r = requests.post(f"{base}/media", auth=auth, data=f,
                              headers={"Content-Disposition": f'attachment; filename="{path.name}"',
                                       "Content-Type": "image/png"}, timeout=120)
        if r.status_code < 500:
            break
        print(f"media upload {r.status_code}, retry {attempt + 1}/3", file=sys.stderr)
        time.sleep(5 * (attempt + 1))
    r.raise_for_status()
    media = r.json()
    if alt:
        requests.post(f"{base}/media/{media['id']}", auth=auth, json={"alt_text": alt}, timeout=60)
    return media


def ensure_term(base, auth, taxonomy, name):
    r = requests.get(f"{base}/{taxonomy}", auth=auth, params={"search": name, "per_page": 100}, timeout=60)
    r.raise_for_status()
    for t in r.json():
        if t["name"].lower() == name.lower():
            return t["id"]
    r = requests.post(f"{base}/{taxonomy}", auth=auth, json={"name": name}, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


def main():
    load_env()
    p = argparse.ArgumentParser()
    p.add_argument("--client", required=True)
    p.add_argument("--work-dir", required=True)
    args = p.parse_args()

    cfg = yaml.safe_load(Path(args.client).read_text())
    work = Path(args.work_dir)
    meta = yaml.safe_load((work / "meta.yaml").read_text())
    md_text = (work / "article.md").read_text()
    base, auth = api(cfg)
    mode = cfg["publishing"].get("mode", "draft")

    # upload local images referenced as images/xxx.png and swap in hosted URLs
    featured_id = None
    for m in re.finditer(r"!\[([^\]]*)\]\((images/[^)]+)\)", md_text):
        alt, rel = m.group(1), m.group(2)
        img = work / rel
        if not img.exists():
            print(f"warning: {img} missing, dropping ref", file=sys.stderr)
            md_text = md_text.replace(m.group(0), "")
            continue
        media = upload_media(base, auth, img, alt)
        md_text = md_text.replace(rel, media["source_url"])
        featured_id = featured_id or media["id"]

    # strip H1 (WP renders the title itself)
    md_text = re.sub(r"^# .*\n+", "", md_text, count=1)
    html = markdown.markdown(md_text, extensions=["tables", "fenced_code"])

    post = {
        "title": meta["title"],
        "slug": meta.get("slug", ""),
        "content": html,
        "status": "publish" if mode == "live" else "draft",
        "excerpt": meta.get("meta_description", ""),
    }
    wp_cfg = cfg["publishing"]["wordpress"]
    if wp_cfg.get("category"):
        post["categories"] = [ensure_term(base, auth, "categories", wp_cfg["category"])]
    if meta.get("tags"):
        post["tags"] = [ensure_term(base, auth, "tags", t) for t in meta["tags"]]
    if featured_id:
        post["featured_media"] = featured_id

    r = requests.post(f"{base}/posts", auth=auth, json=post, timeout=120)
    r.raise_for_status()
    data = r.json()

    # Rank Math SEO meta (best-effort: the plugin may not be installed on every client site)
    rm_meta = {}
    if meta.get("meta_description"):
        rm_meta["rank_math_description"] = meta["meta_description"]
    if meta.get("primary_keyword"):
        rm_meta["rank_math_focus_keyword"] = meta["primary_keyword"]
    if rm_meta:
        rm_base = wp_cfg["base_url"].rstrip("/") + "/wp-json/rankmath/v1/updateMeta"
        rr = requests.post(rm_base, auth=auth, timeout=60,
                           json={"objectID": data["id"], "objectType": "post", "meta": rm_meta})
        if rr.status_code != 200:
            print(f"warning: rank math meta not set ({rr.status_code}) — plugin missing or route changed",
                  file=sys.stderr)
    print(json.dumps({
        "post_id": data["id"],
        "status": data["status"],
        "url": data["link"],
        "edit_url": f"{wp_cfg['base_url'].rstrip('/')}/wp-admin/post.php?post={data['id']}&action=edit",
    }))


if __name__ == "__main__":
    main()
