"""Controller constructors and the submission file format.

A submission describes the first controller x1 = f(x0).  The second
controller is never submitted: the evaluator always uses the optimal one,
g*(y) = E[X1 | Y = y].

Supported ``controller.type`` values
------------------------------------
``linear``
    {"type": "linear", "gain": lam}                      f(x) = lam * x
``piecewise_affine``
    {"type": "piecewise_affine",
     "breakpoints": [t1, ..., t_{n-1}],                  strictly increasing
     "intercepts":  [a0, ..., a_{n-1}],
     "slopes":      [b0, ..., b_{n-1}]}
    f(x) = a_i + b_i x on [t_i, t_{i+1}), with t_0 = -inf and t_n = +inf.
``odd_piecewise_affine``
    Same fields, describing x >= 0 only; f is extended by f(-x) = -f(x).
    "breakpoints" are the positive breakpoints p1 < ... < pm, and piece j is
    [p_j, p_{j+1}) with p_0 = 0 and p_{m+1} = +inf.
``points``
    {"type": "points", "x": [...], "y": [...], "odd": false,
     "extrapolation": "linear" | "constant"}
    Linear interpolation through the points (x must be strictly increasing).
    Outside the table the end segments are continued ("linear") or held
    constant ("constant").  With "odd": true the table describes x >= 0
    (x[0] must be 0 and y[0] must be 0) and f is extended as an odd function.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .evaluator import PiecewiseAffine

SCHEMA = "witsenhausen-controller/v1"


def linear(gain: float) -> PiecewiseAffine:
    return PiecewiseAffine([], [0.0], [float(gain)])


def two_point(amplitude: float) -> PiecewiseAffine:
    """Witsenhausen's 1968 design: f(x) = amplitude * sign(x)."""
    a = float(amplitude)
    return PiecewiseAffine([0.0], [-a, a], [0.0, 0.0])


def odd_piecewise_affine(breakpoints, intercepts, slopes) -> PiecewiseAffine:
    """Odd extension of a piecewise-affine description of f on [0, inf)."""
    p = np.asarray(breakpoints, dtype=float).ravel()
    c = np.asarray(intercepts, dtype=float).ravel()
    d = np.asarray(slopes, dtype=float).ravel()
    if c.size != p.size + 1 or d.size != c.size:
        raise ValueError("need len(intercepts) == len(slopes) == len(breakpoints) + 1")
    if p.size and (p[0] <= 0 or np.any(np.diff(p) <= 0)):
        raise ValueError("positive-half breakpoints must be > 0 and strictly increasing")
    # Negative half, from -inf up to 0: piece j mirrored is (-p_{j+1}, -p_j]
    neg_t = -p[::-1]
    neg_a = -c[::-1]
    neg_b = d[::-1]
    if c[0] == 0.0:
        # the two halves of the centre piece are the same line: merge them
        t = np.concatenate((neg_t, p))
        a = np.concatenate((neg_a[:-1], c))
        b = np.concatenate((neg_b[:-1], d))
    else:
        t = np.concatenate((neg_t, [0.0], p))
        a = np.concatenate((neg_a, c))
        b = np.concatenate((neg_b, d))
    return PiecewiseAffine(t, a, b)


def from_points(x, y, odd: bool = False, extrapolation: str = "linear") -> PiecewiseAffine:
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    if x.size != y.size or x.size < 2:
        raise ValueError("need at least two (x, y) points of equal length")
    if np.any(np.diff(x) <= 0):
        raise ValueError("x must be strictly increasing")
    if extrapolation not in ("linear", "constant"):
        raise ValueError("extrapolation must be 'linear' or 'constant'")
    slopes = np.diff(y) / np.diff(x)
    inter = y[:-1] - slopes * x[:-1]
    if extrapolation == "linear":
        left = (inter[0], slopes[0])
        right = (inter[-1], slopes[-1])
    else:
        left = (y[0], 0.0)
        right = (y[-1], 0.0)
    if odd:
        if x[0] != 0.0 or y[0] != 0.0:
            raise ValueError("odd tables must start at (0, 0)")
        # pieces on [x_j, x_{j+1}) for j >= 0, then the right tail
        bps = x[1:]
        c = np.concatenate((inter, [right[0]]))
        d = np.concatenate((slopes, [right[1]]))
        return odd_piecewise_affine(bps, c, d)
    bps = x
    a = np.concatenate(([left[0]], inter, [right[0]]))
    b = np.concatenate(([left[1]], slopes, [right[1]]))
    return PiecewiseAffine(bps, a, b)


def controller_from_spec(spec: dict) -> PiecewiseAffine:
    kind = spec.get("type")
    if kind == "linear":
        return linear(spec["gain"])
    if kind == "piecewise_affine":
        return PiecewiseAffine(spec["breakpoints"], spec["intercepts"], spec["slopes"])
    if kind == "odd_piecewise_affine":
        return odd_piecewise_affine(spec["breakpoints"], spec["intercepts"], spec["slopes"])
    if kind == "points":
        return from_points(
            spec["x"], spec["y"],
            odd=bool(spec.get("odd", False)),
            extrapolation=spec.get("extrapolation", "linear"),
        )
    raise ValueError(f"unknown controller type: {kind!r}")


REQUIRED_FIELDS = ("schema", "name", "authors", "date", "setting", "controller")


def validate_submission(sub: dict) -> list[str]:
    """Return a list of problems (empty if the submission is well formed)."""
    problems = []
    for key in REQUIRED_FIELDS:
        if key not in sub:
            problems.append(f"missing field '{key}'")
    if problems:
        return problems
    if sub["schema"] != SCHEMA:
        problems.append(f"schema must be '{SCHEMA}'")
    if not isinstance(sub["authors"], list) or not sub["authors"]:
        problems.append("authors must be a non-empty list")
    setting = sub["setting"]
    if not isinstance(setting, dict) or "k" not in setting or "sigma" not in setting:
        problems.append("setting must have 'k' and 'sigma'")
    try:
        controller_from_spec(sub["controller"])
    except Exception as exc:  # noqa: BLE001 - report any parse error
        problems.append(f"controller: {exc}")
    return problems


def load_submission(path) -> tuple[dict, PiecewiseAffine]:
    sub = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = validate_submission(sub)
    if problems:
        raise ValueError(f"{path}: " + "; ".join(problems))
    return sub, controller_from_spec(sub["controller"])
