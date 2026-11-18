#!/usr/bin/env python3
"""Render web/figures/preview.png from web/figures/preview.html.

The image (1200 x 630) is what LinkedIn, Slack, X and other sites show when a link to the
site is shared; scripts/build_site.py copies it to site/assets/preview.png and points the
pages' Open Graph tags at it. It holds no numbers, so it only needs rendering again when
its design changes.

    python scripts/build_preview.py

Needs Chrome, Edge or Chromium (found as in scripts/check_site.py). Standard library otherwise.
"""

from __future__ import annotations

import functools
import http.server
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
OUT = WEB / "figures" / "preview.png"
sys.path.insert(0, str(ROOT / "scripts"))

from check_site import find_browser, png_size  # noqa: E402
from serve import Handler  # noqa: E402


def main():
    browser = find_browser()
    if not browser:
        sys.exit("no Chrome, Edge or Chromium found (set CHROME to its path)")
    # served over HTTP so the page can load the bundled fonts
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(WEB)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/figures/preview.html"
    with tempfile.TemporaryDirectory(prefix="wl-preview-") as tmp:
        subprocess.run([browser, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", f"--user-data-dir={tmp}", "--window-size=1200,630",
                        "--virtual-time-budget=5000", f"--screenshot={OUT}", url],
                       capture_output=True, timeout=120)
    server.shutdown()
    size = png_size(OUT) if OUT.exists() else None
    if size != (1200, 630):
        sys.exit(f"expected a 1200 x 630 PNG at {OUT.relative_to(ROOT)}, got {size}")
    print(f"wrote {OUT.relative_to(ROOT)} (1200 x 630, {OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
