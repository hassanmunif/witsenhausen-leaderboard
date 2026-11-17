"""Correctness tests for the reference evaluator.

Each test compares the evaluator with an independent computation that does
not share its closed-form piece integrals or its y-quadrature.
"""

import math
import sys
from pathlib import Path

import numpy as np
import pytest
from numpy.polynomial.legendre import leggauss
from scipy import integrate
from scipy.special import expit, ndtr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from witsenhausen import (  # noqa: E402
    PiecewiseAffine,
    evaluate,
    from_points,
    linear,
    odd_piecewise_affine,
    posterior_mean,
    two_point,
)

TOL = 1e-10


def phi(z):
    return np.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)


# ---------------------------------------------------------------- closed forms
@pytest.mark.parametrize("k,sigma", [(0.2, 5.0), (1.0, 1.0), (0.05, 10.0), (0.5, 2.0)])
@pytest.mark.parametrize("lam", [0.0, 0.04, 0.3, 0.9583, 1.0, 1.7, -0.5])
def test_linear_closed_form(k, sigma, lam):
    exact = k * k * sigma * sigma * (lam - 1) ** 2 + lam * lam * sigma * sigma / (1 + lam * lam * sigma * sigma)
    r = evaluate(linear(lam), k, sigma)
    assert abs(r.cost - exact) < TOL
    assert r.error_estimate < 1e-9


def bpsk_mmse(a):
    """MMSE of X = +-a (equiprobable) from X + N(0,1), by 1-D quadrature."""
    val, _ = integrate.quad(lambda w: phi(w) * 2.0 * expit(-2.0 * a * (a + w)),
                            -40, 40, points=[-a], limit=400, epsabs=1e-15, epsrel=1e-13)
    return a * a * val


@pytest.mark.parametrize("k,sigma", [(0.2, 5.0), (0.3, 3.0), (1.0, 1.0)])
def test_witsenhausen_two_point(k, sigma):
    a = sigma
    stage1 = k * k * (a * a - 2 * a * sigma * math.sqrt(2 / math.pi) + sigma * sigma)
    exact = stage1 + bpsk_mmse(a)
    r = evaluate(two_point(a), k, sigma)
    assert abs(r.cost - exact) < TOL


def test_benchmark_published_values():
    # Witsenhausen's design at the benchmark is quoted as 0.404253 (Mehmetoglu
    # et al.) and 0.40425320 (Tseng & Tang); the best linear cost as 0.96.
    r = evaluate(two_point(5.0), 0.2, 5.0)
    assert round(r.cost, 6) == 0.404253
    best_lin = min(evaluate(linear(l), 0.2, 5.0).cost for l in np.linspace(0.9, 1.0, 201))
    assert abs(best_lin - 0.96) < 1e-6


# ------------------------------------------------------ flat steps (mixtures)
def mixture_cost(levels, probs, power, k):
    levels = np.asarray(levels)
    probs = np.asarray(probs)

    def py(y):
        return np.sum(probs * phi(y - levels))

    def num(y):
        return np.sum(probs * levels * phi(y - levels))

    lo, hi = levels.min() - 15, levels.max() + 15
    pts = list(np.linspace(lo, hi, 60))
    eg2, _ = integrate.quad(lambda y: num(y) ** 2 / py(y), lo, hi, points=pts[1:-1],
                            limit=2000, epsabs=1e-15, epsrel=1e-14)
    ex2 = float(np.sum(probs * levels ** 2))
    return k * k * power + ex2 - eg2


def test_flat_three_level_step():
    k, sigma, t, c = 0.2, 5.0, 3.1, 6.4
    f = PiecewiseAffine([-t, t], [-c, 0.0, c], [0.0, 0.0, 0.0])
    pout = ndtr(-t / sigma)
    probs = [pout, 1 - 2 * pout, pout]
    # E[(f(X)-X)^2] by 1-D quadrature
    power, _ = integrate.quad(lambda x: (f(np.array([x]))[0] - x) ** 2 * phi(x / sigma) / sigma,
                              -80, 80, points=[-t, t], limit=400, epsabs=1e-15, epsrel=1e-14)
    exact = mixture_cost([-c, 0.0, c], probs, power, k)
    r = evaluate(f, k, sigma)
    assert abs(r.cost - exact) < TOL


