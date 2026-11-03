"""Run one configuration.

    python -m cli.run --mode bazaar --seed 3 --log runs/bazaar_s3.jsonl --normalize
    python -m cli.run --config configs/m0_baseline.json --log runs/m0_s0.jsonl
    python -m cli.run --mode bazaar --set inspectors.count=6 --set detection.form=step
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from engine.config import load
from engine.runner import run_config


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="JSON config file")
    ap.add_argument("--mode", choices=["m0", "bazaar"], help="mode, if the config file does not set one")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="dotted override, repeatable")
    ap.add_argument("--log", help="write the JSONL event log here")
    ap.add_argument("--normalize", action="store_true",
                    help="bazaar: also run the random and informed reference buyers on the same world and seed")
    args = ap.parse_args(argv)
    overrides = list(args.set) + ([f"seed={args.seed}"] if args.seed is not None else [])
    cfg = load(args.config, overrides, mode=args.mode)
    if args.log:
        os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)
    out, _ = run_config(cfg, log_path=args.log, normalize=args.normalize)
    print(json.dumps(out, indent=1, sort_keys=True))
    if args.log:
        print(f"log: {args.log}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
