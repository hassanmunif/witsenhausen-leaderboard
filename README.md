# Witsenhausen leaderboard

A verified leaderboard for [Witsenhausen's counterexample](https://en.wikipedia.org/wiki/Witsenhausen%27s_counterexample), a decentralized control problem that has been open since 1968. Every cost here is recomputed by a reference evaluator from a submitted controller file.

**Site:** https://hassanmunif.github.io/witsenhausen-leaderboard/

**Maintainer:** Hassan Munif, CRAN (UMR 7039), CNRS, Université de Lorraine. Corrections, missing results and controller files are welcome by email (hassan.munif0@gmail.com), as an issue, or as a pull request.

The site is written like a short paper split into pages. A home page shows the gap between the best verified cost and the best proven lower bound, and the record controller. Each numbered section is its own page:

1. **The problem** (`problem.html`): the formal statement, with a TikZ block diagram and numbered equations, and the formulas of the lower bounds.
2. **Leaderboard** (`leaderboard.html`): controllers ranked by cost and lower bounds ranked by value, each with an evidence level: *Numerically verified* (the evaluator recomputed the cost from a submitted file), *Peer-reviewed* (a bound proved in a peer-reviewed paper) or *Claimed* (stated but not checked, such as a cost printed in a paper). A claimed cost with evidence against it is marked *disputed* and is hidden unless its box is ticked. Tick boxes filter the controllers by evidence level, and a dropdown picks the parameter setting, which the address keeps (`leaderboard.html#k0.50_s5`).
3. **How a cost is verified** (`verification.html`): the evaluator's formulas and its independent checks.
4. **Record history** (`history.html`): a chart of how the best benchmark cost (k = 0.2, σ = 5) has fallen since 1968, separating costs reported in papers from costs verified here.
5. **Theory** (`theory.html`): a log of theoretical results, each marked peer-reviewed or preprint.
6. **Contribute** (`contribute.html`): how to submit, with an example file.

An unnumbered **About** page (`about.html`) says who maintains the site, how to reach them, what is listed, how disputed claims are handled, and how to cite the leaderboard.

Equations, figures and tables are numbered across the whole site, and references to them link to the right page (for example `problem.html#eq-6`). Mathematics is typeset with KaTeX and the text is set in Latin Modern. Both are bundled in `web/vendor/`, so the site needs no CDN and also works when opened from disk.

## The problem

X0 ~ N(0, σ²) and W ~ N(0, 1) are independent. The first controller sees X0 and sets X1 = f(X0), paying k²·(X1 − X0)². The second controller sees only Y = X1 + W and outputs U2, paying (X1 − U2)². Minimize

    J = k² E[(X1 − X0)²] + E[(X1 − U2)²].

For any f, the best second controller is U2 = E[X1 | Y]. **The evaluator always uses it**, so a submission only describes f.

## How verification works

`witsenhausen/evaluator.py` scores piecewise-affine controllers (jumps allowed). Steps and sloped steps are represented exactly; any other controller can be submitted as a piecewise-affine approximation, such as a sampled table, and the score is the exact cost of the submitted function.

- The first-stage cost and E[X1²] are closed-form sums of truncated-Gaussian moments.
- Given an observation y, every affine piece contributes in closed form to the density of Y and to E[X1 | Y = y]. The only numerical integral left is E[g*(Y)²] over y. It is computed with composite Gauss–Legendre quadrature and then repeated at twice the resolution; the difference is part of the reported error estimate.
- The tests compare the evaluator with independent calculations: the closed-form cost of linear controllers, Witsenhausen's two-point design via 1-D quadrature, Gaussian-mixture costs for flat steps, and brute-force 2-D quadrature for sloped pieces. They agree to within 5×10⁻¹⁰.

On the benchmark, the evaluator reproduces the published values for the best linear controller (0.96) and for Witsenhausen's two-point design (0.404253).

**Record rule.** A verified submission sets a new record only if its cost is below the standing record by more than 10⁻⁹ plus both error estimates. Otherwise it ties. Records are taken in order of `date`, so the record goes to the first result that reached it. On the leaderboard the record holder is tagged *record*, and verified costs that the rule cannot separate share a rank, shown as =1, with the record holder first.

**Costs from papers** (`data/literature.json`) appear on the leaderboard as *Claimed*, as printed. If your submission reproduces one of them, say so in the pull request: the paper's row is then shown as reproduced by your verified entry (its `verified_by` field is set to your submission), whose details keep the printed cost.

**Controllers from papers.** A file that reproduces a published controller keeps the paper's authors in `authors` and the paper's date in `date`, and adds `ported_by` (who made the file) and `verified_on` (the day it was first scored here). The leaderboard then shows the paper's year, and the details show both. The files for Deng & Ho (1999) and Bansal & Başar (1987) at the benchmark are written by hand from the parameters in their notes. Zhu's (2026) controllers are made by `scripts/ports/zhu_2026.py` from the paper's ancillary data.

**Disputed claims.** If there is evidence that a printed cost is not the cost of the paper's controller, the row gets a `disputed` record: `date`, a one-sentence `reason`, and `note`, the path of a Markdown note in `notes/` that explains the check and links its scripts. The row stays *Claimed* with its printed cost. It is hidden on the leaderboard unless *Disputed* is ticked, is drawn as a ring on the history chart, and never counts as the best claimed cost. The first one is `notes/tseng-tang-2017.md`, checked by the scripts in `scripts/reexamine/`.

## Lower bounds

`witsenhausen/bounds.py` computes four proven bounds, all valid for every controller pair. Their values are computed numerically, and the site reports the strongest of them, rounded down:

| Bound | Source |
|---|---|
| Grover–Sahai | Theorem 2 of Grover, Park & Sahai, *The finite-dimensional Witsenhausen counterexample* (arXiv:1003.0514) |
| Grover–Park–Sahai, m = 1 | Theorem 3 of the same paper (sphere-packing bound), scalar case |
| Witsenhausen's bound | Theorem 3 of Witsenhausen (1968): the second controller is told \|X0\|. Generalised by Wu & Verdú (2011), Theorem 4 |
| Grover–Wagner–Sahai, m = 1 | Corollary 1 of Grover, Wagner & Sahai, *Information embedding and the triple role of control* (IEEE Trans. Inf. Theory, 2015; arXiv:1306.5018), which holds for every vector length. Fixing γ and relaxing the corollary's infimum gives a closed form, and every γ in (0, 1) gives a valid bound. `tests/test_bounds.py` checks it against a direct minimisation of the corollary |

## Submitting a controller

1. Add `submissions/<setting-id>/<your-name>.json`. Folder names are in `data/settings.json` (`k0.20_s5` is the benchmark).
2. Run `python scripts/score_all.py --check` to see your verified cost.
3. Open a pull request. CI runs the tests, re-scores every submission, builds the site and checks its pages (see *Checks* below). It fails on malformed files, on a `setting` that does not match the folder, on dates not written YYYY-MM-DD, on controllers too large to evaluate quickly (more than 100,000 pieces, or values spread too widely), on results that cannot be right (non-finite, negative, or an error estimate above 10⁻⁶), and on a `claimed_cost` that is not a number or is more than 10⁻⁶ from the verified cost.
4. After the merge, GitHub Actions does the same again and redeploys the site, and your entry appears with its verified cost.

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

Dates are written YYYY-MM-DD. `date` is when the result first appeared. Two optional fields are for controllers taken from papers: `ported_by` names whoever made the file when that is not the authors, and `verified_on` is the day it was first scored here (not earlier than `date`).

Text fields such as `name`, `method` and `notes` may contain inline LaTeX between dollar signs, for example `"$f(x)=\\sigma\\,\\mathrm{sgn}(x)$"`. The site renders it with KaTeX.

## Checking a controller locally

```bash
pip install -r requirements.txt
python -m pytest -q                   # evaluator, scorer and data tests (about a minute)
python -m witsenhausen score submissions/k0.20_s5/reference-curved-steps.json
python scripts/score_all.py --check   # re-score every submission -> data/results.json
```

## Checks

The same checks run on every pull request (`verify.yml`) and on every push to `main` before the site is deployed (`pages.yml`), so a change that breaks them never goes live:

- `python -m pytest -q` tests the evaluator and the scorer, and `tests/test_data.py` checks that the data files agree: every `verified_by` names a submission in the same setting, every printed cost matches its number, disputed claims have a reason and an existing note, the theory log is in order, dollar signs come in pairs, every setting has submissions, and `data/bounds.json` matches the code (a changed bound needs a new `BOUNDS_VERSION`).
- `python scripts/check_site.py` checks the built site. It parses every formula on the pages and in the data with the bundled KaTeX (needs Node.js), opens every page, and the leaderboard of every setting, in headless Chrome, Edge or Chromium (served from a local web server), and fails on a script error, a file that does not load, a formula that does not render, or a table or chart that is not drawn. It also follows every link inside the site, including anchors such as `problem.html#eq-6`. Without a browser or Node.js it skips those parts; CI runs it with `--strict`, which fails instead.

To run them locally: `python -m pytest -q`, then `python scripts/build_site.py` and `python scripts/check_site.py`.

## Previewing the site

```bash
python scripts/serve.py --open        # builds site/ if needed and serves it at http://localhost:2000
python scripts/build_site.py          # rebuild site/ after changing data/ or web/
```

The site build needs only the Python standard library. It fills `web/layout.html` with each page in `web/pages/`, adds the shared `site.css`, `site.js` and the scores (`data.js`), and copies the fonts, KaTeX and the submission files into `site/`. The pages, their titles and their order are `PAGES` in `scripts/build_site.py`.

**The diagram.** `web/figures/problem.tex` is the TikZ source of the block diagram. The compiled `web/figures/problem.svg` is committed, so neither the build nor CI needs TeX. After editing the `.tex` file, run `python scripts/build_figures.py` (needs `pdflatex` with TikZ and `pdftocairo`).

**Link previews.** Every page carries Open Graph and Twitter tags, so a shared link shows its title, description and `web/figures/preview.png`. The tags need the site's full address, `site_url` in `data/site.json`: change it there if the site moves, for example to its own domain. The image holds no numbers, so it does not go stale. Its source is `web/figures/preview.html`; after editing it, run `python scripts/build_preview.py` (needs Chrome, Edge or Chromium).

`scripts/make_baselines.py` regenerates the exact baselines (best linear, two-point). `scripts/ports/` holds the scripts that turn controllers published in papers into submission files. `scripts/optimize_reference.py` is the reference optimizer behind the "curved sloped steps" entries. It needs `pip install "jax[cpu]"`.

`scripts/reexamine/` holds the checks behind disputed claims. Each runs from the repository root in under a minute, for example `python scripts/reexamine/tseng_tang_tails.py`.

## Layout

```
witsenhausen/        evaluator, controller formats, lower bounds (numpy + scipy only)
tests/               tests of the evaluator, the scorer and the data files
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
web/figures/         TikZ source of the diagram and its compiled SVG; the link-preview image and its source
web/vendor/          KaTeX and the Latin Modern fonts (third-party; see web/vendor/README.md)
.github/workflows/   checks for pull requests (verify.yml) and site deployment (pages.yml)
site/                built site (generated, not committed: GitHub builds it)
scripts/             scoring, site build, checks and preview, figure build, baselines, reference optimizer
scripts/reexamine/   checks behind disputed claims (numpy + scipy)
scripts/ports/       controllers from papers turned into submission files
notes/               one note per disputed claim
```

## Licence

MIT, see `LICENSE`.
