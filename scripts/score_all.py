#!/usr/bin/env python3
"""Score every submission with the reference evaluator and write data/results.json.

    python scripts/score_all.py            # score everything, refresh results.json
    python scripts/score_all.py --check    # validate + score, do not write (CI on pull requests)

Submissions live in submissions/<setting-id>/<name>.json.  A file is rejected
if it is malformed, if its "setting" disagrees with its folder, or if its
"claimed_cost" (optional) differs from the verified cost by more than 1e-6.
Lower bounds are cached in data/bounds.json (recomputed when missing).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from witsenhausen import EVALUATOR_VERSION, evaluate, load_submission, posterior_mean  # noqa: E402
from witsenhausen.bounds import BOUND_INFO, all_bounds  # noqa: E402
from witsenhausen.evaluator import _piece_moments  # noqa: E402

BOUNDS_VERSION = "1"
CLAIM_TOLERANCE = 1e-6


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def bounds_for(settings, refresh=False):
    cache_path = ROOT / "data" / "bounds.json"
    cache = load_json(cache_path) if cache_path.exists() and not refresh else {}
    changed = False
    for s in settings:
        key = s["id"]
        entry = cache.get(key)
        if entry and entry.get("version") == BOUNDS_VERSION and entry.get("k") == s["k"] and entry.get("sigma") == s["sigma"]:
            continue
        t = time.time()
        print(f"  computing lower bounds for {key} ...", flush=True)
        b = all_bounds(s["k"], s["sigma"])
        cache[key] = {"version": BOUNDS_VERSION, "k": s["k"], "sigma": s["sigma"], **b,
                      "seconds": round(time.time() - t, 1)}
        changed = True
    if changed:
        cache_path.write_text(json.dumps(cache, indent=1) + "\n", encoding="utf-8")
    # labels, sources and evidence levels always come from the code, not the cache
    for entry in cache.values():
        for name, b in entry["bounds"].items():
            b.update(BOUND_INFO[name])
    return cache


def step_summary(f, sigma, min_prob=1e-6):
    """Split f at its jumps into "steps" and report, for each one that carries
    probability, its x0-interval, its probability and its mean level E[x1 | step]."""
    p, m, _ = _piece_moments(f, sigma)
    a, b, t = f.intercepts, f.slopes, f.breakpoints
    left, right = a[:-1] + b[:-1] * t, a[1:] + b[1:] * t
    jump = np.abs(right - left) > 1e-7 * (1.0 + np.abs(left) + np.abs(right))
    starts = [0] + [int(i) + 1 for i in np.where(jump)[0]]
    ends = starts[1:] + [f.n_pieces]
    lo, hi = f.edges()
    steps = []
    for s0, e0 in zip(starts, ends):
        pr = float(p[s0:e0].sum())
        if pr < min_prob:
            continue
        level = float((p[s0:e0] * (a[s0:e0] + b[s0:e0] * m[s0:e0])).sum() / pr)
        steps.append({
            "lo": None if not np.isfinite(lo[s0]) else round(float(lo[s0]), 4),
            "hi": None if not np.isfinite(hi[e0 - 1]) else round(float(hi[e0 - 1]), 4),
            "prob": pr,
            "level": level,
        })
    xs = np.linspace(0.013, 6.0 * sigma, 97)
    odd = bool(np.allclose(f(xs), -f(-xs), atol=1e-9))
    return {"odd": odd, "n_steps": len(steps), "steps": steps[:60]}


def controller_samples(f, sigma, n=241, max_segments=1500):
    """Plot data: the exact pieces of x1 = f(x0) on [-6 sigma, 6 sigma] (or
    samples if there are too many pieces) and samples of the optimal second
    controller g*(y)."""
    L = 6.0 * sigma
    out = {}
    lo, hi = f.edges()
    keep = (hi > -L) & (lo < L)
    if keep.sum() <= max_segments:
        segs = []
        for l, h, a, b in zip(lo[keep], hi[keep], f.intercepts[keep], f.slopes[keep]):
            x0, x1 = max(l, -L), min(h, L)
            segs.append([round(float(x0), 6), round(float(a + b * x0), 6),
                         round(float(x1), 6), round(float(a + b * x1), 6)])
        out["segments"] = segs
    x = np.linspace(-L, L, 2 * n - 1)
    out["x"] = [round(float(v), 5) for v in x]
    out["f"] = [round(float(v), 6) for v in f(x)]
    y = np.linspace(-L - 4.0, L + 4.0, 2 * n - 1)
    gy = posterior_mean(f, sigma, y)
    out["y"] = [round(float(v), 5) for v in y]
    out["g"] = [round(float(v), 6) for v in gy]
    return out


def score_file(path: Path, setting: dict):
    sub, f = load_submission(path)
    problems = []
    k, sigma = setting["k"], setting["sigma"]
    if not (math.isclose(sub["setting"]["k"], k) and math.isclose(sub["setting"]["sigma"], sigma)):
        problems.append(f"setting {sub['setting']} does not match folder {setting['id']} (k={k}, sigma={sigma})")
        return sub, None, problems
    t = time.time()
    r = evaluate(f, k, sigma)
    secs = time.time() - t
    claimed = sub.get("claimed_cost")
    if claimed is not None and abs(float(claimed) - r.cost) > CLAIM_TOLERANCE:
        problems.append(f"claimed_cost {claimed} differs from verified cost {r.cost:.10f} by more than {CLAIM_TOLERANCE}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    entry = {
        "id": path.stem,
        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": digest,
        "name": sub["name"],
        "short_name": sub.get("short_name"),
        "authors": sub["authors"],
        "date": sub["date"],
        "method": sub.get("method", ""),
        "source": sub.get("source", {}),
        "notes": sub.get("notes", ""),
        "claimed_cost": claimed,
        "result": r.to_dict(),
        "eval_seconds": round(secs, 3),
        "plot": controller_samples(f, sigma),
        "steps": step_summary(f, sigma),
    }
    return sub, entry, problems


def assign_records(entries, tol):
    """Chronological record rule: a new record must beat the standing record
    by more than tol + both error estimates."""
    order = sorted(entries, key=lambda e: (e["date"], e["result"]["cost"]))
    record = None
    history = []
    for e in order:
        c, err = e["result"]["cost"], e["result"]["error_estimate"]
        if record is None or c < record["result"]["cost"] - (tol + err + record["result"]["error_estimate"]):
            record = e
            history.append({"id": e["id"], "date": e["date"], "cost": c, "name": e["name"], "authors": e["authors"]})
    for e in entries:
        e["is_record"] = record is not None and e["id"] == record["id"]
    return record, history


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate and score without writing results.json")
    ap.add_argument("--refresh-bounds", action="store_true")
    args = ap.parse_args(argv)

    settings_doc = load_json(ROOT / "data" / "settings.json")
    settings = settings_doc["settings"]
    tol = settings_doc["record_rule"]["tolerance"]
    bounds = bounds_for(settings, refresh=args.refresh_bounds)

    failures = []
    out_settings = []
    known_ids = {s["id"] for s in settings}
    for folder in sorted((ROOT / "submissions").iterdir()):
        if folder.is_dir() and folder.name not in known_ids:
            failures.append(f"{folder.name}: unknown setting folder (see data/settings.json)")

    for s in settings:
        entries = []
        folder = ROOT / "submissions" / s["id"]
        for path in sorted(folder.glob("*.json")) if folder.exists() else []:
            try:
                _, entry, problems = score_file(path, s)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{path.relative_to(ROOT)}: {exc}")
                continue
            if problems:
                failures.extend(f"{path.relative_to(ROOT)}: {p}" for p in problems)
                continue
            entries.append(entry)
            r = entry["result"]
            print(f"  {s['id']:>9}  {r['cost']:.10f} ± {r['error_estimate']:.1e}  {entry['name']}")
        entries.sort(key=lambda e: e["result"]["cost"])
        for rank, e in enumerate(entries, 1):
            e["rank"] = rank
        record, history = assign_records(entries, tol)
        b = bounds[s["id"]]
        best_cost = record["result"]["cost"] if record else None
        out_settings.append({
            **s,
            "entries": entries,
            "record_id": record["id"] if record else None,
            "record_history": history,
            "lower_bounds": b,
            "gap": None if best_cost is None else {
                "best_verified": best_cost,
                "best_lower_bound": b["best_value"],
                "absolute": best_cost - b["best_value"],
                "ratio": best_cost / b["best_value"] if b["best_value"] > 0 else None,
            },
        })

    if failures:
        print("\nREJECTED:")
        for msg in failures:
            print("  - " + msg)
    if args.check:
        sys.exit(1 if failures else 0)

    results = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evaluator_version": EVALUATOR_VERSION,
        "record_rule": settings_doc["record_rule"],
        "benchmark": settings_doc["benchmark"],
        "settings": out_settings,
        "rejected": failures,
    }
    (ROOT / "data" / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote data/results.json ({sum(len(s['entries']) for s in out_settings)} verified entries)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
