#!/usr/bin/env python3
"""Write Zhu's (2026) controllers as submission files, one per setting.

Q. Zhu, "From optimal transport to optimal quantization: a variational study of the Witsenhausen
counterexample", arXiv:2609.18992v2 (8 October 2026). Its ancillary file continuous_solution.json
holds, for sigma = 5 and k = 0.1, ..., 0.5, the computed transport map T at 181 grid points x_i
in [-4.5 sigma, 4.5 sigma].

The paper's feasible value J(Q_grid) (Appendix A.8(ii)) is the exact cost of the law with atoms
T(x_i) and Gaussian weights w_i, proportional to exp(-x_i^2 / (2 sigma^2)). The first controller that
produces this law at the least first-stage cost is the monotone (quantile) map of the paper's
Proposition 4.2: sort the atoms, add up their weights to W_1 < W_2 < ..., and send the cell
(sigma Phi^-1(W_{i-1}), sigma Phi^-1(W_i)] to the i-th smallest atom. This script writes that map.

    python scripts/ports/zhu_2026.py path/to/continuous_solution.json

The file is at https://arxiv.org/src/2609.18992v2/anc/continuous_solution.json. The scorer then
checks each controller against the paper's value for it (claimed_cost, within 1e-6).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.special import ndtri

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from witsenhausen import SCHEMA  # noqa: E402

SIGMA = 5.0                 # every scalar solve in the file uses sigma = 5
DATE = "2026-10-08"         # arXiv v2, the version with the ancillary files
VERIFIED_ON = "2026-11-17"
PAPER = "https://arxiv.org/abs/2609.18992"


def quantile_map(x, levels, sigma):
    """The monotone map from N(0, sigma^2) onto the atoms `levels` with Gaussian weights at x."""
    x, levels = np.asarray(x, dtype=float), np.asarray(levels, dtype=float)
    w = np.exp(-x * x / (2.0 * sigma * sigma))
    w /= w.sum()
    order = np.argsort(levels, kind="stable")
    cuts = sigma * ndtri(np.cumsum(w[order])[:-1])
    if not np.all(np.diff(cuts) > 0):
        raise ValueError("cell boundaries are not increasing")
    return {"type": "piecewise_affine", "breakpoints": cuts.tolist(),
            "intercepts": levels[order].tolist(), "slopes": [0.0] * levels.size}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("data", type=Path, help="continuous_solution.json from the paper's ancillary files")
    args = ap.parse_args(argv)
    data = json.loads(args.data.read_text(encoding="utf-8"))
    settings = json.loads((ROOT / "data" / "settings.json").read_text(encoding="utf-8"))["settings"]
    for s in settings:
        key = f"{s['k']:g}"
        if s["sigma"] != SIGMA or key not in data:
            continue
        sol = data[key]
        value = sol["certified_upper_bound"]
        sub = {
            "schema": SCHEMA,
            "name": "Zhu's discretized transport map, 181 levels",
            "short_name": "Zhu's transport map",
            "authors": ["Q. Zhu"],
            "ported_by": "H. Munif",
            "date": DATE,
            "verified_on": VERIFIED_ON,
            "setting": {"k": s["k"], "sigma": s["sigma"]},
            "method": "Optimal-transport map on a 181-point grid, read as a law with 181 atoms",
            "source": {"kind": "paper", "url": PAPER},
            "claimed_cost": value,
            "notes": "Made by scripts/ports/zhu_2026.py from the paper's ancillary file continuous_solution.json. "
                     "The grid values $\\hat T(x_i)$ become levels with Gaussian weights, and $f$ sends the cell "
                     "$(\\sigma\\Phi^{-1}(W_{i-1}),\\ \\sigma\\Phi^{-1}(W_i)]$ to the $i$-th smallest level, where the "
                     "$W_i$ add up the weights in that order: the least-cost map onto this law, as in the paper's "
                     f"Proposition 4.2. The file gives ${value}$ for this law.",
            "controller": quantile_map(data["x"], sol["y"], SIGMA),
        }
        path = ROOT / "submissions" / s["id"] / "zhu-2026.json"
        path.write_text(json.dumps(sub, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{s['id']}: wrote {path.relative_to(ROOT)} ({len(sol['y'])} levels, paper's value {value})")


if __name__ == "__main__":
    main()
