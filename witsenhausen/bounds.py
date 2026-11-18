"""Provable lower bounds on the optimal cost of Witsenhausen's counterexample.

Every bound here holds for *all* controller pairs (f, g), linear or not, in
the scalar problem  X0 ~ N(0, sigma^2), W ~ N(0, 1),
J = k^2 E[(X1 - X0)^2] + E[(X1 - g(X1 + W))^2].

grover_sahai(k, sigma)
    Grover & Sahai (2010); Theorem 2 of Grover, Park & Sahai, "The
    finite-dimensional Witsenhausen counterexample" (arXiv:1003.0514):

        J* >= inf_{P >= 0}  k^2 P + ((sqrt(kappa(P)) - sqrt(P))^+)^2,
        kappa(P) = sigma^2 / ((sigma + sqrt(P))^2 + 1).

grover_park_sahai(k, sigma)
    Theorem 3 of the same paper (sphere-packing bound), vector length m = 1.
    For any sigma_G >= 1 and L > 0 (chosen per P):

        J* >= inf_{P >= 0}  k^2 P + eta(P, sigma_G, L),
        eta = sigma_G / c(L) * exp(-L^2 (sigma_G^2 - 1) / 2)
              * ((sqrt(kappa2) - sqrt(P))^+)^2,
        kappa2 = sigma^2 sigma_G^2 /
                 (c(L)^2 e^{1 - d(L)} ((sigma + sqrt(P))^2 + d(L) sigma_G^2)),
        c(L) = 1 / P(chi2_1 <= L^2),  d(L) = P(chi2_3 <= L^2) / P(chi2_1 <= L^2).

genie_two_point(k, sigma)
    Witsenhausen's own lower bound: Theorem 3 of Witsenhausen, "A counterexample
    in stochastic optimum control" (SIAM J. Control, 1968). Wu & Verdu (CDC-ECC
    2011, Theorem 4) generalise it; the coupling Y' = -Y recovers it.  The
    argument: a genie tells the second controller xi = |X0|.  Given xi, X1 takes the
    two values f(xi), f(-xi) with probability 1/2 each, so the second stage
    costs at least h(a) with a = (f(xi) - f(-xi))/2, where h(a) is the MMSE
    of an equiprobable +-a signal in unit Gaussian noise.  Since
    ((f(xi)-xi)^2 + (f(-xi)+xi)^2)/2 >= (a - xi)^2,

        J* >= E[V(|X0|)],   V(xi) = min_a  k^2 (a - xi)^2 + h(a),
        h(a) = a^2 E[1 - tanh(a (a + W))]
             = sqrt(2 pi) a^2 phi(a) * int phi(y) / cosh(a y) dy   (Witsenhausen's form).

grover_wagner_sahai(k, sigma)
    Corollary 1 of Grover, Wagner & Sahai, "Information embedding and the
    triple role of control" (IEEE Trans. Inf. Theory 61(4), 2015;
    arXiv:1306.5018).  The corollary holds for every vector length m, so
    also for m = 1.  It bounds the estimation error at control power P by an
    infimum over the correlation c = E[X0 U1] of a supremum over gamma.
    Fixing gamma in (0, 1) and relaxing the constraints of the infimum (on c,
    on P >= 0 and on E[X1^2] >= 0) gives a closed form:

        J* >= k^2 [ 2 sigma sqrt((1-gamma) / (gamma (1 + k^2 gamma)))
                    - (1-gamma) (sigma^2 + gamma) / gamma ].

    Every gamma in (0, 1) gives a valid bound, so the search over gamma only
    chooses which valid bound to report; no step of it can overstate the
    bound.  At sigma = 5 the relaxations cost nothing (tests/test_bounds.py).

Numerics: the outer infimum over P (or the inner minimum over a) is taken
on a fine grid and refined locally; the inner suprema (sigma_G, L) only need
to be feasible, not optimal, for the bound to stay valid.  Reported values
are rounded *down* (see ``round_down``) so that small numerical errors cannot
make a bound look stronger than it is.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.optimize import minimize, minimize_scalar
from scipy.special import expit
from scipy.stats import chi2

__all__ = ["grover_sahai", "grover_park_sahai", "genie_two_point", "grover_wagner_sahai", "all_bounds", "round_down"]


def round_down(x: float, digits: int = 5) -> float:
    """Round a positive number down to ``digits`` significant digits."""
    if x <= 0:
        return 0.0
    e = math.floor(math.log10(x)) - digits + 1
    q = 10.0 ** e
    return math.floor(x / q) * q


# ----------------------------------------------------------- Grover-Sahai
def _gs_term(s, sigma):
    kappa = sigma * sigma / ((sigma + s) ** 2 + 1.0)
    return np.maximum(np.sqrt(kappa) - s, 0.0) ** 2


def grover_sahai(k: float, sigma: float) -> dict:
    s_max = sigma / math.sqrt(sigma * sigma + 1.0)  # for s >= s_max the 2nd term is 0
    s = np.linspace(0.0, s_max, 200_001)
    F = k * k * s * s + _gs_term(s, sigma)
    i = int(np.argmin(F))
    lo, hi = s[max(i - 1, 0)], s[min(i + 1, s.size - 1)]
    res = minimize_scalar(lambda t: k * k * t * t + float(_gs_term(t, sigma)),
                          bounds=(lo, hi), method="bounded", options={"xatol": 1e-13})
    val = min(float(F[i]), float(res.fun))
    P = float(res.x) ** 2 if res.fun <= F[i] else float(s[i]) ** 2
    return {"name": "grover_sahai", "value": val, "argmin_power": P}


# ------------------------------------------------- Grover-Park-Sahai (m = 1)
def _gps_eta(s, sG, L, sigma):
    """eta for arrays broadcast together (s = sqrt(P))."""
    p1 = chi2.cdf(L * L, 1)
    p3 = chi2.cdf(L * L, 3)
    c = 1.0 / p1
    d = p3 / p1
    kappa2 = sigma * sigma * sG * sG / (c * c * np.exp(1.0 - d) * ((sigma + s) ** 2 + d * sG * sG))
    return (sG / c) * np.exp(-L * L * (sG * sG - 1.0) / 2.0) * np.maximum(np.sqrt(kappa2) - s, 0.0) ** 2


def _gps_best_eta(s, sigma, polish=False):
    """max over a (sigma_G, L) grid of eta(s); optionally polished locally."""
    sG = np.concatenate(([1.0], np.geomspace(1.0005, 6.0, 59)))
    L = np.geomspace(0.05, 12.0, 80)
    S, G, LL = np.meshgrid(np.atleast_1d(s), sG, L, indexing="ij")
    eta = _gps_eta(S, G, LL, sigma)
    flat = eta.reshape(eta.shape[0], -1)
    j = np.argmax(flat, axis=1)
    best = flat[np.arange(flat.shape[0]), j]
    if not polish:
        return best
    out = best.copy()
    Gf, Lf = G.reshape(G.shape[0], -1), LL.reshape(LL.shape[0], -1)
    for r, si in enumerate(np.atleast_1d(s)):
        x0 = np.array([math.log(Gf[r, j[r]]), math.log(Lf[r, j[r]])])

        def neg(z, si=si):
            g = max(1.0, math.exp(z[0]))
            return -float(_gps_eta(si, g, math.exp(z[1]), sigma))

        res = minimize(neg, x0, method="Nelder-Mead", options={"xatol": 1e-10, "fatol": 1e-15, "maxiter": 4000})
        out[r] = max(out[r], -res.fun)
    return out


def grover_park_sahai(k: float, sigma: float) -> dict:
    eta0 = float(_gps_best_eta(0.0, sigma, polish=True)[0])
    s_cap = min(sigma, math.sqrt(max(eta0, 1e-300)) / k) if k > 0 else sigma
    s = np.linspace(0.0, s_cap, 2001)
    F = k * k * s * s + _gps_best_eta(s, sigma)
    i = int(np.argmin(F))
    # refine the outer infimum on a fine local grid with polished inner sups
    lo, hi = s[max(i - 2, 0)], s[min(i + 2, s.size - 1)]
    sf = np.linspace(lo, hi, 81)
    Ff = k * k * sf * sf + _gps_best_eta(sf, sigma, polish=True)
    j = int(np.argmin(Ff))
    val = min(float(F[i]), float(Ff[j]))
    return {"name": "grover_park_sahai", "value": val, "argmin_power": float(sf[j]) ** 2}


# ------------------------------------------------------ genie two-point
def _bpsk_mmse(a: np.ndarray) -> np.ndarray:
    """h(a) = a^2 E[1 - tanh(a (a + W))] = a^2 E[2 expit(-2a(a + W))]."""
    a = np.asarray(a, dtype=float)
    edges = np.linspace(-13.0, 13.0, 1041)  # panels of width 0.025
    x, w = leggauss(12)
    half = 0.5 * np.diff(edges)[:, None]
    mid = 0.5 * (edges[:-1] + edges[1:])[:, None]
    wn = (mid + half * x[None, :]).ravel()
    ww = (half * w[None, :]).ravel() * np.exp(-0.5 * wn * wn) / math.sqrt(2.0 * math.pi)
    out = np.empty(a.size)
    for start in range(0, a.size, 256):
        aa = a[start:start + 256, None]
        out[start:start + 256] = (aa[:, 0] ** 2) * (2.0 * expit(-2.0 * aa * (aa + wn[None, :])) @ ww)
    return out


def genie_two_point(k: float, sigma: float) -> dict:
    xi_max = 12.0 * sigma
    da = 1e-3
    a = np.arange(0.0, xi_max + 8.0 + da, da)
    h = _bpsk_mmse(a)
    # curvature bound for the grid-minimisation safety margin
    h2 = np.max(np.abs(np.diff(h, 2))) / (da * da)
    margin = (2.0 * k * k + 2.0 * h2) * da * da / 8.0
    # V on a xi grid (Gauss-Legendre panels over [0, xi_max])
    edges = np.linspace(0.0, xi_max, 1201)
    gx, gw = leggauss(8)
    half = 0.5 * np.diff(edges)[:, None]
    mid = 0.5 * (edges[:-1] + edges[1:])[:, None]
    xi = (mid + half * gx[None, :]).ravel()
    wxi = (half * gw[None, :]).ravel()
    V = np.empty(xi.size)
    for start in range(0, xi.size, 64):
        X = xi[start:start + 64, None]
        V[start:start + 64] = np.min(k * k * (a[None, :] - X) ** 2 + h[None, :], axis=1)
    V = np.maximum(V - margin, 0.0)
    dens = 2.0 * np.exp(-0.5 * (xi / sigma) ** 2) / (sigma * math.sqrt(2.0 * math.pi))
    val = float(np.sum(wxi * dens * V))
    return {"name": "genie_two_point", "value": val, "grid_margin": float(margin)}


# ------------------------------------------------------ Grover-Wagner-Sahai, m = 1
def _gws_closed_form(k: float, sigma: float, g):
    g = np.asarray(g, dtype=float)
    return k * k * (2.0 * sigma * np.sqrt((1.0 - g) / (g * (1.0 + k * k * g))) - (1.0 - g) * (sigma * sigma + g) / g)


def grover_wagner_sahai(k: float, sigma: float) -> dict:
    g = expit(np.linspace(-15.0, 15.0, 6001))  # gamma in (0, 1), dense near both ends
    v = _gws_closed_form(k, sigma, g)
    i = int(np.argmax(v))
    lo, hi = float(g[max(i - 1, 0)]), float(g[min(i + 1, g.size - 1)])
    res = minimize_scalar(lambda t: -float(_gws_closed_form(k, sigma, t)), bounds=(lo, hi),
                          method="bounded", options={"xatol": 1e-15})
    gamma = float(res.x) if -res.fun > v[i] else float(g[i])
    val = float(_gws_closed_form(k, sigma, gamma))
    return {"name": "grover_wagner_sahai", "value": max(val, 0.0), "gamma": gamma}


BOUND_INFO = {
    "grover_sahai": {
        "label": "Grover–Sahai",
        "equation": 7,
        "source": "https://www.inderscience.com/filter.php?aid=31164",
        "source_label": "Grover & Sahai (2010); also Theorem 2 of Grover, Park & Sahai",
        "authors": "P. Grover, A. Sahai",
        "year": 2010,
        "evidence": "Peer-reviewed",
        "note": "Holds for every vector length.",
    },
    "grover_park_sahai": {
        "label": "Grover–Park–Sahai, scalar case",
        "equation": 8,
        "source": "https://www.arxiv.org/abs/1003.0514",
        "source_label": "Grover, Park & Sahai, Theorem 3 with $m = 1$",
        "authors": "P. Grover, S. Y. Park, A. Sahai",
        "year": 2010,
        "evidence": "Peer-reviewed",
        "note": "Sphere-packing bound.",
    },
    "genie_two_point": {
        "label": "Witsenhausen",
        "equation": 9,
        "source": "https://doi.org/10.1137/0306011",
        "source_label": "Witsenhausen (1968), Theorem 3",
        "authors": "H. S. Witsenhausen",
        "year": 1968,
        "evidence": "Peer-reviewed",
        "note": "The second controller is told $|x_0|$; generalised by Wu and Verdú (2011, Theorem 4).",
    },
    "grover_wagner_sahai": {
        "label": "Grover–Wagner–Sahai, scalar case",
        "equation": 10,
        "source": "https://arxiv.org/abs/1306.5018",
        "source_label": "Grover, Wagner & Sahai, Corollary 1 with $m = 1$",
        "authors": "P. Grover, A. B. Wagner, A. Sahai",
        "year": 2015,
        "evidence": "Peer-reviewed",
        "note": "Closed form at one $\\gamma$; every $\\gamma$ in $(0, 1)$ gives a valid bound.",
    },
}


def all_bounds(k: float, sigma: float) -> dict:
    out = {}
    for fn in (grover_sahai, grover_park_sahai, genie_two_point, grover_wagner_sahai):
        r = fn(k, sigma)
        r.update(BOUND_INFO[r["name"]])
        r["value_rounded_down"] = round_down(r["value"])
        out[r["name"]] = r
    best = max(out.values(), key=lambda r: r["value"])
    return {"bounds": out, "best": best["name"], "best_value": best["value_rounded_down"]}
