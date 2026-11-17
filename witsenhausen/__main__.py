"""Command line:  python -m witsenhausen score FILE.json [FILE.json ...]
                python -m witsenhausen bounds --k 0.2 --sigma 5
"""

import argparse
import json
import sys

from .bounds import all_bounds
from .controllers import load_submission
from .evaluator import evaluate


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m witsenhausen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sc = sub.add_parser("score", help="score submission files")
    sc.add_argument("files", nargs="+")
    bd = sub.add_parser("bounds", help="compute lower bounds")
    bd.add_argument("--k", type=float, required=True)
    bd.add_argument("--sigma", type=float, required=True)
    args = ap.parse_args(argv)

    if args.cmd == "score":
        status = 0
        for path in args.files:
            try:
                s, f = load_submission(path)
                r = evaluate(f, s["setting"]["k"], s["setting"]["sigma"])
                print(json.dumps({"file": path, "name": s["name"], **r.to_dict()}, indent=1))
            except Exception as exc:  # noqa: BLE001
                print(f"{path}: {exc}", file=sys.stderr)
                status = 1
        sys.exit(status)
    if args.cmd == "bounds":
        b = all_bounds(args.k, args.sigma)
        print(json.dumps(b, indent=1))


if __name__ == "__main__":
    main()
