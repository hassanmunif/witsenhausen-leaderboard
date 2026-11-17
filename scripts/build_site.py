#!/usr/bin/env python3
"""Build the static site in site/ from web/ and data/*.json.

Run scripts/score_all.py first so data/results.json is current.  The build
needs only the Python standard library:

* web/layout.html + web/pages/<page>.html -> site/<page>.html, one file per page
* web/site.css, web/site.js               -> site/assets/
* data/*.json                             -> site/assets/data.js, read by the pages that draw charts and tables
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

# One entry per page, in reading order.  "no" is the section number shown in titles,
# "data" says whether the page needs assets/data.js, and "summary" is its line in the
# contents on the home page (it may contain \( \) maths).
PAGES = [
    {"slug": "index", "nav": None, "no": None, "title": None, "data": True,
     "description": "A verified leaderboard for Witsenhausen's counterexample: the best controllers found so far, "
                    "proven lower bounds, and the history of records."},
    {"slug": "problem", "nav": "Problem", "no": 1, "title": "The problem", "data": False,
     "description": "The formal statement of Witsenhausen's counterexample, why it is hard, its reduction to a single function, and lower bounds.",
     "summary": r"The formal definition, why the information structure makes it hard, the reduction to one function \(f\), and the lower bounds."},
    {"slug": "leaderboard", "nav": "Leaderboard", "no": 2, "title": "Leaderboard", "data": True,
     "description": "Controllers for Witsenhausen's counterexample ranked by cost, each marked claimed or numerically verified, "
                    "and the proven lower bounds.",
     "summary": "Controllers ranked by cost, each marked claimed or numerically verified, and the proven lower bounds."},
    {"slug": "verification", "nav": "Verification", "no": 3, "title": "How a cost is verified", "data": False,
     "description": "How the reference evaluator computes the cost of a piecewise-affine controller for Witsenhausen's "
                    "counterexample, and the checks it passes.",
     "summary": "How the reference evaluator computes a cost from a controller file, with an error estimate, and the independent checks it passes."},
    {"slug": "history", "nav": "History", "no": 4, "title": "Record history on the benchmark", "data": True,
     "description": "How the best cost on the Witsenhausen benchmark k = 0.2, sigma = 5 has fallen since 1968, claimed in papers and numerically verified.",
     "summary": "How the best benchmark cost has fallen since 1968, claimed in papers and numerically verified here."},
    {"slug": "theory", "nav": "Theory", "no": 5, "title": "What is known about the optimum", "data": True,
     "description": "Results about the optimal controllers for Witsenhausen's counterexample: existence, structure, complexity and bounds.",
     "summary": "Existence, structure, complexity and bounds: results about the optimum itself, each marked peer-reviewed or preprint."},
    {"slug": "contribute", "nav": "Contribute", "no": 6, "title": "Contribute", "data": True,
     "description": "How to submit a controller for Witsenhausen's counterexample, with an example file and a prompt for AI agents.",
     "summary": "How to submit a controller file, a prompt to hand to an AI agent, and what would count as progress."},
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
4. If you beat it, write submissions/k0.20_s5/<your-name>.json (schema witsenhausen-controller/v1, with "method" and "claimed_cost"), run python scripts/score_all.py --check, and open a pull request.
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


def numbered(page: dict) -> str:
    return f'<span class="no">{page["no"]}</span>{html.escape(page["title"])}'


def nav_html(current: str) -> str:
    links = []
    for p in PAGES[1:]:
        here = ' aria-current="page"' if p["slug"] == current else ""
        links.append(f'<a href="{p["slug"]}.html"{here}>{html.escape(p["nav"])}</a>')
    return "\n      ".join(links)


def pager_html(i: int) -> str:
    """Previous and next section at the foot of each section page; the home page has the contents instead."""
    if i == 0:
        return ""
    links = []
    if i > 1:
        p = PAGES[i - 1]
        links.append(f'<a class="prev" href="{p["slug"]}.html" rel="prev"><span class="dir">Previous</span><span class="t">{numbered(p)}</span></a>')
    if i + 1 < len(PAGES):
        p = PAGES[i + 1]
        links.append(f'<a class="next" href="{p["slug"]}.html" rel="next"><span class="dir">Next</span><span class="t">{numbered(p)}</span></a>')
    return '<nav class="pager" aria-label="Previous and next section">\n  ' + "\n  ".join(links) + "\n</nav>"


def toc_html() -> str:
    items = []
    for p in PAGES[1:]:
        items.append(f'    <li><a class="t" href="{p["slug"]}.html">{numbered(p)}</a><p>{html.escape(p["summary"], quote=False)}</p></li>')
    return "\n".join(items)


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
        "agent_prompt": AGENT_PROMPT.format(record=record_txt, repo=repo),
    }
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
    n_entries = sum(len(s["entries"]) for s in results["settings"])
    footer = [f'<span>Evaluator v{results["evaluator_version"]}</span>',
              f'<span>Scores generated {generated.replace("T", " ").replace("Z", " UTC")}</span>',
              "<span>Set in Latin Modern, mathematics by KaTeX, Figure 2 drawn with Ti<i>k</i>Z</span>"]
    repo_link = ""
    if repo_configured(repo):
        footer.append(f'<a href="{html.escape(repo)}" rel="noopener">Source and submissions on GitHub</a>')
        repo_link = f'<a class="gh" href="{html.escape(repo)}" rel="noopener">Repository</a>'
    author = site.get("author") or {}
    if author.get("name"):
        name = html.escape(author["name"])
        if re.match(r"^https?://", author.get("url", "")):
            name = f'<a href="{html.escape(author["url"])}" rel="author">{name}</a>'
        footer.append(f'<span class="credit">Created by {name}</span>')
    page_values = {
        "META": html.escape(f"Scores generated {generated[:10]} with evaluator v{results['evaluator_version']}. "
                            f"{n_entries} verified controllers across {len(results['settings'])} parameter settings."),
        "TOC": toc_html(),
        "FIGURE_PROBLEM": (WEB / "figures" / "problem.svg").read_text(encoding="utf-8"),
    }

    layout = (WEB / "layout.html").read_text(encoding="utf-8")
    SITE.mkdir(exist_ok=True)
    written = []
    for i, page in enumerate(PAGES):
        slug = page["slug"]
        content = fill((WEB / "pages" / f"{slug}.html").read_text(encoding="utf-8"), page_values, f"web/pages/{slug}.html")
        scripts = ([f'<script src="assets/data.js?v={v["data.js"]}"></script>'] if page["data"] else []) + [
            '<script src="vendor/katex/katex.min.js"></script>',
            '<script src="vendor/katex/contrib/auto-render.min.js"></script>',
            f'<script src="assets/site.js?v={v["site.js"]}"></script>']
        here = ' aria-current="page"' if slug == "index" else ""
        out = fill(layout, {
            "TITLE": html.escape(site["title"] if slug == "index" else f'{page["title"]} – {site["title"]}'),
            "DESCRIPTION": html.escape(page["description"]),
            "CSS_VERSION": v["site.css"],
            "PAGE": slug,
            "BRAND": f'<a class="brand" href="index.html"{here}>{html.escape(site["title"])}</a>',
            "NAV": nav_html(slug),
            "REPO_LINK": repo_link,
            "CONTENT": content.rstrip("\n"),
            "PAGER": pager_html(i),
            "FOOTER": "".join(footer),
            "SCRIPTS": "\n".join(scripts),
        }, "web/layout.html")
        (SITE / f"{slug}.html").write_text(out, encoding="utf-8")
        written.append(f"{slug}.html")

    (SITE / "assets").mkdir(exist_ok=True)
    for name, text in assets.items():
        (SITE / "assets" / name).write_text(text, encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    shutil.copytree(WEB / "vendor", SITE / "vendor", dirs_exist_ok=True)
    shutil.copytree(ROOT / "submissions", SITE / "submissions", dirs_exist_ok=True)
    print(f"wrote {len(written)} pages to site/ ({', '.join(written)}), "
          f"site/assets/ (data.js {len(assets['data.js']) / 1024:.0f} KB), site/vendor/ and site/submissions/")


if __name__ == "__main__":
    main()
