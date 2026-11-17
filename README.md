# Witsenhausen leaderboard

A verified leaderboard for [Witsenhausen's counterexample](https://en.wikipedia.org/wiki/Witsenhausen%27s_counterexample), a decentralized control problem that has been open since 1968. Every cost here is recomputed by a reference evaluator from a submitted controller file.

The site is written like a short paper split into pages. A home page shows the gap between the best verified cost and the best proven lower bound, and the record controller. Each numbered section is its own page:

1. **The problem** (`problem.html`): the formal statement, with a TikZ block diagram and numbered equations, and the formulas of the lower bounds.
2. **Leaderboard** (`leaderboard.html`): controllers ranked by cost and lower bounds ranked by value, each with an evidence level: *Numerically verified* (the evaluator recomputed the cost from a submitted file), *Peer-reviewed* (a bound proved in a peer-reviewed paper) or *Claimed* (stated but not checked, such as a cost printed in a paper). Tick boxes filter the controllers by evidence level, and a dropdown picks the parameter setting, which the address keeps (`leaderboard.html#k0.50_s5`).
3. **How a cost is verified** (`verification.html`): the evaluator's formulas and its independent checks.
4. **Record history** (`history.html`): a chart of how the best benchmark cost (k = 0.2, σ = 5) has fallen since 1968, separating costs reported in papers from costs verified here.
5. **Theory** (`theory.html`): a log of theoretical results, each marked peer-reviewed or preprint.
6. **Contribute** (`contribute.html`): how to submit, with an example file.

A button in the top bar switches between light and dark; it starts in light mode and remembers the reader's choice. Equations, figures and tables are numbered across the whole site, and references to them link to the right page (for example `problem.html#eq-6`). Mathematics is typeset with KaTeX and the text is set in Latin Modern. Both are bundled in `web/vendor/`, so the site needs no CDN and also works when opened from disk.

## The problem

X0 ~ N(0, σ²) and W ~ N(0, 1) are independent. The first controller sees X0 and sets X1 = f(X0), paying k²·(X1 − X0)². The second controller sees only Y = X1 + W and outputs U2, paying (X1 − U2)². Minimize

    J = k² E[(X1 − X0)²] + E[(X1 − U2)²].

For any f, the best second controller is U2 = E[X1 | Y]. **The evaluator always uses it**, so a submission only describes f.

## How verification works

`witsenhausen/evaluator.py` scores piecewise-affine controllers (jumps allowed), which covers every controller in the literature: steps, sloped steps and sampled tables.

- The first-stage cost and E[X1²] are closed-form sums of truncated-Gaussian moments.
- Given an observation y, every affine piece contributes in closed form to the density of Y and to E[X1 | Y = y]. The only numerical integral left is E[g*(Y)²] over y. It is computed with composite Gauss–Legendre quadrature and then repeated at twice the resolution; the difference is part of the reported error estimate.
- The tests compare the evaluator with independent calculations: the closed-form cost of linear controllers, Witsenhausen's two-point design via 1-D quadrature, Gaussian-mixture costs for flat steps, and brute-force 2-D quadrature for sloped pieces. They agree to within 5×10⁻¹⁰.

On the benchmark, the evaluator reproduces the published values for the best linear controller (0.96) and for Witsenhausen's two-point design (0.404253).

**Record rule.** A verified submission sets a new record only if its cost is below the standing record by more than 10⁻⁹ plus both error estimates. Otherwise it ties.

**Literature values** (`data/literature.json`) appear on the leaderboard as *Claimed*, as printed, with zeros added to nine decimals. When a submitted controller file reproduces one, set its `verified_by` to that entry's id: the paper's claimed row then gives way to the numerically verified entry, which links to the paper.

## Lower bounds

`witsenhausen/bounds.py` computes three bounds, all valid for every controller pair. The site reports the best of them, rounded down:

| Bound | Source |
|---|---|
| Grover–Sahai | Theorem 2 of Grover, Park & Sahai, *The finite-dimensional Witsenhausen counterexample* (arXiv:1003.0514) |
| Grover–Park–Sahai, m = 1 | Theorem 3 of the same paper (sphere-packing bound), scalar case |
| Genie-aided two-point bound | Derived in the module docstring: the second controller is told \|X0\| |

## Submitting a controller

1. Add `submissions/<setting-id>/<your-name>.json`. Folder names are in `data/settings.json` (`k0.20_s5` is the benchmark).
2. Run `python scripts/score_all.py --check` to see your verified cost.
3. Open a pull request. CI re-scores every submission. It fails on malformed files, on a `setting` that does not match the folder, and on a `claimed_cost` more than 10⁻⁶ from the verified cost.

A submission looks like this:

```json
{
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
    "slopes": [0.05, 0.03, 0.02, 0.01]
  }
}
```

Controller formats (`controller.type`):

| Type | Fields | Meaning |
|---|---|---|
| `linear` | `gain` | f(x) = gain · x |
| `piecewise_affine` | `breakpoints` (n−1), `intercepts` (n), `slopes` (n) | f(x) = a_i + b_i x on [t_i, t_{i+1}); the first piece starts at −∞ and the last ends at +∞ |
| `odd_piecewise_affine` | same fields, for x ≥ 0 only | positive breakpoints p_1 < … < p_m, pieces [0, p_1), …, [p_m, ∞), extended by f(−x) = −f(x) |
| `points` | `x`, `y`, optional `odd`, `extrapolation` | linear interpolation through a table; `extrapolation` is `linear` or `constant` |

Text fields such as `name`, `method` and `notes` may contain inline LaTeX between dollar signs, for example `"$f(x)=\\sigma\\,\\mathrm{sgn}(x)$"`. The site renders it with KaTeX.

A prompt for AI agents is written in `scripts/build_site.py` (`AGENT_PROMPT`). It is not shown on the site; set `"show_agent_prompt": true` in `data/site.json` to add it to the Contribute page.

## Running it locally

```bash
pip install -r requirements.txt
python -m pytest -q                   # evaluator tests (about a minute)
python -m witsenhausen score submissions/k0.20_s5/reference-curved-steps.json
python scripts/score_all.py           # re-score everything -> data/results.json
python scripts/build_site.py          # -> site/ (open site/index.html in a browser)
python scripts/serve.py --open        # serve site/ at http://localhost:2000
```

On Windows you can also double-click `serve.bat`, which serves the site at http://localhost:2000 and opens it in your browser. The server only listens on this computer (127.0.0.1); close its window to stop it.

The site build needs only the Python standard library. It fills `web/layout.html` with each file in `web/pages/` and writes one page per section to `site/`, writes `site/assets/` (the shared `site.css` and `site.js`, and `data.js`, which holds the scores for the pages that draw charts and tables), copies `web/vendor/` to `site/vendor/` and copies `submissions/` to `site/submissions/`, so controller files can be downloaded from the site. The list of pages, their titles and their order is `PAGES` in `scripts/build_site.py`; the navigation and the previous and next links are generated from it.

**The diagram.** `web/figures/problem.tex` is the TikZ source of the block diagram. The compiled `web/figures/problem.svg` is committed, so neither the build nor CI needs TeX. After editing the `.tex` file, run `python scripts/build_figures.py` (needs `pdflatex` with TikZ and `pdftocairo`).

`scripts/make_baselines.py` regenerates the exact baselines (best linear, two-point). `scripts/optimize_reference.py` is the reference optimizer behind the "curved sloped steps" entries. It needs `pip install "jax[cpu]"`.

## Publishing on GitHub Pages

The site is published from https://github.com/hassanmunif/witsenhausen-leaderboard to https://hassanmunif.github.io/witsenhausen-leaderboard/.

First time:

1. On GitHub, create an empty public repository named `witsenhausen-leaderboard` (no README, licence or .gitignore).
2. In its **Settings → Pages**, choose **GitHub Actions** as the source.
3. On Windows, double-click `publish.bat`. It copies the workflows from `ci/workflows/` into `.github/workflows/` (the only place GitHub looks for them), creates the git repository, commits with GitHub's private noreply address and pushes. Git asks you to sign in to GitHub the first time.

After that, double-click `publish.bat` whenever you change something. Every push to `main` runs the tests, re-scores all submissions, rebuilds the site and deploys it (`pages.yml`); pull requests only run the checks (`verify.yml`). On another system, run `python scripts/install_workflows.py` once, then commit and push with git as usual.

## Layout

```
witsenhausen/        evaluator, controller formats, lower bounds (numpy + scipy only)
tests/               evaluator correctness tests
submissions/<id>/    one JSON file per controller and setting
data/settings.json   parameter settings and the record rule
data/literature.json results as reported in papers
data/theory.json     theoretical results
data/bounds.json     cached lower bounds (generated)
data/results.json    verified scores (generated)
web/layout.html      page shell shared by every page (navigation, footer, scripts)
web/pages/           the content of each page (index, problem, leaderboard, ...)
web/site.css         styles for every page
web/site.js          charts, tables and maths rendering
web/figures/         TikZ source of the diagram and its compiled SVG
web/vendor/          KaTeX and the Latin Modern fonts (third-party; see web/vendor/README.md)
ci/workflows/        GitHub Actions workflows (copy to .github/workflows/ with scripts/install_workflows.py)
site/                built site (generated, not committed: GitHub builds it)
scripts/             scoring, site build, figure build, baselines, reference optimizer
```

## Licence

MIT, see `LICENSE`.
