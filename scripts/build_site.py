#!/usr/bin/env python3
"""Build the static site in site/ from web/ and data/*.json.

Run scripts/score_all.py first so data/results.json is current.  The build
needs only the Python standard library:

* web/layout.html + web/pages/<page>.html -> site/<page>.html, one file per page
* web/site.css, web/site.js               -> site/assets/
* data/*.json                             -> site/assets/data.js, read by the pages that draw charts and tables
* web/figures/preview.png                -> site/assets/       (the image shown when a link is shared)
* web/vendor/                             -> site/vendor/       (KaTeX and the Latin Modern fonts)
* submissions/                            -> site/submissions/  (so controller files can be downloaded)

The site uses no CDN, so the pages also work opened from disk (site/index.html).
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SITE = ROOT / "site"

# One entry per page, in the order of the links in the top bar. The home page has no link of its own:
# the site title and its logo lead to it. "data" says whether the page needs assets/data.js.
PAGES = [
    {"slug": "index", "nav": None, "title": None, "data": True,
     "description": "A verified leaderboard for Witsenhausen's counterexample: the best controllers found so far, "
                    "proven lower bounds, and the history of records."},
    {"slug": "leaderboard", "nav": "Leaderboard", "title": "Leaderboard", "data": True,
     "description": "Controllers for Witsenhausen's counterexample ranked by cost, each marked claimed or numerically verified, "
                    "and the proven lower bounds."},
    {"slug": "problem", "nav": "Problem", "title": "The problem", "data": False,
     "description": "The formal statement of Witsenhausen's counterexample, why it is hard, its reduction to a single function, and lower bounds."},
    {"slug": "verification", "nav": "Verification", "title": "Verification", "data": False,
     "description": "How the reference evaluator computes the cost of a piecewise-affine controller for Witsenhausen's "
                    "counterexample, and the checks it passes."},
    {"slug": "history", "nav": "History", "title": "Record history on the benchmark", "data": True,
     "description": "How the best cost on the Witsenhausen benchmark k = 0.2, sigma = 5 has fallen since 1968, claimed in papers and numerically verified."},
    {"slug": "theory", "nav": "Theory", "title": "What is known about the optimum", "data": True,
     "description": "Results about the optimal controllers for Witsenhausen's counterexample: existence, structure, complexity and bounds."},
    {"slug": "contribute", "nav": "Contribute", "title": "Contribute", "data": True,
     "description": "How to submit a controller for Witsenhausen's counterexample, with an example file and what would count as progress."},
    {"slug": "about", "nav": "About", "title": "About", "data": False,
     "description": "Who maintains the Witsenhausen leaderboard, how to reach them, what is listed, how disputed claims are handled, and how to cite it."},
]

EXAMPLE = {
    "schema": "witsenhausen-controller/v1",
    "name": "My sloped steps",
    "authors": ["Your Name"],
    "date": "2026-11-16",
    "setting": {"k": 0.2, "sigma": 5.0},
    "method": "How you found it, in one sentence",
    "source": {"kind": "code", "url": "https://github.com/you/your-code"},
    "claimed_cost": 0.168096953,
    "controller": {
        "type": "odd_piecewise_affine",
        "breakpoints": [3.2, 9.6, 16.1],
        "intercepts": [0.0, 6.3, 12.8, 19.6],
        "slopes": [0.05, 0.03, 0.02, 0.01],
    },
}

AGENT_PROMPT = """Goal: beat the verified record on Witsenhausen's counterexample.

Problem: x0 ~ N(0, sigma^2) and w ~ N(0, 1) are independent. The first controller sets x1 = f(x0); the second sees y = x1 + w. The cost is J(f) = k^2 E[(x1 - x0)^2] + E[(x1 - E[x1 | y])^2]. Benchmark: k = 0.2, sigma = 5. Current verified record: {record} (see data/results.json).