# ------------------------------------------------- sloped pieces, brute force
def brute_force_cost(f, k, sigma, x_nodes_per_piece=400, y_step=0.02):
    """Brute-force J(f): Gauss-Legendre in x on each (truncated) piece,
    trapezoid-free Gauss-Legendre panels in y.  Independent of the
    evaluator's closed-form piece integrals."""
    X = 12 * sigma
    lo, hi = f.edges()
    gx, gw = leggauss(x_nodes_per_piece)
    xs, ws = [], []
    for l, h in zip(lo, hi):
        l, h = max(l, -X), min(h, X)
        if h <= l:
            continue
        xs.append(0.5 * (h - l) * gx + 0.5 * (h + l))
        ws.append(0.5 * (h - l) * gw)
    xs = np.concatenate(xs)
    ws = np.concatenate(ws) * phi(xs / sigma) / sigma
    fx = f(xs)
    power = np.sum(ws * (fx - xs) ** 2)
    ex2 = np.sum(ws * fx ** 2)
    ylo, yhi = fx.min() - 14, fx.max() + 14
    n = int(math.ceil((yhi - ylo) / 0.25))
    edges = np.linspace(ylo, yhi, n + 1)
    gy, gyw = leggauss(24)
    eg2 = 0.0
    for a, b in zip(edges[:-1], edges[1:]):
        ys = 0.5 * (b - a) * gy + 0.5 * (a + b)
        lik = phi(ys[:, None] - fx[None, :])
        den = lik @ ws
        num = lik @ (ws * fx)
        eg2 += np.sum(0.5 * (b - a) * gyw * num * num / den)
    return k * k * power + ex2 - eg2


def test_sloped_steps_against_brute_force():
    k, sigma = 0.2, 5.0
    f = odd_piecewise_affine(
        breakpoints=[3.2, 9.6, 16.1],
        intercepts=[0.0, 6.5 - 0.03 * 6.4, 13.1 - 0.02 * 12.85, 19.8 - 0.01 * 16.1],
        slopes=[0.05, 0.03, 0.02, 0.01],
    )
    r = evaluate(f, k, sigma)
    bf = brute_force_cost(f, k, sigma)
    assert abs(r.cost - bf) < 5e-10


def test_general_piecewise_against_brute_force():
    k, sigma = 0.35, 3.0
    f = PiecewiseAffine([-4.0, -1.0, 0.5, 2.0, 6.0],
                        [-3.0, 1.0, 0.2, -0.4, 5.0, 2.0],
                        [0.4, 2.0, 0.0, 1.3, -0.2, 1.0])
    r = evaluate(f, k, sigma)
    bf = brute_force_cost(f, k, sigma)
    assert abs(r.cost - bf) < 5e-10


# ----------------------------------------------------------------- invariance
def test_redundant_breakpoints_do_not_change_cost():
    k, sigma = 0.2, 5.0
    f = odd_piecewise_affine([3.2, 9.6, 16.1], [0.0, 6.3, 12.8, 19.6], [0.05, 0.03, 0.02, 0.01])
    fine = f.with_breakpoints(np.linspace(-30, 30, 20001))  # widths 3e-3 -> narrow series path
    r1 = evaluate(f, k, sigma)
    r2 = evaluate(fine, k, sigma)
    assert fine.n_pieces > 20000
    assert abs(r1.cost - r2.cost) < 2e-10


def test_odd_and_points_constructors_agree():
    f = odd_piecewise_affine([2.0, 7.0], [0.0, 5.0, 9.0], [0.1, 0.05, 0.0])
    g = from_points([0, 2, 7, 30], [0, 5.1, 9.0, 9.0], odd=True, extrapolation="constant")
    for x in [0.5, 1.5]:
        assert abs(f(np.array([x]))[0] - 0.1 * x) < 1e-15
        assert abs(f(np.array([-x]))[0] + 0.1 * x) < 1e-15
    assert g(np.array([-1.0]))[0] == pytest.approx(-5.1 / 2)
    assert g(np.array([100.0]))[0] == pytest.approx(9.0)


def test_posterior_mean_is_odd_for_odd_controller():
    f = odd_piecewise_affine([3.0, 9.0], [0.0, 6.4, 13.0], [0.04, 0.02, 0.01])
    y = np.linspace(-20, 20, 81)
    g = posterior_mean(f, 5.0, y)
    assert np.max(np.abs(g + g[::-1])) < 1e-12
