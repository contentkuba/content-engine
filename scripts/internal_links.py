#!/usr/bin/env python3
"""Internal-link plumbing for Agent 5. Works on LIVE posts via the CMS API.

Commands (all take --client clients/<c>.yaml):
  inventory                       build/refresh work/<client>/linkmap.json from live blog posts
  get-post --post-id <id>         print a post's text content (WP: HTML, Wix: extracted ricos text)
  add-link --post-id <id> --find "<exact existing sentence/phrase>" --url <target> [--anchor "<substring of find>"]
                                  wrap --anchor (default: whole --find text) in a link, only if
                                  --find occurs EXACTLY ONCE and the post doesn't already link to --url

Safety: exact-match-or-abort edits, one link per call, refuses duplicate links.
WordPress keeps native revisions of every edit. Wix edits update the draft and republish.
"""
import argparse, html, json, os, re, sys
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup

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


def load_client(path):
    cfg = yaml.safe_load(Path(path).read_text())
    cms = cfg["publishing"]["cms"]
    return cfg, cms


def linkmap_path(cfg):
    d = ROOT / "work" / cfg["name"]
    d.mkdir(parents=True, exist_ok=True)
    return d / "linkmap.json"


# ---------- WordPress ----------

def wp_api(cfg):
    wp = cfg["publishing"]["wordpress"]
    return (wp["base_url"].rstrip("/") + "/wp-json/wp/v2",
            (env(wp["user_env"]), env(wp["app_password_env"])))


def wp_all_posts(base, auth):
    posts, page = [], 1
    while True:
        r = requests.get(f"{base}/posts", auth=auth, timeout=60,
                         params={"per_page": 100, "page": page, "status": "publish",
                                 "_fields": "id,link,title,content"})
        if r.status_code == 400:  # past last page
            break
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        posts.extend(batch)
        page += 1
    return posts


def wp_inventory(cfg):
    base, auth = wp_api(cfg)
    items = []
    for p in wp_all_posts(base, auth):
        soup = BeautifulSoup(p["content"]["rendered"], "html.parser")
        items.append({
            "post_id": str(p["id"]),
            "url": p["link"],
            "title": html.unescape(p["title"]["rendered"]),
            "headings": [h.get_text(" ", strip=True) for h in soup.find_all(["h2", "h3"])][:10],
            "outbound_urls": sorted({a["href"] for a in soup.find_all("a", href=True)}),
        })
    return items


def wp_get_post(cfg, post_id):
    base, auth = wp_api(cfg)
    r = requests.get(f"{base}/posts/{post_id}", auth=auth, timeout=60,
                     params={"_fields": "id,link,title,content"})
    r.raise_for_status()
    return r.json()


def wp_add_link(cfg, post_id, find, url, anchor):
    base, auth = wp_api(cfg)
    post = wp_get_post(cfg, post_id)
    content = post["content"]["rendered"]
    if url in content:
        sys.exit(f"post {post_id} already links to {url} — refusing duplicate")
    n = content.count(find)
    if n != 1:
        sys.exit(f"--find text occurs {n} times in post {post_id} (need exactly 1); "
                 f"pass a longer, unique snippet")
    linked = find.replace(anchor, f'<a href="{url}">{anchor}</a>', 1)
    r = requests.post(f"{base}/posts/{post_id}", auth=auth, timeout=120,
                      json={"content": content.replace(find, linked, 1)})
    r.raise_for_status()
    return {"post_id": post_id, "post_url": post["link"], "anchor": anchor, "target": url}


# ---------- Wix ----------

def wix_headers(cfg):
    wix = cfg["publishing"]["wix"]
    return {"Authorization": env(wix["api_key_env"]),
            "wix-site-id": env(wix["site_id_env"]),
            "Content-Type": "application/json"}


WIX = "https://www.wixapis.com"


def ricos_walk_text(node, fn):
    """Depth-first visit of TEXT nodes; fn may return a replacement LIST of nodes."""
    kids = node.get("nodes", [])
    new_kids = []
    for child in kids:
        if child.get("type") == "TEXT":
            repl = fn(child)
            new_kids.extend(repl if repl is not None else [child])
        else:
            ricos_walk_text(child, fn)
            new_kids.append(child)
    node["nodes"] = new_kids


def ricos_plain_text(rich):
    out = []

    def collect(n):
        out.append(n["textData"]["text"])

    root = {"nodes": rich.get("nodes", [])}
    ricos_walk_text(root, lambda n: (collect(n), None)[1])
    return "".join(out)


def ricos_urls(rich):
    urls = set()

    def visit(n):
        for d in n.get("textData", {}).get("decorations", []):
            if d.get("type") == "LINK":
                urls.add(d.get("linkData", {}).get("link", {}).get("url", ""))
        return None

    ricos_walk_text({"nodes": rich.get("nodes", [])}, visit)
    return urls


def wix_list_posts(cfg):
    hdrs = wix_headers(cfg)
    posts, offset = [], 0
    while True:
        r = requests.get(f"{WIX}/blog/v3/posts", headers=hdrs, timeout=60,
                         params={"paging.limit": 100, "paging.offset": offset})
        r.raise_for_status()
        batch = r.json().get("posts", [])
        if not batch:
            break
        posts.extend(batch)
        offset += len(batch)
    return posts


