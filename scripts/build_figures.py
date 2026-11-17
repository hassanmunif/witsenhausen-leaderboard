#!/usr/bin/env python3
"""Compile the TikZ figures in web/figures/*.tex to SVG.

Needs pdflatex (with TikZ and the standalone class) and pdftocairo (poppler).
The compiled SVGs are committed, so the site build and CI do not need TeX;
run this only after editing a .tex file:

    python scripts/build_figures.py

Glyphs are converted to outlines, and black is replaced by ``currentColor`` so
the figure follows the page's text colour (light and dark mode).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIGS = ROOT / "web" / "figures"

BLACK = re.compile(r"rgb\(0%,\s*0%,\s*0%\)|#000000\b|#000\b")


def themeable(svg: str, prefix: str) -> str:
    svg = re.sub(r"<\?xml[^>]*\?>\s*", "", svg)
    svg = BLACK.sub("currentColor", svg)
    # make ids unique to this figure so several can be inlined in one page
    ids = set(re.findall(r'\bid="([^"]+)"', svg))
    for i in sorted(ids, key=len, reverse=True):
        svg = svg.replace(f'id="{i}"', f'id="{prefix}-{i}"')
        svg = svg.replace(f'"#{i}"', f'"#{prefix}-{i}"')
        svg = svg.replace(f"url(#{i})", f"url(#{prefix}-{i})")
    return svg.strip() + "\n"


def build(tex: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        run = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={tmp}", str(tex)],
            capture_output=True, text=True, cwd=tex.parent,
        )
        if run.returncode != 0:
            sys.exit(f"pdflatex failed for {tex.name}:\n{run.stdout[-2000:]}")
        pdf = tmp / (tex.stem + ".pdf")
        out = tmp / (tex.stem + ".svg")
        subprocess.run(["pdftocairo", "-svg", str(pdf), str(out)], check=True)
        svg = themeable(out.read_text(encoding="utf-8"), tex.stem)
    (FIGS / (tex.stem + ".svg")).write_text(svg, encoding="utf-8")
    print(f"wrote web/figures/{tex.stem}.svg ({len(svg) / 1024:.0f} KB)")


def main():
    for tool in ("pdflatex", "pdftocairo"):
        if shutil.which(tool) is None:
            sys.exit(f"{tool} not found; install TeX Live and poppler-utils to rebuild figures")
    for tex in sorted(FIGS.glob("*.tex")):
        build(tex)


if __name__ == "__main__":
    main()