1. Clone {repo} and run: pip install -r requirements.txt
2. Score candidates only with witsenhausen.evaluate(f, k, sigma). Build f with witsenhausen.odd_piecewise_affine(...) or witsenhausen.PiecewiseAffine(...). Do not edit the evaluator or the tests.
3. A new record must beat {record} by more than 1e-9 plus both error estimates.
4. If you beat it, write submissions/k0.20_s5/<your-name>.json (schema witsenhausen-controller/v1, with "method", "claimed_cost" and "ai_assistance", one sentence naming the AI model and what it did), run python scripts/score_all.py --check, and open a pull request.
5. If you do not beat it, report the best verified cost you reached and what you tried.
"""


def compact_json(obj, indent=2):
    """Pretty JSON with short lists and small objects kept on one line."""
    def fmt(o, level):
        pad = " " * (indent * level)
        if isinstance(o, dict):
            inline = json.dumps(o, ensure_ascii=False)
            if len(inline) <= 60 and not any(isinstance(v, (dict, list)) for v in o.values()):
                return inline
            items = [f'{pad}{" " * indent}{json.dumps(k)}: {fmt(v, level + 1)}' for k, v in o.items()]
            return "{\n" + ",\n".join(items) + "\n" + pad + "}"
        return json.dumps(o, ensure_ascii=False)
    return fmt(obj, 0)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fill(template: str, values: dict, where: str) -> str:
    """Replace every __NAME__ in one pass, so inserted text is never scanned again."""
    def sub(m):
        if m.group(1) not in values:
            raise KeyError(f"{where}: no value for __{m.group(1)}__")
        return values[m.group(1)]
    return re.sub(r"__([A-Z][A-Z0-9_]*)__", sub, template)


def version(text: str) -> str:
    """Short content hash, appended to asset URLs so a new build is never mixed with a cached old file."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def repo_configured(url: str) -> bool:
    return bool(re.match(r"^https?://", url or "")) and "YOUR-GITHUB-USERNAME" not in url


def nav_html(current: str) -> str:
    links = []
    for p in PAGES[1:]:
        here = ' aria-current="page"' if p["slug"] == current else ""
        links.append(f'<a href="{p["slug"]}.html"{here}>{html.escape(p["nav"])}</a>')
    return "\n      ".join(links)


# The site's mark in the top bar: the staircase of the favicon (web/layout.html). It sits inside the link
# to the home page, so the title reads as a logo. Its colours are set in site.css.
LOGO = ('<svg class="logo" viewBox="0 0 32 32" aria-hidden="true" focusable="false">'
        '<rect class="tile" width="32" height="32" rx="5"/><path d="M5 25h7v-7h7v-7h8"/></svg>')

PREVIEW_ALT = ("The words Witsenhausen leaderboard beside a staircase-shaped controller: "
               "verified progress on a control problem open since 1968.")


def social_html(site: dict, page: dict, title: str) -> str:
    """Open Graph and Twitter tags, so a shared link shows a title, a description and an image.
    They need absolute addresses, so they are left out until data/site.json gives site_url."""
    base = site.get("site_url", "")
    if not re.match(r"^https?://", base):
        return ""
    base = base.rstrip("/") + "/"
    url = base if page["slug"] == "index" else f'{base}{page["slug"]}.html'
    e = html.escape
    return "\n".join([
        f'<link rel="canonical" href="{e(url)}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{e(site["title"])}">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(page["description"])}">',
        f'<meta property="og:url" content="{e(url)}">',
        f'<meta property="og:image" content="{e(base)}assets/preview.png">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{e(PREVIEW_ALT)}">',
        '<meta name="twitter:card" content="summary_large_image">',
    ])


