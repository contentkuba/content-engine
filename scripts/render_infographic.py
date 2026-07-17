#!/usr/bin/env python3
"""Render a self-contained HTML infographic to PNG with headless Chrome.

Usage: render_infographic.py <file.html> [--width 1200] [--height 1500] [--out <file.png>]
"""
import argparse, shutil, subprocess, sys
from pathlib import Path

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_chrome():
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        if shutil.which(name):
            return shutil.which(name)
    sys.exit("no Chrome/Chromium found; install Google Chrome or add its path to CHROME_CANDIDATES")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("html")
    p.add_argument("--width", type=int, default=1200)
    p.add_argument("--height", type=int, default=1500)
    p.add_argument("--out")
    args = p.parse_args()

    src = Path(args.html).resolve()
    out = Path(args.out) if args.out else src.with_suffix(".png")
    cmd = [find_chrome(), "--headless=new", "--disable-gpu", "--no-sandbox",
           "--hide-scrollbars", "--force-device-scale-factor=2",
           f"--window-size={args.width},{args.height}",
           f"--screenshot={out}", src.as_uri()]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    # snap-packaged chromium exits non-zero from sandbox/dbus noise even on success:
    # a written, non-empty PNG is the real success signal
    if not out.exists() or out.stat().st_size == 0:
        sys.exit(f"chrome render failed: {res.stderr[-800:]}")
    if res.returncode != 0:
        print(f"note: chrome exit {res.returncode} (sandbox noise), PNG written OK", file=sys.stderr)
    print(out)


if __name__ == "__main__":
    main()
