#!/usr/bin/env python3
"""Google Sheets I/O for the content engine.

Commands:
  create  --client <yaml>                          create spreadsheet + tabs, print its ID
  next    --client <yaml> --status <status>        print first Calendar row with that status (JSON) or exit 1
  update  --client <yaml> --row <n> --set k=v ...  update columns of Calendar row n (1-based data row)
  append  --client <yaml> --tab Keywords|Calendar --json <file|->   append rows from a JSON array of objects
"""
import argparse, json, os, sys
from pathlib import Path

import gspread
import yaml
from google.oauth2.service_account import Credentials

ROOT = Path(__file__).resolve().parent.parent
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

KEYWORDS_HEADER = ["keyword", "volume", "difficulty", "intent", "cpc",
                   "priority_score", "source", "notes"]
CALENDAR_HEADER = ["date", "title", "primary_keyword", "secondary_keywords",
                   "intent", "outline", "status", "work_dir", "published_url", "notes"]


def load_env():
    envfile = ROOT / ".env"
    if envfile.exists():
        for line in envfile.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def client_config(path):
    return yaml.safe_load(Path(path).read_text())


def gclient():
    keyfile = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "secrets/service-account.json")
    keypath = Path(keyfile) if os.path.isabs(keyfile) else ROOT / keyfile
    if not keypath.exists():
        sys.exit(f"service account key not found: {keypath} (see README setup step 2)")
    return gspread.authorize(Credentials.from_service_account_file(str(keypath), scopes=SCOPES))


def open_sheet(cfg):
    sid = (cfg.get("sheet") or {}).get("spreadsheet_id") or ""
    if not sid:
        sys.exit("sheet.spreadsheet_id is empty in the client yaml — run `sheets.py create` first")
    return gclient().open_by_key(sid)


def ensure_tab(ss, title, header):
    try:
        ws = ss.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=title, rows=1000, cols=len(header))
    if not ws.row_values(1):
        ws.update("A1", [header])
    return ws


def cmd_create(args):
    cfg = client_config(args.client)
    gc = gclient()
    sid = (cfg.get("sheet") or {}).get("spreadsheet_id") or ""
    try:
        ss = gc.open_by_key(sid) if sid else gc.create(f"Content Engine — {cfg['name']}")
    except gspread.exceptions.APIError as e:
        if "storage quota" in str(e):
            sys.exit(
                "Google no longer lets service accounts own files. Create the spreadsheet "
                f"manually in your Drive, share it (Editor) with the service account email "
                f"(client_email in the key JSON), paste its ID into {args.client} -> "
                "sheet.spreadsheet_id, then re-run this command to add the tabs."
            )
        raise
    if getattr(args, "share", None):
        ss.share(args.share, perm_type="user", role="writer", notify=False)
    ensure_tab(ss, "Keywords", KEYWORDS_HEADER)
    ensure_tab(ss, "Calendar", CALENDAR_HEADER)
    print(json.dumps({"spreadsheet_id": ss.id, "url": ss.url}))
    if not sid:
        print(f"paste into {args.client} -> sheet.spreadsheet_id, and share the sheet "
              f"with the service account email if not already", file=sys.stderr)


def rows_as_dicts(ws):
    values = ws.get_all_values()
    if not values:
        return [], []
    header = values[0]
    return header, [dict(zip(header, r + [""] * (len(header) - len(r)))) for r in values[1:]]


def cmd_next(args):
    ws = open_sheet(client_config(args.client)).worksheet("Calendar")
    _, rows = rows_as_dicts(ws)
    for i, row in enumerate(rows, start=1):
        if row.get("status", "").strip() == args.status:
            print(json.dumps({"row": i, **row}, ensure_ascii=False))
            return
    print(f"no Calendar row with status={args.status}", file=sys.stderr)
    sys.exit(1)


def cmd_update(args):
    ws = open_sheet(client_config(args.client)).worksheet("Calendar")
    header = ws.row_values(1)
    updates = []
    for kv in args.set:
        k, _, v = kv.partition("=")
        if k not in header:
            sys.exit(f"unknown column: {k} (have: {header})")
        updates.append(gspread.Cell(row=args.row + 1, col=header.index(k) + 1, value=v))
    ws.update_cells(updates)
    print(f"row {args.row}: set {', '.join(args.set)}")


def cmd_append(args):
    ws = open_sheet(client_config(args.client)).worksheet(args.tab)
    header = ws.row_values(1)
    data = json.load(sys.stdin if args.json == "-" else open(args.json))
    ws.append_rows([[str(obj.get(col, "")) for col in header] for obj in data],
                   value_input_option="USER_ENTERED")
    print(f"appended {len(data)} rows to {args.tab}")


def main():
    load_env()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in [("create", cmd_create), ("next", cmd_next),
                     ("update", cmd_update), ("append", cmd_append)]:
        sp = sub.add_parser(name)
        sp.add_argument("--client", required=True)
        sp.set_defaults(fn=fn)
        if name == "create":
            sp.add_argument("--share", help="email to share a newly created spreadsheet with")
        if name == "next":
            sp.add_argument("--status", required=True)
        elif name == "update":
            sp.add_argument("--row", type=int, required=True, help="1-based data row (as printed by `next`)")
            sp.add_argument("--set", nargs="+", required=True, metavar="col=value")
        elif name == "append":
            sp.add_argument("--tab", required=True, choices=["Keywords", "Calendar"])
            sp.add_argument("--json", required=True, help="JSON array file, or - for stdin")
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
