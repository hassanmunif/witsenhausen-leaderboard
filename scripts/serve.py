#!/usr/bin/env python3
"""Serve the built site on this computer at http://localhost:2000.

    python scripts/serve.py              # build site/ if missing, then serve
    python scripts/serve.py --open       # also open it in the default browser
    python scripts/serve.py --port 8000  # another port
    python scripts/serve.py --build      # rebuild site/ first (after re-scoring)

The server listens on 127.0.0.1 only, so other computers on the network
cannot reach it.  Stop it with Ctrl+C or by closing its window.
Standard library only.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

# Set explicitly: on Windows, Python's guesses come from the registry and can be wrong.
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".png": "image/png",
    ".md": "text/plain; charset=utf-8",
    "": "application/octet-stream",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = TYPES

    def end_headers(self):
        # Always serve the latest build when the page is reloaded.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if args and str(args[1]).startswith(("4", "5")):  # only report errors
            sys.stderr.write("  %s %s\n" % (args[1], args[0]))


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Serve site/ at http://localhost:PORT")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--open", action="store_true", help="open the page in the default browser")
    ap.add_argument("--build", action="store_true", help="rebuild site/ before serving")
    args = ap.parse_args(argv)

    if args.build or not (SITE / "index.html").exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_site.py")], check=True)

    port = args.port
    if not port_free(port):
        old = port
        while not port_free(port):
            port += 1
        print(f"Port {old} is in use; using {port} instead.")

    handler = functools.partial(Handler, directory=str(SITE))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://localhost:{port}/"
    print(f"Serving {SITE}")
    print(f"Open {url}   (Ctrl+C or close this window to stop)")
    if args.open:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
