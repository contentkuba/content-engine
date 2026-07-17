#!/usr/bin/env python3
"""DataForSEO REST helper — fallback for headless runs where the dfs-mcp MCP server
is unavailable. Same endpoints, basic auth from .env.

Usage:
  dfs.py <endpoint_path> '<json_payload>'
Examples:
  dfs.py serp/google/organic/live/advanced '{"keyword":"windows 10 esu","location_name":"United States","language_code":"en","depth":10}'
  dfs.py dataforseo_labs/google/keyword_suggestions/live '{"keyword":"quickbooks desktop","limit":25,"filters":[["keyword_info.search_volume",">",40]]}'

Prints the first task's result JSON to stdout.
"""
import json, os, sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    envfile = ROOT / ".env"
    if envfile.exists():
        for line in envfile.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    load_env()
    login, pw = os.environ.get("DATAFORSEO_LOGIN", ""), os.environ.get("DATAFORSEO_PASSWORD", "")
    if not (login and pw):
        sys.exit("DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD missing from .env")
    path = sys.argv[1].strip("/")
    payload = json.loads(sys.argv[2])
    r = requests.post(f"https://api.dataforseo.com/v3/{path}",
                      auth=(login, pw), json=[payload], timeout=120)
    r.raise_for_status()
    data = r.json()
    task = data["tasks"][0]
    if task["status_code"] >= 40000:
        sys.exit(f"dataforseo error {task['status_code']}: {task['status_message']}")
    json.dump(task.get("result"), sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
