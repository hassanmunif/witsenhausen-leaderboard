#!/usr/bin/env python3
"""Re-examination of Tseng & Tang (CDC 2017), check 1: what a five-sigma cutoff leaves out of the cost.

Tseng's open-source solver (UCP-Solver, single_threaded/sources/witsenhausen.cpp, get_J_value) sums the
cost over x0 in [-5 sigma, 5 sigma] and samples the noise on the same grid scaled by 1/sigma, so only
over w in [-5, 5]. The probability outside is dropped, not renormalised. This script scores the verified
reference controllers exactly with the reference evaluator and subtracts the three pieces the cutoff
leaves out:

    T1 = k^2 E[(f(X0) - X0)^2 ; |X0| > 5 sigma]
    T2 = E[(X1 - g(Y))^2 ; |X0| > 5 sigma]
    T3 = E[(X1 - g(Y))^2 ; |X0| <= 5 sigma, |W| > 5]

where g(y) = E[X1 | Y = y] is the exact optimal second controller. The result is compared with Table II
of the paper. Where Table II is essentially linear (k >= 0.75), the best linear controller is used.

    python scripts/reexamine/tseng_tang_tails.py      (about 30 seconds)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.interpolate import CubicSpline
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from witsenhausen import evaluate, posterior_mean  # noqa: E402
from witsenhausen.controllers import controller_from_spec, linear  # noqa: E402

SIGMA = 5.0
X_CUT, W_CUT = 5.0 * SIGMA, 5.0
# Table II of Tseng & Tang (CDC 2017): costs at sigma = 5 for several k.
TABLE_II = {0.1: 0.052292, 0.2: 0.166897, 0.3: 0.314824, 0.4: 0.477652, 0.5: 0.640974,
            0.75: 0.961424, 1.0: 0.961467, 8.0: 0.961522}
GX, GW = leggauss(16)


def pdf(z, s=1.0):
    return np.exp(-0.5 * (z / s) ** 2) / (np.sqrt(2.0 * np.pi) * s)


def nodes(lo, hi, width, breaks=()):
    """Composite 16-point Gauss-Legendre rule on [lo, hi], with panel edges at the given breakpoints."""
    edges = sorted({lo, hi, *(float(b) for b in breaks if lo < b < hi)})
    xs, ws = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        e = np.linspace(a, b, max(1, int(np.ceil((b - a) / width))) + 1)
        c, d = e[:-1, None], e[1:, None]
        xs.append((0.5 * (d - c) * GX + 0.5 * (d + c)).ravel())
        ws.append((0.5 * (d - c) * GW).ravel())
    return np.concatenate(xs), np.concatenate(ws)


def optimal_second_controller(f):
    """g(y) = E[X1 | Y = y] on a fine grid as a cubic spline, checked against the exact values."""
    fx = f(np.linspace(-60.0, 60.0, 2001))
    y = np.arange(fx.min() - 15.0, fx.max() + 15.0, 0.002)
    g = CubicSpline(y, posterior_mean(f, SIGMA, y))
    yt = np.random.default_rng(0).uniform(-35.0, 35.0, 2000)
    assert np.max(np.abs(g(yt) - posterior_mean(f, SIGMA, yt))) < 1e-8
    return g


def second_stage(f, g, xq, xw, wq, ww, chunk=400):
    """Sum over the x and w nodes of p(x) p(w) (f(x) - g(f(x) + w))^2."""
    px, pw, x1, total = pdf(xq, SIGMA) * xw, pdf(wq) * ww, f(xq), 0.0
    for i in range(0, len(xq), chunk):
        a = x1[i:i + chunk, None]
        total += np.sum(px[i:i + chunk, None] * pw[None, :] * (a - g(a + wq[None, :])) ** 2)
    return total


def left_out(f, k):
    """T1 + T2 + T3: the part of the exact cost outside |x0| <= 5 sigma, |w| <= 5."""
    g, bps = optimal_second_controller(f), np.asarray(f.breakpoints, dtype=float)
    t1 = t2 = 0.0
    wq, ww = nodes(-14.0, 14.0, 0.05)
    for lo, hi in [(-60.0, -X_CUT), (X_CUT, 60.0)]:
        xq, xw = nodes(lo, hi, 0.25, bps)
        t1 += k * k * np.sum(pdf(xq, SIGMA) * xw * (f(xq) - xq) ** 2)
        t2 += second_stage(f, g, xq, xw, wq, ww)
    xq, xw = nodes(-X_CUT, X_CUT, 0.1, bps)
    t3 = sum(second_stage(f, g, xq, xw, *nodes(lo, hi, 0.05)) for lo, hi in [(-14.0, -W_CUT), (W_CUT, 14.0)])
    return t1 + t2 + t3


def best_linear(k):
    def cost(lam):
        return k * k * SIGMA ** 2 * (1.0 - lam) ** 2 + lam * lam * SIGMA ** 2 / (1.0 + lam * lam * SIGMA ** 2)
    return linear(minimize_scalar(cost, bounds=(0.5, 1.2), method="bounded", options={"xatol": 1e-13}).x)


def main():
    rows = []
    for k in (0.1, 0.2, 0.3, 0.4, 0.5):
        sub = json.loads((ROOT / f"submissions/k{k:.2f}_s5/reference-curved-steps.json").read_text(encoding="utf-8"))
        rows.append((k, "verified reference", controller_from_spec(sub["controller"])))
    for k in (0.75, 1.0, 8.0):
        rows.append((k, "best linear", best_linear(k)))
    print(f"{'k':>5}  {'controller':<19} {'exact cost':>11} {'left out':>9} {'with cutoff':>12} {'Table II':>9} {'Table II - cutoff':>18}")
    for k, label, f in rows:
        exact = evaluate(f, k, SIGMA).cost
        cut = exact - left_out(f, k)
        print(f"{k:>5}  {label:<19} {exact:>11.7f} {exact - cut:>9.2e} {cut:>12.7f} {TABLE_II[k]:>9.6f} {TABLE_II[k] - cut:>+18.1e}", flush=True)


if __name__ == "__main__":
    main()
