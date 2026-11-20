#!/usr/bin/env python3
r"""Check the built site before it is published. Run it after scripts/build_site.py.

    python scripts/check_site.py            # uses Chrome (or Edge, Chromium) and Node.js if it finds them
    python scripts/check_site.py --strict   # fails if either is missing (CI)

1. Formulas. Every formula is parsed by the bundled KaTeX under Node.js: each \( \) and \[ \] on the
   pages, and each $...$ in the data they show (names, methods, notes, claims). A formula that does not
   parse, or uses an unknown command, would show up as red source text.
2. Pages. Every page is served from a local web server and opened in a headless browser. It must load
   all its files, run without a script error or a KaTeX error, and draw its content: the home page's
   figures and numbers, the leaderboard of every setting (one row per verified entry and per open
   claim, and every lower bound), the history charts, the theory log and the contribute page's targets.
3. Links. Every link to another page of the site, or to an anchor on one (problem.html#eq-6), reaches
   a page and an element that exist, and every controller file the leaderboard offers is in site/.
   Every page's link-preview image (og:image) is in site/ and is 1200 x 630.

Standard library only, apart from the browser and Node.js. Exit status 1 if any check fails.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
KATEX = ROOT / "web" / "vendor" / "katex" / "katex.min.js"
sys.path.insert(0, str(ROOT / "scripts"))

from build_site import PAGES  # noqa: E402
from serve import Handler  # noqa: E402

# Added to the <head> of a temporary copy of each page, so that a script error, or a script or style
# sheet that fails to load, is written on <html> and shows in the page the browser hands back.
ERROR_HOOK = """<script>(function () {
  function note(msg) { if (!document.documentElement.hasAttribute("data-check-error")) document.documentElement.setAttribute("data-check-error", msg); }
  window.addEventListener("error", function (e) {
    var t = e.target;
    if (t && t !== window && (t.src || t.href)) note("could not load " + (t.src || t.href).split("/").pop());
    else note((e.message || "script error") + " (" + String(e.filename || "").split("/").pop() + ":" + (e.lineno || "?") + ")");
  }, true);
  window.addEventListener("unhandledrejection", function (e) { note("unhandled rejection: " + e.reason); });
})();</script>"""

# Run by Node.js with the bundled KaTeX: each formula is rendered as on the site, but errors throw.
KATEX_CHECK = r"""
const katex = require(process.argv[1]);
const items = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));
const bad = [];
for (const it of items) {
  try { katex.renderToString(it.tex, { throwOnError: true, displayMode: !!it.display }); }
  catch (e) { bad.push(it.where + ": " + it.shown + " does not parse (" + String(e.message).split(" at position")[0] + ")"); }
}
process.stdout.write(JSON.stringify(bad));
"""

NOT_TEXT = {"example", "agent_prompt", "plot", "steps", "result", "sha256", "file"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


# ---------- a small DOM, enough to count rows and look up ids ----------
class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.children, self.text = tag, attrs, parent, [], []

    def iter(self):
        yield self
        for c in self.children:
            yield from c.iter()

    def kids(self, tag):
        return [c for c in self.children if c.tag == tag]

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()

    def content(self):
        return "".join(t for n in self.iter() for t in n.text)


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = self.cur = Node("#document", {}, None)
        self.feed(html)
        self.close()
        self.ids = {n.attrs["id"]: n for n in self.root.iter() if n.attrs.get("id")}
        self.html = next((n for n in self.root.iter() if n.tag == "html"), self.root)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: v or "" for k, v in attrs}, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, {k: v or "" for k, v in attrs}, self.cur))

    def handle_endtag(self, tag):
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.cur = node.parent

    def handle_data(self, data):
        self.cur.text.append(data)


# ---------- data ----------
def load_data():
    text = (SITE / "assets" / "data.js").read_text(encoding="utf-8")
    m = re.search(r"window\.WL = (.*);\s*$", text, re.S)
    if not m:
        sys.exit("site/assets/data.js does not define window.WL: rebuild with scripts/build_site.py")
    return json.loads(m.group(1))


def texts(obj, where=""):
    """(where, text) for every string in the site data that contains a dollar sign."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in NOT_TEXT:
                yield from texts(v, f"{where}.{k}" if where else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            label = v["id"] if isinstance(v, dict) and isinstance(v.get("id"), str) else str(i)
            yield from texts(v, f"{where}[{label}]")
    elif isinstance(obj, str) and "$" in obj:
        yield where, obj


class PageText(HTMLParser):
    """The text of a page in the places where KaTeX's auto-render looks for \\( \\) and \\[ \\]."""
    SKIP = {"script", "noscript", "style", "textarea", "pre", "code", "option"}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.depth, self.chunks = 0, []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            self.chunks.append(data)


def page_formulas():
    for page in PAGES:
        for text in PageText((SITE / f"{page['slug']}.html").read_text(encoding="utf-8")).chunks:
            for m in re.finditer(r"\\\[(.+?)\\\]|\\\((.+?)\\\)", text, re.S):
                display = m.group(1) is not None
                yield {"where": f"{page['slug']}.html", "tex": m.group(1) if display else m.group(2),
                       "display": display, "shown": m.group(0).strip()}


# ---------- 1. formulas ----------
def check_formulas(node, data, problems):
    items = list(page_formulas())
    for where, text in texts(data):
        parts = text.split("$")
        if len(parts) % 2 == 0:
            problems.append(f"{where}: odd number of $ in {text[:70]!r}")
        else:
            items += [{"where": where, "tex": t, "shown": f"${t}$"} for t in parts[1::2]]
    with tempfile.TemporaryDirectory(prefix="wl-katex-") as tmp:
        path = Path(tmp) / "formulas.json"
        path.write_text(json.dumps(items), encoding="utf-8")
        r = subprocess.run([node, "-e", KATEX_CHECK, str(KATEX), str(path)],
                           capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    if r.returncode != 0:
        problems.append(f"formulas: Node.js failed: {r.stderr.strip()[-300:]}")
    else:
        problems += json.loads(r.stdout)
    return len(items)


# ---------- 2. pages ----------
def find_browser():
    for name in (os.environ.get("CHROME"), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge"):
        if name and (shutil.which(name) or Path(name).is_file()):
            return shutil.which(name) or name
    for path in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                 r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                 r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                 r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if Path(path).is_file():
            return path
    return None


class CheckHandler(Handler):
    missing = []

    def log_message(self, fmt, *args):
        if len(args) > 1 and str(args[1]).startswith(("4", "5")):
            self.missing.append(f"{args[1]} for {self.path}")


def open_page(browser, url, profile):
    r = subprocess.run([browser, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-first-run",
                        "--no-default-browser-check", f"--user-data-dir={profile}", "--window-size=1280,900",
                        "--virtual-time-budget=10000", "--dump-dom", url],
                       capture_output=True, encoding="utf-8", errors="replace", timeout=180)
    if "<html" not in r.stdout:
        raise RuntimeError(f"the browser returned no page for {url}: {r.stderr.strip()[-300:]}")
    return Page(r.stdout)


def rows(page, tbody_id):
    """The rows of a table body, without the placeholder row of an empty table."""
    node = page.ids.get(tbody_id)
    return [tr for tr in node.kids("tr") if not any(td.has_class("empty") for td in tr.kids("td"))] if node else []


def home(page, data, _):
    out = [f"#{i} has no chart" for i in ("gap", "hero-plot") if i not in page.ids or not any(n.tag == "svg" for n in page.ids[i].iter())]
    if len(page.ids["claims"].kids("li") if "claims" in page.ids else []) < 2:
        out.append("#claims shows fewer than two numbers")
    st = next(s for s in data["settings"] if s["id"] == data["benchmark"])
    claims = [r for r in data["literature"] if r["setting"] == st["id"] and not r.get("verified_by") and not r.get("disputed")]
    shown, want = len(rows(page, "top-rows")), min(5, len(st["entries"]) + len(claims))
    if shown != want:
        out.append(f"#top-rows shows {shown} entries, expected {want}")
    return out


def leaderboard(page, data, sid):
    st = next(s for s in data["settings"] if s["id"] == sid)
    claims = [r for r in data["literature"] if r["setting"] == sid and not r.get("verified_by") and not r.get("disputed")]
    out = []
    shown, want = len(rows(page, "board-rows")), len(st["entries"]) + len(claims)
    if shown != want:
        out.append(f"{shown} controller rows, expected {want} ({len(st['entries'])} verified, {len(claims)} claimed)")
    table = page.ids["board-rows"].content() if "board-rows" in page.ids else ""
    missing = [e["id"] for e in st["entries"] if f"{e['result']['cost']:.9f}" not in table]  # shown to nine decimals
    if missing:
        out.append("verified entries missing from the table: " + ", ".join(missing))
    nb, wb = len(rows(page, "bound-rows")), len(st["lower_bounds"]["bounds"])
    if nb != wb:
        out.append(f"{nb} lower-bound rows, expected {wb}")
    return out


def history(page, data, _):
    out = [f"#{i} draws no points" for i in ("hist-all", "hist-zoom")
           if not any(n.tag == "g" and n.has_class("pt") for n in (page.ids[i].iter() if i in page.ids else []))]
    if len(page.ids["hist-legend"].kids("span") if "hist-legend" in page.ids else []) < 2:
        out.append("#hist-legend is empty")
    return out


def theory(page, data, _):
    shown = len(page.ids["theorylist"].kids("li") if "theorylist" in page.ids else [])
    return [] if shown == len(data["theory"]) else [f"{shown} theory entries shown, expected {len(data['theory'])}"]


def contribute(page, data, _):
    out = []
    if len(page.ids["targets"].kids("li") if "targets" in page.ids else []) < 3:
        out.append("#targets lists fewer than three targets")
    if "example" not in page.ids or not page.ids["example"].content().strip():
        out.append("#example is empty")
    return out


def typeset(page, data, _):
    return [] if any(n.has_class("katex") for n in page.root.iter()) else ["no formula was typeset"]


CONTENT = {"index": home, "problem": typeset, "leaderboard": leaderboard, "verification": typeset,
           "history": history, "theory": theory, "contribute": contribute}


def check_pages(browser, data, problems):
    """Open every page (the leaderboard once per setting); return one opened copy of each page."""
    opened = {}
    with tempfile.TemporaryDirectory(prefix="wl-check-") as tmp:
        site = Path(tmp) / "site"
        shutil.copytree(SITE, site)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(CheckHandler, directory=str(site)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}/"
        for page in PAGES:
            p = site / f"{page['slug']}.html"
            html = p.read_text(encoding="utf-8")
            if "<head>" not in html:
                problems.append(f"{p.name}: no <head>")
                continue
            p.write_text(html.replace("<head>", "<head>\n" + ERROR_HOOK, 1), encoding="utf-8")
        views = 0
        for page in PAGES:
            slug = page["slug"]
            for frag in ([s["id"] for s in data["settings"]] if slug == "leaderboard" else [""]):
                label = f"{slug}.html" + (f"#{frag}" if frag else "")
                CheckHandler.missing = []
                try:
                    view = open_page(browser, base + label, Path(tmp) / "profile")
                except (RuntimeError, subprocess.TimeoutExpired) as exc:
                    problems.append(f"{label}: {exc}")
                    continue
                problems += [f"{label}: the server answered {m}" for m in CheckHandler.missing]
                views += 1
                opened.setdefault(slug, view)
                if view.html.attrs.get("data-check-error"):
                    problems.append(f"{label}: {view.html.attrs['data-check-error']}")
                bad_tex = [n for n in view.root.iter() if n.has_class("katex-error")]
                if bad_tex:
                    problems.append(f"{label}: {len(bad_tex)} formula(s) failed to render, first {bad_tex[0].attrs.get('title', '')[:100]!r}")
                problems += [f"{label}: {msg}" for msg in CONTENT.get(slug, lambda *a: [])(view, data, frag)]
        server.shutdown()
        server.server_close()
    return opened, views


def static_pages():
    return {p["slug"]: Page((SITE / f"{p['slug']}.html").read_text(encoding="utf-8")) for p in PAGES}


# ---------- 3. links ----------
def check_links(pages, data, problems):
    settings = {s["id"] for s in data["settings"]}
    n = 0
    for slug, page in pages.items():
        for a in (x for x in page.root.iter() if x.tag == "a" and x.attrs.get("href")):
            href = a.attrs["href"]
            parts = urlsplit(href)
            if parts.scheme or parts.netloc:
                continue  # another site
            n += 1
            path, frag = unquote(parts.path), unquote(parts.fragment)
            target = SITE / path if path else SITE / f"{slug}.html"
            if not target.is_file():
                problems.append(f"{slug}.html: link {href!r} leads to a file that is not in site/")
                continue
            other = target.stem if target.suffix == ".html" and target.parent == SITE else None
            if not frag or other not in pages or (other == "leaderboard" and frag in settings):
                continue
            if frag not in pages[other].ids:
                problems.append(f"{slug}.html: link {href!r} leads to {other}.html, which has no element with id {frag!r}")
    for s in data["settings"]:
        for e in s["entries"]:
            n += 1
            if not (SITE / e["file"]).is_file():
                problems.append(f"leaderboard.html#{s['id']}: controller file {e['file']} is not in site/")
    return n


def png_size(path):
    head = Path(path).read_bytes()[:24]
    return struct.unpack(">II", head[16:24]) if head[:8] == b"\x89PNG\r\n\x1a\n" else None


def check_previews(pages, problems):
    """The image a shared link shows (og:image) is in site/ and is 1200 x 630."""
    base = json.loads((ROOT / "data" / "site.json").read_text(encoding="utf-8")).get("site_url", "")
    base = base.rstrip("/") + "/" if base else ""
    n = 0
    for slug, page in pages.items():
        tags = {m.attrs.get("property") or m.attrs.get("name"): m.attrs.get("content", "") for m in page.root.iter() if m.tag == "meta"}
        image = tags.get("og:image")
        if not image:
            if base:
                problems.append(f"{slug}.html: no og:image, although data/site.json gives site_url")
            continue
        n += 1
        path = SITE / image[len(base):] if base and image.startswith(base) else None
        if path is None or not path.is_file():
            problems.append(f"{slug}.html: preview image {image} is not in site/")
        elif png_size(path) != (1200, 630):
            problems.append(f"{slug}.html: preview image is {png_size(path)}, expected (1200, 630)")
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check the built site in site/.")
    ap.add_argument("--strict", action="store_true", help="fail if no browser or no Node.js is found, instead of skipping those checks")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    if not (SITE / "index.html").is_file():
        sys.exit("site/ is not built: run python scripts/build_site.py first")
    data = load_data()
    problems = []

    node = shutil.which("node")
    if node:
        print(f"formulas: {check_formulas(node, data, problems)} checked with KaTeX")
    else:
        print("formulas: skipped, Node.js not found")
        if args.strict:
            problems.append("Node.js not found")

    browser = find_browser()
    if browser:
        pages, views = check_pages(browser, data, problems)
        print(f"pages: {views} views opened in {Path(browser).name}")
    else:
        print("pages: skipped, no Chrome, Edge or Chromium found (set CHROME to its path)")
        if args.strict:
            problems.append("no Chrome, Edge or Chromium found")
        pages = static_pages()
    for slug, page in static_pages().items():
        pages.setdefault(slug, page)
    print(f"links: {check_links(pages, data, problems)} checked")
    print(f"link previews: {check_previews(pages, problems)} pages checked")

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
