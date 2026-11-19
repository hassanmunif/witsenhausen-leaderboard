#!/usr/bin/env python3
"""Reference optimizer: odd "sloped-step" controllers with curved steps.

The first controller is parametrized on x >= 0 as N steps; step j covers
[p_j, p_{j+1}) and is itself a continuous piecewise-linear curve with M
sub-pieces, so steps can bend.  Steps may jump at the p_j; f is extended as
an odd function.  The same closed-form cost as the reference evaluator is
written in JAX and minimized with L-BFGS using exact gradients.

Every result is re-scored with the numpy reference evaluator before it is
written, and only that score is used anywhere on the leaderboard.

Needs:  pip install "jax[cpu]"
Usage:  python scripts/optimize_reference.py --k 0.2 --sigma 5 --out submissions/k0.20_s5/reference.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

import jax
import jax.numpy as jnp
from jax.scipy.special import log_ndtr, logsumexp, ndtr

jax.config.update("jax_enable_x64", True)

from scipy.optimize import minimize  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from witsenhausen import SCHEMA, evaluate, odd_piecewise_affine  # noqa: E402

LOG_SQRT_2PI = 0.5 * math.log(2.0 * math.pi)


def log_phi(z):
    return -0.5 * z * z - LOG_SQRT_2PI


def trunc(lo, hi):
    """log P, mean, var of N(0,1) truncated to (lo, hi); finite inputs."""
    lower = hi <= 0.0
    upper = lo >= 0.0
    mid = ~(lower | upper)
    l1 = jnp.where(lower, lo, -2.0)
    h1 = jnp.where(lower, hi, -1.0)
    a1, b1 = log_ndtr(l1), log_ndtr(h1)
    lp_lower = b1 + jnp.log(-jnp.expm1(a1 - b1))
    l2 = jnp.where(upper, lo, 1.0)
    h2 = jnp.where(upper, hi, 2.0)
    a2, b2 = log_ndtr(-h2), log_ndtr(-l2)
    lp_upper = b2 + jnp.log(-jnp.expm1(a2 - b2))
    l3 = jnp.where(mid, lo, -1.0)
    h3 = jnp.where(mid, hi, 1.0)
    lp_mid = jnp.log1p(-(ndtr(l3) + ndtr(-h3)))
    lp = jnp.where(lower, lp_lower, jnp.where(upper, lp_upper, lp_mid))
    el = jnp.exp(log_phi(lo) - lp)
    eh = jnp.exp(log_phi(hi) - lp)
    mean = el - eh
    var = 1.0 + lo * el - hi * eh - mean * mean
    return lp, mean, var


class Model:
    def __init__(self, k, sigma, n_steps, n_sub, y_max=None, panel=0.2, order=16):
        self.k, self.sigma, self.N, self.M = float(k), float(sigma), int(n_steps), int(n_sub)
        self.E = 200.0 * self.sigma  # stands in for +inf (P(|X0| > 200 sigma) = 0)
        y_max = y_max or (12.0 * self.sigma + 14.0)
        n_pan = int(math.ceil(y_max / panel))
        edges = np.linspace(0.0, y_max, n_pan + 1)
        gx, gw = np.polynomial.legendre.leggauss(order)
        half = 0.5 * np.diff(edges)[:, None]
        midp = 0.5 * (edges[:-1] + edges[1:])[:, None]
        self.y = jnp.asarray((midp + half * gx[None, :]).ravel())
        self.wy = jnp.asarray((half * gw[None, :]).ravel())
        self.n_params = self.N + self.N * (self.M + 1) - 1 + 2
        self._vg = jax.jit(jax.value_and_grad(self.cost))

    # -- parameters <-> pieces -------------------------------------------
    def unpack(self, theta):
        N, M = self.N, self.M
        gaps = jax.nn.softplus(theta[:N]) + 1e-3
        p = jnp.cumsum(gaps)
        vals = jnp.concatenate([jnp.zeros(1), theta[N:N + N * (M + 1) - 1]]).reshape(N, M + 1)
        last_level, last_slope = theta[-2], theta[-1]
        return p, vals, last_level, last_slope

    def pieces(self, theta):
        p, vals, last_level, last_slope = self.unpack(theta)
        edges0 = jnp.concatenate([jnp.zeros(1), p])
        t = jnp.linspace(0.0, 1.0, self.M + 1)
        sub = edges0[:-1, None] + (edges0[1:] - edges0[:-1])[:, None] * t[None, :]
        xl, xr = sub[:, :-1].ravel(), sub[:, 1:].ravel()
        vl, vr = vals[:, :-1].ravel(), vals[:, 1:].ravel()
        slope = (vr - vl) / (xr - xl)
        icpt = vl - slope * xl
        xl = jnp.append(xl, p[-1])
        xr = jnp.append(xr, self.E)
        icpt = jnp.append(icpt, last_level - last_slope * p[-1])
        slope = jnp.append(slope, last_slope)
        lo = jnp.concatenate([-xr[::-1], xl])
        hi = jnp.concatenate([-xl[::-1], xr])
        a = jnp.concatenate([-icpt[::-1], icpt])
        b = jnp.concatenate([slope[::-1], slope])
        return lo, hi, a, b

    def cost(self, theta):
        k, sigma = self.k, self.sigma
        lo, hi, a, b = self.pieces(theta)
        lp, zm, zv = trunc(lo / sigma, hi / sigma)
        pr = jnp.exp(lp)
        m, v = sigma * zm, sigma * sigma * zv
        ex1sq = jnp.sum(pr * ((a + b * m) ** 2 + b * b * v))
        c = b - 1.0
        power = jnp.sum(pr * ((a + c * m) ** 2 + c * c * v))
        z = self.y[None, :] - a[:, None]
        vv = (1.0 + (b * sigma) ** 2)[:, None]
        s = sigma / jnp.sqrt(vv)
        mu = (b[:, None] * sigma * sigma / vv) * z
        lp2, tm, _ = trunc((lo[:, None] - mu) / s, (hi[:, None] - mu) / s)
        logw = -0.5 * z * z / vv - 0.5 * jnp.log(vv) - LOG_SQRT_2PI + lp2
        means = a[:, None] + b[:, None] * (mu + s * tm)
        L = logsumexp(logw, axis=0)
        g = jnp.sum(jnp.exp(logw - L[None, :]) * means, axis=0)
        eg2 = 2.0 * jnp.sum(self.wy * jnp.exp(L) * g * g)
        return k * k * power + ex1sq - eg2

    # -- init / export -----------------------------------------------------
    def init_theta(self, spacing=6.6, first_break=None, slope=0.03, centre_slope=0.02):
        N, M = self.N, self.M
        first_break = first_break or spacing / 2.0
        p = np.array([first_break + j * spacing for j in range(N)])
        gaps = np.diff(np.concatenate(([0.0], p)))
        raw = np.log(np.expm1(gaps - 1e-3))
        edges0 = np.concatenate(([0.0], p))
        vals = np.zeros((N, M + 1))
        for j in range(N):
            xs = np.linspace(edges0[j], edges0[j + 1], M + 1)
            if j == 0:
                vals[j] = centre_slope * xs
            else:
                level = j * spacing
                centre = 0.5 * (edges0[j] + edges0[j + 1])
                vals[j] = level + slope * (xs - centre)
        last_level = N * spacing - slope * spacing / 2.0
        return np.concatenate((raw, vals.ravel()[1:], [last_level, slope]))

    def from_controller(self, f_pos):
        """Initial theta from an odd controller given as a callable on x >= 0
        with known step edges ``f_pos.edges`` (used for warm starts)."""
        raise NotImplementedError

    def to_odd_spec(self, theta):
        p, vals, last_level, last_slope = (np.asarray(x) for x in self.unpack(jnp.asarray(theta)))
        edges0 = np.concatenate(([0.0], p))
        bps, icpts, slopes = [], [], []
        for j in range(self.N):
            xs = np.linspace(edges0[j], edges0[j + 1], self.M + 1)
            for i in range(self.M):
                sl = (vals[j, i + 1] - vals[j, i]) / (xs[i + 1] - xs[i])
                icpts.append(vals[j, i] - sl * xs[i])
                slopes.append(sl)
                bps.append(xs[i + 1])
        icpts.append(float(last_level - last_slope * p[-1]))
        slopes.append(float(last_slope))
        icpts[0] = 0.0  # centre piece passes through the origin exactly
        return {
            "type": "odd_piecewise_affine",
            "breakpoints": [float(x) for x in bps],
            "intercepts": [float(x) for x in icpts],
            "slopes": [float(x) for x in slopes],
        }


def optimize(model: Model, theta0, maxiter=4000, verbose=True):
    t0 = time.time()
    hist = []

    def fun(th):
        v, g = model._vg(jnp.asarray(th))
        hist.append(float(v))
        return float(v), np.asarray(g, dtype=float)

    res = minimize(fun, np.asarray(theta0, float), jac=True, method="L-BFGS-B",
                   options={"maxiter": maxiter, "maxfun": maxiter * 2, "ftol": 1e-16, "gtol": 1e-12, "maxcor": 50})
    if verbose:
        print(f"  L-BFGS: {res.nit} it, J={res.fun:.12f} ({time.time() - t0:.1f}s) {res.message}")
    return res.x, float(res.fun)


PROVENANCE = "Computed with this site's reference optimizer, scripts/optimize_reference.py; not a published result."
# Declared in every file this script writes; the leaderboard tags such entries AI-assisted.
AI_ASSISTANCE = "Claude Opus 5.5 (Anthropic) suggested the curved steps and wrote the optimizer."


def write_submission(path, spec, k, sigma, result, n_steps, n_sub, notes=""):
    sub = {
        "schema": SCHEMA,
        "name": f"Curved sloped steps ({n_steps} steps per side, {n_sub} sub-pieces each)",
        "short_name": "reference optimizer",
        "authors": ["H. Munif"],
        "date": date.today().isoformat(),
        "setting": {"k": k, "sigma": sigma},
        "method": "L-BFGS with exact gradients (JAX) over odd piecewise-linear steps, several restarts",
        "ai_assistance": AI_ASSISTANCE,
        "source": {"kind": "code", "url": "scripts/optimize_reference.py"},
        "claimed_cost": round(result.cost, 12),
        "notes": (notes + " " if notes else "") + PROVENANCE,
        "controller": spec,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(sub, indent=1) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=float, required=True)
    ap.add_argument("--sigma", type=float, required=True)
    ap.add_argument("--steps", type=int, default=6)
    ap.add_argument("--sub", type=int, default=8)
    ap.add_argument("--spacing", type=float, default=6.6)
    ap.add_argument("--maxiter", type=int, default=4000)
    ap.add_argument("--init", type=str, default=None, help="warm start from a theta .npy file")
    ap.add_argument("--save-theta", type=str, default=None)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args(argv)

    model = Model(args.k, args.sigma, args.steps, args.sub)
    theta = np.load(args.init) if args.init else model.init_theta(spacing=args.spacing)
    print(f"k={args.k} sigma={args.sigma}: {model.n_params} parameters, start J={float(model.cost(jnp.asarray(theta))):.9f}")
    theta, J = optimize(model, theta, maxiter=args.maxiter)
    spec = model.to_odd_spec(theta)
    f = odd_piecewise_affine(spec["breakpoints"], spec["intercepts"], spec["slopes"])
    r = evaluate(f, args.k, args.sigma)
    print(f"  reference evaluator: J={r.cost:.12f} ± {r.error_estimate:.1e} (JAX {J:.12f})")
    if args.save_theta:
        np.save(args.save_theta, theta)
    if args.out:
        write_submission(args.out, spec, args.k, args.sigma, r, args.steps, args.sub)
        print(f"  wrote {args.out}")


if __name__ == "__main__":
    main()
