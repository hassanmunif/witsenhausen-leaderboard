"""The closed-form Grover-Wagner-Sahai bound, equation (10) on the problem page.

It is checked against a direct minimisation of their Corollary 1 at the same gamma,
which it must never exceed, and against costs that controllers actually achieve.
"""

import math
import sys
from pathlib import Path

import pytest
from scipy.optimize import minimize, minimize_scalar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from witsenhausen.bounds import grover_wagner_sahai  # noqa: E402


def corollary_1(P, c, g, sigma):
    """(1/g^2) ((sqrt(s^2/(1+s^2+P+2c)) - sqrt((1-g)^2 s^2 + g^2 P - 2g(1-g)c))^+)^2."""
    r1 = 1.0 + sigma * sigma + P + 2.0 * c
    r2 = (1.0 - g) ** 2 * sigma * sigma + g * g * P - 2.0 * g * (1.0 - g) * c
    if r1 <= 0.0 or r2 < 0.0:
        return math.inf
    return (max(math.sqrt(sigma * sigma / r1) - math.sqrt(r2), 0.0) / g) ** 2


@pytest.mark.parametrize("k", [0.1, 0.2, 0.3, 0.4, 0.5])
def test_closed_form_matches_corollary_1_at_sigma_5(k):
    sigma = 5.0
    b = grover_wagner_sahai(k, sigma)

    def cost(x):  # k^2 P + Corollary 1 at fixed gamma, with |c| <= sigma sqrt(P) kept
        P, c = x
        if P < 0.0 or abs(c) > sigma * math.sqrt(P):
            return 1e9
        return k * k * P + corollary_1(P, c, b["gamma"], sigma)

    direct = min(minimize(cost, [P0, 0.0], method="Nelder-Mead",
                          options={"xatol": 1e-12, "fatol": 1e-15, "maxiter": 20000}).fun for P0 in (0.3, 0.9, 2.0))
    assert b["value"] <= direct + 1e-12      # a relaxation can only lower the bound
    assert direct - b["value"] < 1e-8        # and at sigma = 5 it loses nothing


def test_benchmark_value():
    b = grover_wagner_sahai(0.2, 5.0)
    assert 0.0370807 < b["value"] < 0.0370808 and 0.96 < b["gamma"] < 0.97


@pytest.mark.parametrize("sigma", [0.3, 1.0, 5.0, 20.0])
@pytest.mark.parametrize("k", [0.05, 0.2, 0.5, 1.0, 3.0])
def test_never_above_an_achievable_cost(k, sigma):
    def linear(lam):
        return k * k * sigma * sigma * (1 - lam) ** 2 + lam * lam * sigma * sigma / (1 + lam * lam * sigma * sigma)
    best_linear = min(minimize_scalar(linear, bounds=b, method="bounded").fun for b in [(0.0, 0.5), (0.5, 1.5)])
    assert grover_wagner_sahai(k, sigma)["value"] <= min(k * k * sigma * sigma, best_linear) + 1e-12
