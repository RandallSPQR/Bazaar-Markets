"""Re-run the engine from a log and assert that it reproduces the log exactly.

    python -m cli.replay runs/bazaar_s3.jsonl [--out runs/bazaar_s3.replay.jsonl]

The engine is rebuilt from the header's config and seed. Agents are replaced
by the raw outputs recorded in the log, in order. The new log must match the
old one byte for byte. Only the header's `env` block and `engine_version` may
differ; those are reported as warnings. A log from another engine version that
does not replay is reported with that version difference as the likely cause. Exit status: 0 = identical, 1 = mismatch.
"""
from __future__ import annotations

import argparse
import json

from engine.runner import compare_logs, replay


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("--out", help="also write the replayed log here")
    args = ap.parse_args(argv)
    with open(args.log, encoding="utf-8") as f:
        old = [line.rstrip("\n") for line in f if line.strip()]
    _, new = replay(old)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(new.text())
    res = compare_logs(old, new.lines)
    for w in res.get("warnings", []):
        print("warning:", w)
    if res["identical"]:
        out = json.loads(old[-1])
        print(f"REPLAY OK: {res['lines']} lines identical")
        if out.get("ev") == "outcome":
            keys = [k for k in ("dec_share_imp_last", "buyer_surplus_mean_cents", "shortfall_rate",
                                "deceptive_share_impressions", "catches") if k in out]
            print("outcome:", {k: out[k] for k in keys})
        return 0
    print("REPLAY MISMATCH:", json.dumps(res, indent=1))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
