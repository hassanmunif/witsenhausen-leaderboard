"""The scorer refuses controllers it cannot evaluate reliably and results that cannot be right."""
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import score_all  # noqa: E402

BENCHMARK = {"id": "k0.20_s5", "k": 0.2, "sigma": 5.0}


def write(tmp_path, controller, **extra):
    sub = {"schema": "witsenhausen-controller/v1", "name": "test", "authors": ["Test"], "date": "2026-11-17",
           "setting": {"k": 0.2, "sigma": 5.0}, "controller": controller, **extra}
    path = tmp_path / "test.json"
    path.write_text(json.dumps(sub), encoding="utf-8")  # json writes NaN as the literal NaN
    return path


def result(**kw):
    base = dict(cost=0.17, stage1=0.03, mmse=0.14, error_estimate=1e-11)
    base.update(kw)
    return SimpleNamespace(**base)


def test_a_normal_result_is_accepted():
    assert score_all.result_problems(result()) == []


@pytest.mark.parametrize("kw", [dict(cost=math.nan), dict(mmse=math.inf), dict(error_estimate=math.nan)])
def test_non_finite_results_are_rejected(kw):
    assert "non-finite" in score_all.result_problems(result(**kw))[0]


def test_negative_costs_are_rejected():
    assert "negative" in score_all.result_problems(result(cost=-0.5, mmse=-0.53))[0]


def test_unresolved_costs_are_rejected():
    assert "error estimate" in score_all.result_problems(result(error_estimate=2e-6))[0]
    # above 1 the limit is relative
    assert score_all.result_problems(result(cost=4e6, stage1=4e6, mmse=0.0, error_estimate=1.2e-5)) == []


def test_huge_constant_controller_is_not_ranked(tmp_path):
    """f(x) = 1e16 used to score about -5.6e31 and was accepted as the record."""
    path = write(tmp_path, {"type": "piecewise_affine", "breakpoints": [], "intercepts": [1e16], "slopes": [0.0]})
    _, entry, problems = score_all.score_file(path, BENCHMARK)
    assert entry is None and any("negative" in p for p in problems)


def test_nan_claimed_cost_is_rejected(tmp_path):
    path = write(tmp_path, {"type": "linear", "gain": 1.0}, claimed_cost=float("nan"))
    _, entry, problems = score_all.score_file(path, BENCHMARK)
    assert entry is None and "finite number" in problems[0]


def test_too_many_pieces_is_rejected_before_evaluating(tmp_path):
    n = score_all.MAX_PIECES + 10
    xs = [i / 100.0 for i in range(-n // 2, n // 2 + 2)]
    path = write(tmp_path, {"type": "points", "x": xs, "y": xs})
    _, entry, problems = score_all.score_file(path, BENCHMARK)
    assert entry is None and "pieces" in problems[0]


def test_too_steep_controller_is_rejected_before_evaluating(tmp_path):
    path = write(tmp_path, {"type": "linear", "gain": 1000.0})
    _, entry, problems = score_all.score_file(path, BENCHMARK)
    assert entry is None and "too large to evaluate" in problems[0]


def test_the_reference_controller_is_still_accepted():
    _, entry, problems = score_all.score_file(ROOT / "submissions/k0.20_s5/reference-curved-steps.json", BENCHMARK)
    assert problems == [] and abs(entry["result"]["cost"] - 0.1669223117) < 1e-9


@pytest.mark.parametrize("extra, message", [
    (dict(date="1999"), "date must be a date written YYYY-MM-DD"),
    (dict(verified_on="17/11/2026"), "verified_on must be a date written YYYY-MM-DD"),
    (dict(date="2026-11-17", verified_on="2026-11-16"), "earlier than date"),
    (dict(ported_by=" "), "ported_by must be a non-empty string"),
])
def test_bad_dates_and_credits_are_rejected(tmp_path, extra, message):
    path = write(tmp_path, {"type": "linear", "gain": 1.0}, **extra)
    _, entry, problems = score_all.score_file(path, BENCHMARK)
    assert entry is None and message in problems[0]


def test_a_port_of_an_older_paper_is_accepted(tmp_path):
    path = write(tmp_path, {"type": "linear", "gain": 1.0}, date="1968-02-01", verified_on="2026-11-17", ported_by="Someone")
    _, entry, problems = score_all.score_file(path, BENCHMARK)
    assert problems == [] and (entry["date"], entry["verified_on"], entry["ported_by"]) == ("1968-02-01", "2026-11-17", "Someone")


def entry(id_, cost, date, err=1e-11):
    return {"id": id_, "name": id_, "authors": ["A"], "date": date, "result": {"cost": cost, "error_estimate": err}}


def test_ties_share_a_rank_and_the_record_holder_comes_first():
    tol = 1e-9
    early, later = entry("early", 0.1669223117, "2017-12-01"), entry("later", 0.1669223112, "2026-11-16")
    worse = entry("worse", 0.1670, "2001-03-01")
    entries = [worse, later, early]
    record, _ = score_all.assign_records(entries, tol)
    assert record["id"] == "early"   # the later entry is lower, but not by more than the tolerance
    out = score_all.ranked(entries, tol)
    assert [(e["id"], e["rank"], e["tied"]) for e in out] == [("early", 1, True), ("later", 1, True), ("worse", 3, False)]


def test_a_clear_improvement_is_not_a_tie():
    tol = 1e-9
    entries = [entry("old", 0.1670, "2001-03-01"), entry("new", 0.1669, "2026-11-16")]
    record, _ = score_all.assign_records(entries, tol)
    out = score_all.ranked(entries, tol)
    assert record["id"] == "new" and [(e["id"], e["rank"], e["tied"]) for e in out] == [("new", 1, False), ("old", 2, False)]
