#!/usr/bin/env python3
"""Measure the true rendered height of a self-contained HTML infographic.

Renders the page in headless Chrome with a tall viewport, has inline JS stamp
document.body.scrollHeight onto <html data-h>, and reads it back via --dump-dom.
Lets you size the canvas to the content instead of guessing (dead-space band).

Usage: measure_height.py <file.html> [width]
"""
import pathlib
import re
import subprocess
import sys

CHROME = "/usr/bin/chromium-browser"
STAMP = ('<script>document.documentElement.setAttribute('
         '"data-h", document.body.scrollHeight)</script></body>')


def main():
    html = pathlib.Path(sys.argv[1]).resolve()
    width = sys.argv[2] if len(sys.argv) > 2 else "1600"

    probe = html.read_text().replace("</body>", STAMP)
    tmp = html.with_name("_probe.html")
    tmp.write_text(probe)
    try:
        out = subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
             f"--window-size={width},4000", "--virtual-time-budget=3000",
             "--dump-dom", tmp.as_uri()],
            capture_output=True, text=True, timeout=90).stdout
    finally:
        tmp.unlink(missing_ok=True)

    m = re.search(r'data-h="(\d+)"', out)
    if not m:
        sys.exit("measure failed: no data-h in dumped DOM")
    print(m.group(1))


if __name__ == "__main__":
    main()
