#!/usr/bin/env python3
"""Publish a work-dir article to Wix Blog via the REST API (API key auth).

Converts article.md to Wix Ricos rich content (headings, paragraphs, lists,
images, bold, links). Creates a draft post; publishes it if publishing.mode is live.

Usage: publish_wix.py --client clients/<c>.yaml --work-dir work/<c>/<date>-<slug>
Prints JSON: {"draft_post_id": ..., "status": ..., "url": ...}
"""
import argparse, json, mimetypes, os, re, sys
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup, NavigableString
import markdown

ROOT = Path(__file__).resolve().parent.parent
WIX = "https://www.wixapis.com"


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


def headers(cfg):
    wix = cfg["publishing"]["wix"]
    return {"Authorization": env(wix["api_key_env"]),
            "wix-site-id": env(wix["site_id_env"]),
            "Content-Type": "application/json"}


def upload_image(hdrs, path: Path):
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    r = requests.post(f"{WIX}/site-media/v1/files/generate-upload-url", headers=hdrs,
                      json={"mimeType": mime, "fileName": path.name}, timeout=60)
    r.raise_for_status()
    upload_url = r.json()["uploadUrl"]
    with open(path, "rb") as f:
        r = requests.put(upload_url, params={"filename": path.name},
                         data=f, headers={"Content-Type": mime}, timeout=120)
    r.raise_for_status()
    file = r.json()["file"]
    return {"id": file["id"],
            "width": file.get("media", {}).get("image", {}).get("width"),
            "height": file.get("media", {}).get("image", {}).get("height")}


# ---- minimal HTML -> Ricos ----

def text_nodes(el):
    """Flatten inline content of an element into Ricos TEXT nodes with bold/link decorations."""
    out = []

    def walk(node, decorations):
        if isinstance(node, NavigableString):
            s = str(node)
            if s:
                out.append({"type": "TEXT", "id": "", "nodes": [],
                            "textData": {"text": s, "decorations": decorations}})
            return
        decos = list(decorations)
        if node.name in ("strong", "b"):
            decos = decos + [{"type": "BOLD", "fontWeightValue": 700}]
        if node.name in ("em", "i"):
            decos = decos + [{"type": "ITALIC", "italicData": True}]
        if node.name == "a" and node.get("href"):
            decos = decos + [{"type": "LINK", "linkData": {"link": {"url": node["href"]}}}]
        for child in node.children:
            walk(child, decos)

    for child in el.children:
        walk(child, [])
    return out


def html_to_ricos(html, images):
    soup = BeautifulSoup(html, "html.parser")
    nodes = []
    nid = 0

    def make(node_type, **extra):
        nonlocal nid
        nid += 1
        return {"type": node_type, "id": f"n{nid}", "nodes": [], **extra}

    for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "ul", "ol", "img"], recursive=True):
        if el.find_parent(["ul", "ol"]) and el.name not in ("ul", "ol"):
            continue
        if el.name and el.name.startswith("h"):
            n = make("HEADING", headingData={"level": int(el.name[1])})
            n["nodes"] = text_nodes(el)
            nodes.append(n)
        elif el.name == "p":
            img = el.find("img")
            if img is not None and img.get("src") in images:
                info = images[img["src"]]
                nodes.append(make("IMAGE", imageData={
                    "image": {"src": {"id": info["id"]},
                              **({"width": info["width"], "height": info["height"]}
                                 if info.get("width") else {})},
                    "altText": img.get("alt", "")}))
                continue
            n = make("PARAGRAPH", paragraphData={})
            n["nodes"] = text_nodes(el)
            if n["nodes"]:
                nodes.append(n)
        elif el.name in ("ul", "ol"):
            list_node = make("BULLETED_LIST" if el.name == "ul" else "ORDERED_LIST")
            for li in el.find_all("li", recursive=False):
                item = make("LIST_ITEM")
                para = make("PARAGRAPH", paragraphData={})
                para["nodes"] = text_nodes(li)
                item["nodes"] = [para]
                list_node["nodes"].append(item)
            nodes.append(list_node)
    return {"nodes": nodes}


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
    hdrs = headers(cfg)
    wix_cfg = cfg["publishing"]["wix"]
    mode = cfg["publishing"].get("mode", "draft")

    # upload images; map local ref -> wix media id
    images = {}
    for m in re.finditer(r"!\[[^\]]*\]\((images/[^)]+)\)", md_text):
        rel = m.group(1)
        img = work / rel
        if img.exists():
            images[rel] = upload_image(hdrs, img)
        else:
            print(f"warning: {img} missing, dropping ref", file=sys.stderr)
            md_text = md_text.replace(m.group(0), "")

    md_text = re.sub(r"^# .*\n+", "", md_text, count=1)  # title handled by Wix
    html = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    rich = html_to_ricos(html, images)

    draft = {"draftPost": {
        "title": meta["title"],
        "richContent": rich,
        "seoData": {"slug": meta.get("slug", ""),
                    "description": meta.get("meta_description", "")},
        **({"memberId": wix_cfg["member_id"]} if wix_cfg.get("member_id") else {}),
    }}
    r = requests.post(f"{WIX}/blog/v3/draft-posts", headers=hdrs, json=draft, timeout=120)
    if r.status_code >= 400:
        sys.exit(f"wix draft create failed {r.status_code}: {r.text[:800]}")
    post = r.json()["draftPost"]
    result = {"draft_post_id": post["id"], "status": "draft",
              "url": f"https://manage.wix.com/dashboard/{env(wix_cfg['site_id_env'])}/blog/{post['id']}/edit"}

    if mode == "live":
        r = requests.post(f"{WIX}/blog/v3/draft-posts/{post['id']}/publish", headers=hdrs, timeout=120)
        if r.status_code >= 400:
            sys.exit(f"wix publish failed {r.status_code}: {r.text[:800]}")
        result["status"] = "published"
        result["url"] = post.get("url", {}).get("base", "") + post.get("url", {}).get("path", "") or result["url"]

    print(json.dumps(result))


if __name__ == "__main__":
    main()