def main():
    site = load(ROOT / "data" / "site.json")
    results = load(ROOT / "data" / "results.json")
    literature = load(ROOT / "data" / "literature.json")["results"]
    theory = load(ROOT / "data" / "theory.json")["entries"]

    bench = next(s for s in results["settings"] if s["id"] == results["benchmark"])
    record = next((e for e in bench["entries"] if e["id"] == bench["record_id"]), None)
    record_txt = f"{record['result']['cost']:.9f}" if record else "(none yet)"
    repo = site.get("repo_url", "")

    # ---- shared assets ----
    data = {
        "site": {**site, "generated_at": results["generated_at"], "evaluator_version": results["evaluator_version"]},
        "benchmark": results["benchmark"],
        "record_rule": results["record_rule"],
        "settings": results["settings"],
        "literature": literature,
        "theory": theory,
        "example": compact_json(EXAMPLE),
    }
    # The prompt for AI agents is only published when data/site.json says so.
    show_prompt = bool(site.get("show_agent_prompt"))
    if show_prompt:
        data["agent_prompt"] = AGENT_PROMPT.format(record=record_txt, repo=repo)
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    blob = blob.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    assets = {
        "site.css": (WEB / "site.css").read_text(encoding="utf-8"),
        "site.js": (WEB / "site.js").read_text(encoding="utf-8"),
        "data.js": "/* Generated by scripts/build_site.py from data/*.json; do not edit. */\nwindow.WL = " + blob + ";\n",
    }
    v = {name: version(text) for name, text in assets.items()}

    # ---- pieces every page shares ----
    generated = results["generated_at"]
    footer = [f'<span>Evaluator v{results["evaluator_version"]}</span>',
              f'<span>Scores generated {generated.replace("T", " ").replace("Z", " UTC")}</span>']
    repo_link = ""
    if repo_configured(repo):
        footer.append(f'<a href="{html.escape(repo)}" rel="noopener">GitHub repo</a>')
        repo_link = f'<a class="gh" href="{html.escape(repo)}" rel="noopener">Repository</a>'
    author = site.get("author") or {}
    if author.get("name"):
        name = html.escape(author["name"])
        if re.match(r"^https?://", author.get("url", "")):
            name = f'<a href="{html.escape(author["url"])}" rel="author">{name}</a>'
        footer.append(f'<span class="credit">Created by {name}</span>')
    page_values = {
        "AGENT_PROMPT": ('  <div>\n    <div class="prehead"><h2>Prompt for an AI agent</h2><button class="btn" id="copy-prompt">Copy prompt</button></div>\n    <pre class="wrapped"><code id="prompt"></code></pre>\n  </div>' if show_prompt else ""),
        "FIGURE_PROBLEM": (WEB / "figures" / "problem.svg").read_text(encoding="utf-8"),
        "REPO_URL": html.escape(repo.rstrip("/")),
    }

    layout = (WEB / "layout.html").read_text(encoding="utf-8")
    SITE.mkdir(exist_ok=True)
    written = []
    for page in PAGES:
        slug = page["slug"]
        content = fill((WEB / "pages" / f"{slug}.html").read_text(encoding="utf-8"), page_values, f"web/pages/{slug}.html")
        scripts = ([f'<script src="assets/data.js?v={v["data.js"]}"></script>'] if page["data"] else []) + [
            '<script src="vendor/katex/katex.min.js"></script>',
            '<script src="vendor/katex/contrib/auto-render.min.js"></script>',
            f'<script src="assets/site.js?v={v["site.js"]}"></script>']
        here = ' aria-current="page"' if slug == "index" else ""
        title = site["title"] if slug == "index" else f'{page["title"]} – {site["title"]}'
        out = fill(layout, {
            "TITLE": html.escape(title),
            "DESCRIPTION": html.escape(page["description"]),
            "SOCIAL": social_html(site, page, title),
            "CSS_VERSION": v["site.css"],
            "PAGE": slug,
            "BRAND": f'<a class="brand" href="index.html"{here}>{LOGO}<span>{html.escape(site["title"])}</span></a>',
            "NAV": nav_html(slug),
            "REPO_LINK": repo_link,
            "CONTENT": content.rstrip("\n"),
            "FOOTER": "".join(footer),
            "SCRIPTS": "\n".join(scripts),
        }, "web/layout.html")
        (SITE / f"{slug}.html").write_text(out, encoding="utf-8")
        written.append(f"{slug}.html")

    (SITE / "assets").mkdir(exist_ok=True)
    for name, text in assets.items():
        (SITE / "assets" / name).write_text(text, encoding="utf-8")
    shutil.copy2(WEB / "figures" / "preview.png", SITE / "assets" / "preview.png")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    shutil.copytree(WEB / "vendor", SITE / "vendor", dirs_exist_ok=True)
    shutil.copytree(ROOT / "submissions", SITE / "submissions", dirs_exist_ok=True)
    print(f"wrote {len(written)} pages to site/ ({', '.join(written)}), "
          f"site/assets/ (data.js {len(assets['data.js']) / 1024:.0f} KB), site/vendor/ and site/submissions/")


if __name__ == "__main__":
    main()