def wix_inventory(cfg):
    hdrs = wix_headers(cfg)
    items = []
    for p in wix_list_posts(cfg):
        r = requests.get(f"{WIX}/blog/v3/posts/{p['id']}", headers=hdrs, timeout=60,
                         params={"fieldsets": "RICH_CONTENT"})
        r.raise_for_status()
        full = r.json()["post"]
        rich = full.get("richContent", {"nodes": []})
        headings = [ricos_plain_text({"nodes": [n]}) for n in rich["nodes"]
                    if n.get("type") == "HEADING"][:10]
        url = (p.get("url", {}).get("base", "") or "") + (p.get("url", {}).get("path", "") or "")
        items.append({"post_id": p["id"], "url": url, "title": p.get("title", ""),
                      "headings": headings, "outbound_urls": sorted(ricos_urls(rich))})
    return items


def wix_get_draft(cfg, post_id):
    """Published Wix posts are edited via their draft twin (same id)."""
    hdrs = wix_headers(cfg)
    r = requests.get(f"{WIX}/blog/v3/draft-posts/{post_id}", headers=hdrs, timeout=60,
                     params={"fieldsets": "RICH_CONTENT"})
    r.raise_for_status()
    return r.json()["draftPost"]


def wix_add_link(cfg, post_id, find, url, anchor):
    hdrs = wix_headers(cfg)
    draft = wix_get_draft(cfg, post_id)
    rich = draft.get("richContent", {"nodes": []})
    if url in ricos_urls(rich):
        sys.exit(f"post {post_id} already links to {url} — refusing duplicate")
    plain = ricos_plain_text(rich)
    if plain.count(find) != 1:
        sys.exit(f"--find text occurs {plain.count(find)} times in post {post_id} "
                 f"(need exactly 1); note: Wix matching is per-text-node, avoid snippets "
                 f"spanning bold/link boundaries")
    hits = [0]

    def link_node(n):
        text = n["textData"]["text"]
        if anchor not in text or find not in text:
            return None
        pre, _, post_ = text.partition(anchor)
        decos = n["textData"].get("decorations", [])
        hits[0] += 1
        parts = []
        if pre:
            parts.append({"type": "TEXT", "id": "", "nodes": [],
                          "textData": {"text": pre, "decorations": decos}})
        parts.append({"type": "TEXT", "id": "", "nodes": [],
                      "textData": {"text": anchor,
                                   "decorations": decos + [{"type": "LINK",
                                                            "linkData": {"link": {"url": url}}}]}})
        if post_:
            parts.append({"type": "TEXT", "id": "", "nodes": [],
                          "textData": {"text": post_, "decorations": decos}})
        return parts

    ricos_walk_text({"nodes": rich["nodes"]}, link_node)
    if hits[0] != 1:
        sys.exit(f"anchor did not match exactly one text node (matched {hits[0]}); "
                 f"the sentence likely spans formatting boundaries — pick a plainer snippet")
    r = requests.patch(f"{WIX}/blog/v3/draft-posts/{post_id}", headers=hdrs, timeout=120,
                       json={"draftPost": {"id": post_id, "richContent": rich},
                             "fieldMask": "richContent"})
    r.raise_for_status()
    r = requests.post(f"{WIX}/blog/v3/draft-posts/{post_id}/publish", headers=hdrs, timeout=120)
    r.raise_for_status()
    return {"post_id": post_id, "anchor": anchor, "target": url}


# ---------- commands ----------

def cmd_inventory(args):
    cfg, cms = load_client(args.client)
    items = wp_inventory(cfg) if cms == "wordpress" else wix_inventory(cfg)
    path = linkmap_path(cfg)
    path.write_text(json.dumps(items, indent=1, ensure_ascii=False))
    print(json.dumps({"posts": len(items), "linkmap": str(path)}))


def cmd_get_post(args):
    cfg, cms = load_client(args.client)
    if cms == "wordpress":
        p = wp_get_post(cfg, args.post_id)
        print(json.dumps({"title": html.unescape(p["title"]["rendered"]), "url": p["link"],
                          "content_html": p["content"]["rendered"]}, ensure_ascii=False))
    else:
        d = wix_get_draft(cfg, args.post_id)
        print(json.dumps({"title": d.get("title", ""),
                          "content_text": ricos_plain_text(d.get("richContent", {"nodes": []}))},
                         ensure_ascii=False))


def cmd_add_link(args):
    cfg, cms = load_client(args.client)
    anchor = args.anchor or args.find
    if anchor not in args.find:
        sys.exit("--anchor must be a substring of --find")
    if len(anchor.split()) > 8:
        sys.exit("anchor too long (max 8 words) — link a phrase, not a sentence")
    fn = wp_add_link if cms == "wordpress" else wix_add_link
    result = fn(cfg, args.post_id, args.find, args.url, anchor)
    log = ROOT / "work" / cfg["name"] / "link-changelog.jsonl"
    with open(log, "a") as f:
        f.write(json.dumps(result) + "\n")
    print(json.dumps(result))


def main():
    load_env()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in [("inventory", cmd_inventory), ("get-post", cmd_get_post),
                     ("add-link", cmd_add_link)]:
        sp = sub.add_parser(name)
        sp.add_argument("--client", required=True)
        sp.set_defaults(fn=fn)
        if name in ("get-post", "add-link"):
            sp.add_argument("--post-id", required=True)
        if name == "add-link":
            sp.add_argument("--find", required=True,
                            help="exact existing sentence/snippet in the post (must be unique)")
            sp.add_argument("--url", required=True, help="target URL to link to")
            sp.add_argument("--anchor", help="substring of --find to use as anchor text")
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
