"""The data files the site is built from agree with each other and with the code.

These run with the other tests (python -m pytest -q), so a pull request that breaks a reference
between files fails before the site is built.
"""
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import score_all  # noqa: E402
from witsenhausen.bounds import BOUND_INFO, all_bounds  # noqa: E402


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


SETTINGS = load("settings.json")
SETTING_IDS = [s["id"] for s in SETTINGS["settings"]]
LITERATURE = load("literature.json")["results"]
THEORY = load("theory.json")["entries"]
SUBMISSIONS = sorted((ROOT / "submissions").glob("*/*.json"))
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
LAST_YEAR = date.today().year + 1


def test_setting_ids_are_unique_and_include_the_benchmark():
    assert len(set(SETTING_IDS)) == len(SETTING_IDS)
    assert SETTINGS["benchmark"] in SETTING_IDS


@pytest.mark.parametrize("sid", SETTING_IDS)
def test_every_setting_has_submissions(sid):
    """The pages need a verified record in every setting; scripts/make_baselines.py writes the first entries."""
    assert list((ROOT / "submissions" / sid).glob("*.json")), f"no submissions for {sid}: run scripts/make_baselines.py"


def test_every_submission_folder_is_a_setting():
    folders = {p.parent.name for p in SUBMISSIONS}
    assert folders <= set(SETTING_IDS), f"folders not in data/settings.json: {sorted(folders - set(SETTING_IDS))}"


def test_literature_rows_are_complete():
    ids = [r["id"] for r in LITERATURE]
    assert len(set(ids)) == len(ids), f"duplicate ids: {sorted({i for i in ids if ids.count(i) > 1})}"
    required = {"id", "setting", "year", "authors", "title", "venue", "url", "method", "structure",
                "reported_cost", "reported_as", "verified_by", "notes"}
    for r in LITERATURE:
        assert not required - set(r), f"{r['id']}: missing {sorted(required - set(r))}"
        assert r["setting"] in SETTING_IDS, f"{r['id']}: unknown setting {r['setting']!r}"
        assert isinstance(r["year"], int) and 1960 <= r["year"] <= LAST_YEAR, f"{r['id']}: year {r['year']!r}"
        assert r["url"].startswith("https://"), f"{r['id']}: url {r['url']!r}"


def test_printed_costs_match_their_numbers():
    """reported_as is the cost as printed; reported_cost is the same number, used for sorting."""
    for r in LITERATURE:
        assert float(r["reported_as"]) == r["reported_cost"], \
            f"{r['id']}: reported_as {r['reported_as']} but reported_cost {r['reported_cost']}"


def test_verified_by_points_to_a_submission_in_the_same_setting():
    for r in LITERATURE:
        if r["verified_by"] is not None:
            path = ROOT / "submissions" / r["setting"] / f"{r['verified_by']}.json"
            assert path.exists(), f"{r['id']}: verified_by {r['verified_by']!r}, but {path.relative_to(ROOT).as_posix()} does not exist"


def test_disputed_records_are_complete():
    for r in LITERATURE:
        d = r.get("disputed")
        if d is None:
            continue
        assert DATE.fullmatch(str(d.get("date", ""))), f"{r['id']}: disputed date {d.get('date')!r}"
        assert str(d.get("reason", "")).strip(), f"{r['id']}: disputed without a reason"
        if d.get("note"):
            assert (ROOT / d["note"]).exists(), f"{r['id']}: note {d['note']} does not exist"


def test_ai_assistance_is_a_sentence_when_given():
    """An entry made with an AI model's help says which model and what it did; the leaderboard tags it AI-assisted."""
    where = [(f"literature {r['id']}", r) for r in LITERATURE]
    where += [(p.relative_to(ROOT).as_posix(), json.loads(p.read_text(encoding="utf-8"))) for p in SUBMISSIONS]
    for name, item in where:
        if "ai_assistance" in item:
            v = item["ai_assistance"]
            assert isinstance(v, str) and v.strip(), f"{name}: ai_assistance must be a non-empty sentence, got {v!r}"


def test_theory_entries_are_complete_and_in_order():
    required = {"year", "kind", "authors", "title", "venue", "url", "evidence", "claim"}
    for t in THEORY:
        assert not required - set(t), f"{t.get('title')}: missing {sorted(required - set(t))}"
        assert t["evidence"] in ("Peer-reviewed", "Preprint"), f"{t['title']}: evidence {t['evidence']!r}"
        assert t["url"] is None or t["url"].startswith("https://"), f"{t['title']}: url {t['url']!r}"
    years = [t["year"] for t in THEORY]
    assert years == sorted(years), "the theory log is shown in this order, so keep it sorted by year"


def test_dollar_signs_come_in_pairs():
    """Text may hold inline LaTeX between dollar signs; an odd count shows raw TeX on the site.
    scripts/check_site.py also parses every formula with KaTeX."""
    texts = [(f"literature {r['id']}: {k}", v) for r in LITERATURE for k, v in r.items() if isinstance(v, str)]
    texts += [(f"literature {r['id']}: disputed reason", r["disputed"]["reason"]) for r in LITERATURE if r.get("disputed")]
    texts += [(f"theory {t['year']} {t['authors']}: {k}", v) for t in THEORY for k, v in t.items() if isinstance(v, str)]
    for p in SUBMISSIONS:
        sub = json.loads(p.read_text(encoding="utf-8"))
        texts += [(f"{p.relative_to(ROOT).as_posix()}: {k}", sub[k]) for k in ("name", "short_name", "method", "ai_assistance", "notes")
                  if isinstance(sub.get(k), str)]
    bad = [where for where, text in texts if text.count("$") % 2]
    assert not bad, "odd number of $ in: " + "; ".join(bad)


def test_bounds_cache_covers_every_setting():
    """data/bounds.json is only recomputed when it lacks a setting or BOUNDS_VERSION changes."""
    cache = load("bounds.json")
    for s in SETTINGS["settings"]:
        e = cache.get(s["id"])
        assert e is not None, f"{s['id']} is missing from data/bounds.json: run scripts/score_all.py"
        assert (e["version"], e["k"], e["sigma"]) == (score_all.BOUNDS_VERSION, s["k"], s["sigma"]), \
            f"data/bounds.json is stale for {s['id']}: run scripts/score_all.py"
        assert set(e["bounds"]) == set(BOUND_INFO), f"data/bounds.json lists other bounds than witsenhausen/bounds.py for {s['id']}"


def test_cached_bounds_match_the_code():
    """A change to a bound needs a new BOUNDS_VERSION in scripts/score_all.py, or the site keeps the old values.
    Recomputes the benchmark (about 15 seconds)."""
    bench = next(s for s in SETTINGS["settings"] if s["id"] == SETTINGS["benchmark"])
    fresh = all_bounds(bench["k"], bench["sigma"])
    cached = load("bounds.json")[bench["id"]]
    for name, b in fresh["bounds"].items():
        old = cached["bounds"][name]["value"]
        assert math.isclose(b["value"], old, rel_tol=1e-6, abs_tol=1e-12), \
            f"{name}: code gives {b['value']!r}, data/bounds.json has {old!r}; bump BOUNDS_VERSION and rerun scripts/score_all.py"
    assert fresh["best"] == cached["best"]
