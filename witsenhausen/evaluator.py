"""Reference cost evaluator for Witsenhausen's counterexample.

Model
-----
    X0 ~ N(0, sigma^2),  W ~ N(0, 1), independent
    X1 = f(X0)            first controller   (its input is U1 = f(X0) - X0)
    Y  = X1 + W           what the second controller observes
    J  = k^2 E[(f(X0) - X0)^2] + E[(X1 - g(Y))^2]

For any f the best second controller is the conditional mean
g*(y) = E[X1 | Y = y].  The evaluator always uses g*, so a controller is a
single function f and its score is J(f) = J(f, g*).

Controllers are piecewise affine with finitely many pieces (jumps allowed):

    f(x) = a_i + b_i x   for x in [t_i, t_{i+1}),   t_0 = -inf, t_n = +inf.

Any controller can be approximated arbitrarily well in cost by such
functions, and every controller in the literature (steps, sloped steps,
sampled tables) is of this form.

Method
------
* k^2 E[(f - X0)^2] and E[X1^2] are sums of closed-form truncated-Gaussian
  moments (no quadrature).
* Given y, each piece contributes in closed form to the density of Y and to
  E[X1 | Y = y]:

      int_{t_i}^{t_{i+1}} phi_sigma(x) phi(y - a_i - b_i x) dx
          = N(y; a_i, 1 + b_i^2 sigma^2) * [Phi(beta_i) - Phi(alpha_i)]

  because X0 restricted to the piece is, given y, a truncated Gaussian with
  mean mu_i = b_i sigma^2 (y - a_i) / (1 + b_i^2 sigma^2) and standard
  deviation s_i = sigma / sqrt(1 + b_i^2 sigma^2); alpha_i, beta_i are the
  piece edges in that standardized coordinate.  Everything is done in log
  space, so far tails neither underflow nor overflow.
* E[g*(Y)^2] = int p_Y(y) g*(y)^2 dy is the only numerical integral.  It is
  computed with composite Gauss-Legendre quadrature on a window that holds
  all but a provably negligible part of the mass, then repeated with panels
  of half the width; the difference is the reported quadrature error.
* MMSE = E[X1^2] - E[g*(Y)^2] and J = k^2 E[U1^2] + MMSE.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.special import log_ndtr, logsumexp

__all__ = [
    "EVALUATOR_VERSION",
    "PiecewiseAffine",
    "EvaluationResult",
    "evaluate",
    "posterior_mean",
]

EVALUATOR_VERSION = "1.0.0"

_LOG_SQRT_2PI = 0.5 * math.log(2.0 * math.pi)
# Standardized interval width below which midpoint series are used.  The
# truncated terms are O(w^4) relative, i.e. < 1e-12 for w < 1e-3.
_NARROW = 1e-3
# P(|N(0,1)| > 14) ~ 1.6e-44: margins used to bound the y-window.
_TAIL_Z = 14.0


# --------------------------------------------------------------------------
# Controllers
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PiecewiseAffine:
    """f(x) = intercepts[i] + slopes[i] * x on [breakpoints[i-1], breakpoints[i]).

    ``breakpoints`` has n-1 finite, strictly increasing entries; the first
    piece extends to -inf and the last to +inf.
    """

    breakpoints: np.ndarray
    intercepts: np.ndarray
    slopes: np.ndarray

    def __post_init__(self) -> None:
        t = np.asarray(self.breakpoints, dtype=float).ravel()
        a = np.asarray(self.intercepts, dtype=float).ravel()
        b = np.asarray(self.slopes, dtype=float).ravel()
        if a.shape != b.shape:
            raise ValueError("intercepts and slopes must have the same length")
        if a.size != t.size + 1:
            raise ValueError(
                f"need len(intercepts) == len(breakpoints) + 1, got {a.size} and {t.size}"
            )
        if t.size and (not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0)):
            raise ValueError("breakpoints must be finite and strictly increasing")
        if not (np.all(np.isfinite(a)) and np.all(np.isfinite(b))):
            raise ValueError("intercepts and slopes must be finite")
        object.__setattr__(self, "breakpoints", t)
        object.__setattr__(self, "intercepts", a)
        object.__setattr__(self, "slopes", b)

    @property
    def n_pieces(self) -> int:
        return int(self.intercepts.size)

    def edges(self) -> tuple[np.ndarray, np.ndarray]:
        lo = np.concatenate(([-np.inf], self.breakpoints))
        hi = np.concatenate((self.breakpoints, [np.inf]))
        return lo, hi

    def __call__(self, x):
        x = np.asarray(x, dtype=float)
        idx = np.searchsorted(self.breakpoints, x, side="right")
        return self.intercepts[idx] + self.slopes[idx] * x

    def with_breakpoints(self, extra) -> "PiecewiseAffine":
        """Same function, with additional (redundant) breakpoints inserted."""
        extra = np.asarray(extra, dtype=float).ravel()
        if self.breakpoints.size:
            # drop extras that (numerically) duplicate an existing breakpoint
            near = np.min(np.abs(extra[:, None] - self.breakpoints[None, :]), axis=1)
            extra = extra[near > 1e-9 * (1.0 + np.abs(extra))]
        t = np.union1d(self.breakpoints, extra)
        lo = np.concatenate(([-np.inf], t))
        hi = np.concatenate((t, [np.inf]))
        probe = np.where(
            np.isfinite(lo) & np.isfinite(hi),
            0.5 * (lo + hi),
            np.where(np.isfinite(lo), lo + 1.0, hi - 1.0),
        )
        probe[(~np.isfinite(lo)) & (~np.isfinite(hi))] = 0.0
        idx = np.searchsorted(self.breakpoints, probe, side="right")
        return PiecewiseAffine(t, self.intercepts[idx], self.slopes[idx])


# --------------------------------------------------------------------------
# Truncated standard normal moments
# --------------------------------------------------------------------------
def _log_phi(z):
    return -0.5 * z * z - _LOG_SQRT_2PI


def _trunc_moments(lo, hi, need_var: bool = False):
    """For Z ~ N(0,1) and lo < hi (either may be infinite) return

        log P(lo < Z < hi),  E[Z | lo < Z < hi],  Var[Z | lo < Z < hi] (optional)

    elementwise, accurately in the far tails and for very narrow intervals.
    """
    lo = np.asarray(lo, dtype=float)
    hi = np.asarray(hi, dtype=float)
    lo, hi = np.broadcast_arrays(lo, hi)
    shape = lo.shape
    lo = lo.ravel()
    hi = hi.ravel()
    logp = np.empty(lo.size)
    mean = np.empty(lo.size)
    var = np.empty(lo.size) if need_var else None

    with np.errstate(invalid="ignore", over="ignore"):
        width = hi - lo
    narrow = np.isfinite(width) & (width < _NARROW)
    wide = ~narrow

    if narrow.any():
        m = 0.5 * (lo[narrow] + hi[narrow])
        w = width[narrow]
        w2 = w * w
        m2 = m * m
        with np.errstate(divide="ignore"):  # zero-width pieces have log P = -inf
            logw_ = np.log(w)
        logp[narrow] = (
            _log_phi(m)
            + logw_
            + np.log1p((m2 - 1.0) * w2 / 24.0 + (m2 * m2 - 6.0 * m2 + 3.0) * w2 * w2 / 1920.0)
        )
        mean[narrow] = m * (1.0 - w2 / 12.0)
        if need_var:
            var[narrow] = w2 / 12.0

    if wide.any():
        l = lo[wide]
        h = hi[wide]
        lp = np.empty(l.size)
        upper = l >= 0.0
        lower = h <= 0.0
        mid = ~(upper | lower)
        with np.errstate(divide="ignore", invalid="ignore"):
            if lower.any():
                lh = log_ndtr(h[lower])
                ll = log_ndtr(l[lower])
                lp[lower] = lh + np.log(-np.expm1(ll - lh))
            if upper.any():
                lh = log_ndtr(-l[upper])
                ll = log_ndtr(-h[upper])
                lp[upper] = lh + np.log(-np.expm1(ll - lh))
            if mid.any():
                lp[mid] = np.log1p(
                    -(np.exp(log_ndtr(l[mid])) + np.exp(log_ndtr(-h[mid])))
                )
            logp[wide] = lp
            el = np.exp(_log_phi(l) - lp)  # phi(-inf) = 0 -> 0
            eh = np.exp(_log_phi(h) - lp)
            mu = el - eh
            mu = np.where(np.isfinite(lp), mu, 0.5 * (np.clip(l, -1e300, 1e300) + np.clip(h, -1e300, 1e300)))
            mean[wide] = mu
            if need_var:
                lt = np.where(np.isfinite(l), l * el, 0.0)
                ht = np.where(np.isfinite(h), h * eh, 0.0)
                v = 1.0 + lt - ht - mu * mu
                var[wide] = np.where(np.isfinite(lp), np.maximum(v, 0.0), 0.0)

    out = (logp.reshape(shape), mean.reshape(shape))
    if need_var:
        out = out + (var.reshape(shape),)
    return out


# --------------------------------------------------------------------------
# Closed-form first-stage terms
# --------------------------------------------------------------------------
def _piece_moments(f: PiecewiseAffine, sigma: float):
    """Per piece: P(piece), E[X0 | piece], Var[X0 | piece]."""
    lo, hi = f.edges()
    logp, zmean, zvar = _trunc_moments(lo / sigma, hi / sigma, need_var=True)
    p = np.exp(logp)
    return p, sigma * zmean, sigma * sigma * zvar


def _second_moment(p, mean, var, a, b):
    """sum_i E[(a_i + b_i X0)^2 ; piece i] from per-piece moments."""
    centre = a + b * mean
    return float(np.sum(p * (centre * centre + b * b * var)))


# --------------------------------------------------------------------------
# Second stage: density of Y and the conditional-mean controller
# --------------------------------------------------------------------------
def _log_weights_and_means(f: PiecewiseAffine, sigma: float, y: np.ndarray):
    """For y of shape (m,), return log w (n, m) and piece-wise conditional
    means (n, m), where w_i(y) = int_{piece i} phi_sigma(x) phi(y - f(x)) dx
    and the means are E[f(X0) | X0 in piece i, Y = y]."""
    lo, hi = f.edges()
    a = f.intercepts[:, None]
    b = f.slopes[:, None]
    v = 1.0 + (b * sigma) ** 2
    s = sigma / np.sqrt(v)
    z = y[None, :] - a
    mu = (b * sigma * sigma / v) * z
    alpha = (lo[:, None] - mu) / s
    beta = (hi[:, None] - mu) / s
    logp, tmean = _trunc_moments(alpha, beta)
    bad = ~np.isfinite(logp)
    if bad.any():
        tmean = np.where(bad, 0.0, tmean)
    logw = -0.5 * z * z / v - 0.5 * np.log(v) - _LOG_SQRT_2PI + logp
    means = a + b * (mu + s * tmean)
    return logw, means


def _chunks(m: int, n_pieces: int):
    size = max(8, 1_500_000 // max(1, n_pieces))
    for start in range(0, m, size):
        yield slice(start, min(m, start + size))


def posterior_mean(f: PiecewiseAffine, sigma: float, y) -> np.ndarray:
    """The optimal second controller g*(y) = E[X1 | Y = y]."""
    y = np.atleast_1d(np.asarray(y, dtype=float))
    out = np.empty(y.size)
    for sl in _chunks(y.size, f.n_pieces):
        logw, means = _log_weights_and_means(f, sigma, y[sl])
        L = logsumexp(logw, axis=0)
        out[sl] = np.sum(np.exp(logw - L[None, :]) * means, axis=0)
    return out


def _integrand(f: PiecewiseAffine, sigma: float, y: np.ndarray) -> np.ndarray:
    """p_Y(y) * g*(y)^2."""
    out = np.empty(y.size)
    for sl in _chunks(y.size, f.n_pieces):
        logw, means = _log_weights_and_means(f, sigma, y[sl])
        L = logsumexp(logw, axis=0)
        g = np.sum(np.exp(logw - L[None, :]) * means, axis=0)
        out[sl] = np.exp(L) * g * g
    return out


def _panels(lo: float, hi: float, width: float, order: int):
    n = max(1, int(math.ceil((hi - lo) / width)))
    edges = np.linspace(lo, hi, n + 1)
    x, w = leggauss(order)
    half = 0.5 * np.diff(edges)[:, None]
    mid = 0.5 * (edges[:-1] + edges[1:])[:, None]
    return (mid + half * x[None, :]).ravel(), (half * w[None, :]).ravel()


def _x_window(f: PiecewiseAffine, sigma: float, tol: float = 1e-30) -> float:
    """Half-width X such that E[f(X0)^2 ; |X0| > X] < tol."""
    X = _TAIL_Z * sigma
    for _ in range(40):
        g = f.with_breakpoints([-X, X])
        lo, hi = g.edges()
        p, m, v = _piece_moments(g, sigma)
        outside = (hi <= -X) | (lo >= X)
        tail = _second_moment(p[outside], m[outside], v[outside],
                              g.intercepts[outside], g.slopes[outside])
        if tail < tol:
            return X
        X *= 1.5
    raise ValueError("controller grows too fast in the tails to be evaluated")


def _f_range(f: PiecewiseAffine, X: float) -> tuple[float, float]:
    t = f.breakpoints
    t = t[(t > -X) & (t < X)]
    xs = np.concatenate(([-X, X], t))
    vals = [f(xs)]
    if t.size:
        idx = np.searchsorted(f.breakpoints, t, side="left")  # piece ending at t
        vals.append(f.intercepts[idx] + f.slopes[idx] * t)
    vals = np.concatenate(vals)
    return float(vals.min()), float(vals.max())


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
@dataclass
class EvaluationResult:
    k: float
    sigma: float
    cost: float              # J = k^2 E[U1^2] + MMSE
    stage1: float            # k^2 E[U1^2]
    power: float             # E[U1^2]
    mmse: float              # E[(X1 - E[X1|Y])^2]
    second_moment: float     # E[X1^2]
    mean_x1: float           # E[X1]
    error_estimate: float    # bound-style estimate of |cost - exact cost|
    quadrature_error: float  # |difference between the two quadrature resolutions|
    n_pieces: int
    n_nodes: int
    evaluator_version: str = EVALUATOR_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate(
    f: PiecewiseAffine,
    k: float,
    sigma: float,
    panel_width: float = 0.2,
    order: int = 16,
    check: bool = True,
) -> EvaluationResult:
    """Exact-up-to-quadrature cost J(f) of controller ``f`` for parameters
    (k, sigma), with the optimal second controller.

    The y-integral is computed with panels of ``panel_width`` and
    ``order``-point Gauss-Legendre rules; if ``check`` it is recomputed with
    half-width panels and the finer value is returned.
    """
    if not (k >= 0 and sigma > 0):
        raise ValueError("need k >= 0 and sigma > 0")
    k = float(k)
    sigma = float(sigma)

    p, m, v = _piece_moments(f, sigma)
    a, b = f.intercepts, f.slopes
    ex1sq = _second_moment(p, m, v, a, b)
    power = _second_moment(p, m, v, a, b - 1.0)
    mean_x1 = float(np.sum(p * (a + b * m)))

    X = _x_window(f, sigma)
    fmin, fmax = _f_range(f, X)
    ylo, yhi = fmin - _TAIL_Z, fmax + _TAIL_Z

    nodes, weights = _panels(ylo, yhi, panel_width, order)
    eg2 = float(np.dot(weights, _integrand(f, sigma, nodes)))
    n_nodes = nodes.size
    qerr = 0.0
    if check:
        nodes2, weights2 = _panels(ylo, yhi, panel_width / 2.0, order)
        eg2_fine = float(np.dot(weights2, _integrand(f, sigma, nodes2)))
        qerr = abs(eg2_fine - eg2)
        eg2 = eg2_fine
        n_nodes += nodes2.size

    mmse = ex1sq - eg2
    stage1 = k * k * power
    cost = stage1 + mmse
    # Rounding: a few hundred ulps of the largest quantities involved, plus
    # the series truncation for narrow pieces (relative 1e-12 of E[X1^2]).
    rounding = 256 * np.finfo(float).eps * (ex1sq + eg2 + stage1) * math.sqrt(f.n_pieces)
    narrow_pieces = np.isfinite(f.edges()[1] - f.edges()[0]) & (
        (f.edges()[1] - f.edges()[0]) < _NARROW * sigma
    )
    series = 1e-12 * ex1sq if narrow_pieces.any() else 0.0
    error = qerr + rounding + series
    return EvaluationResult(
        k=k,
        sigma=sigma,
        cost=cost,
        stage1=stage1,
        power=power,
        mmse=mmse,
        second_moment=ex1sq,
        mean_x1=mean_x1,
        error_estimate=float(error),
        quadrature_error=float(qerr),
        n_pieces=f.n_pieces,
        n_nodes=int(n_nodes),
    )
