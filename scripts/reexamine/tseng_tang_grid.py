#!/usr/bin/env python3
"""Re-examination of Tseng & Tang (CDC 2017), check 2: their discrete cost on their grid.

A numpy re-implementation of Witsenhausen::get_J_value in Tseng's open-source UCP-Solver
(single_threaded/sources/witsenhausen.cpp, commit ca1e1fc), on the grid stated in the CDC 2017 paper:

* x0 on 16,000 evenly spaced points of [-25, 25], each weighted as in the solver by
  (pdf(x - h/2) + pdf(x + h/2)) / 2 * h;
* the noise on the same points scaled by sigma_w / sigma_x, so only on [-5, 5], weighted the same way.
  Nothing is renormalised, so the probability beyond five standard deviations is missing;
* the second controller on 16,000 points of [-30, 30], interpolated linearly and held constant outside.
  Its values minimise the solver's own per-point cost (compute_C_value, stage 1): they are the
  conditional mean of x1 given y in this discrete model.

The verified reference controllers are scored this way and compared with Table II of the paper.

    python scripts/reexamine/tseng_tang_grid.py      (about 40 seconds)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from witsenhausen import evaluate  # noqa: E402
from witsenhausen.controllers import controller_from_spec  # noqa: E402

SIGMA_X, SIGMA_W, N = 5.0, 1.0, 16_000
# Table II of Tseng & Tang (CDC 2017): costs at sigma = 5.
TABLE_II = {0.1: 0.052292, 0.2: 0.166897, 0.3: 0.314824, 0.4: 0.477652, 0.5: 0.640974}


def pdf(x, s):
    return np.exp(-0.5 * (x / s) ** 2) / (np.sqrt(2.0 * np.pi) * s)


def grid_cost(f, k, n=N, chunk=500):
    """Return the solver's cost of f, and the total probability of the x0 and noise grids."""
    x = np.linspace(-25.0, 25.0, n)
    h = x[1] - x[0]
    px = (pdf(x - h / 2, SIGMA_X) + pdf(x + h / 2, SIGMA_X)) / 2 * h
    r = SIGMA_W / SIGMA_X
    w, hw = x * r, h * r
    w_density = (pdf(w - hw / 2, SIGMA_W) + pdf(w + hw / 2, SIGMA_W)) / 2
    pw = w_density * hw

    def w_prob(v):  # get_w_prob_value: linear interpolation, zero outside [-5, 5]
        return np.where(np.abs(v) <= w[-1], np.interp(v, w, w_density), 0.0)

    x1 = f(x)
    y = np.linspace(-30.0, 30.0, n)
    u = np.empty(n)
    for s in range(0, n, chunk):
        wt = px[None, :] * w_prob(y[s:s + chunk, None] - x1[None, :])
        den = wt.sum(axis=1)
        u[s:s + chunk] = np.where(den > 0, (wt * x1[None, :]).sum(axis=1) / np.where(den > 0, den, 1.0), y[s:s + chunk])
    stage1 = k * k * np.sum((x1 - x) ** 2 * px)
    stage2 = 0.0
    for s in range(0, n, chunk):
        a = x1[s:s + chunk, None]
        stage2 += np.sum(px[s:s + chunk, None] * pw[None, :] * (a - np.interp(a + w[None, :], y, u)) ** 2)
    return stage1 + stage2, px.sum(), pw.sum()


def main():
    print(f"{'k':>4}  {'exact cost':>11} {'on their grid':>14} {'Table II':>9} {'Table II - grid':>16}")
    for k, printed in TABLE_II.items():
        sub = json.loads((ROOT / f"submissions/k{k:.2f}_s5/reference-curved-steps.json").read_text(encoding="utf-8"))
        f = controller_from_spec(sub["controller"])
        cost, mass_x, mass_w = grid_cost(f, k)
        print(f"{k:>4}  {evaluate(f, k, SIGMA_X).cost:>11.7f} {cost:>14.7f} {printed:>9.6f} {printed - cost:>+16.1e}", flush=True)
    print(f"total probability on the grid: x0 {mass_x:.9f}, noise {mass_w:.9f}")


if __name__ == "__main__":
    main()
