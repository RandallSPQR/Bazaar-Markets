"""Bust-out loss diagnostic (2026-11-08; no engine change).

For sellable sampled stalls of capture Stage A (lambda 0.7, tourists 0.4), run the honest chain and
the bust-out-on-day-27 chain and compare, day by day, everything the stall's profit is made of.
Also checks that the two chains are identical before the bust-out and that a bust-out changes
nothing but true quality (and the unit cost and sign that follow from it).

    .venv/bin/python -m analysis.loss_diagnostic > runs/loss_diagnostic.txt
"""
from __future__ import annotations

import hashlib
import json
import sys

from analysis.capture import config, sample_stalls
from engine import benchmark as B
from engine import brands as BR
from engine import bazaar
from engine.bazaar import BazaarEngine
from engine.jsonlog import JsonlLog

COND = "A|lam0.7|t40"
BUST = 27
FIELDS = ("units_sold", "revenue_cents", "cost_cents", "ad_spend_cents", "penalties_cents", "switch_cost_cents",
          "catches", "price_cents", "unit_cost_cents", "q_true", "sign", "stype", "rating", "brand", "busted_day")


class Tap:
    """Records every stall's end-of-day accounting by patching BazaarEngine.run."""

    def __init__(self):
        self.days: list[dict] = []
        self._orig = BazaarEngine.run

    def __enter__(self):
        tap = self

        def run(eng, *a, **k):
            # start-of-day price and rating, before the day's trading
            start = {st.sid: (st.price_cents, st.rating, st.q_true, st.sign) for st in eng.stalls}
            out = tap._orig(eng, *a, **k)
            rec = {}
            for st in eng.stalls:
                r = {f: getattr(st, f, None) for f in FIELDS}
                r["price_start"], r["rating_start"], r["q_start"], r["sign_start"] = start[st.sid]
                r["neutral_price_cents"] = BR.premium_price(eng.cfg, st, 0.5)
                rec[st.sid] = r
            tap.days.append(rec)
            return out

        BazaarEngine.run = run
        return self

    def __exit__(self, *exc):
        BazaarEngine.run = self._orig


class HashSink:
    """A log sink that keeps only a SHA-256 of each day's lines (day 0 = the header), so whole
    logs can be compared without holding them in memory."""

    def __init__(self):
        self.day, self.h, self.n = 0, {0: hashlib.sha256()}, {0: 0}

    def write(self, s: str) -> None:
        if s.startswith('{"day":') and '"ev":"day_start"' in s:
            self.day = json.loads(s)["day"]
            self.h[self.day], self.n[self.day] = hashlib.sha256(), 0
        self.h[self.day].update(s.encode())
        self.n[self.day] += 1

    def digests(self) -> dict:
        return {d: (h.hexdigest(), self.n[d]) for d, h in self.h.items()}


def chain(cfg, sid, day):
    sink = HashSink()
    log = JsonlLog(sink, keep=False)
    with Tap() as tap:
        out = bazaar.run(B.bust_config(cfg, sid, day), log=log)
    return out, tap.days, sink.digests()


def profit(r):
    return r["revenue_cents"] - r["cost_cents"] - r["ad_spend_cents"] - r["penalties_cents"] - r["switch_cost_cents"]


def pick_stalls():
    """The first sellable sampled stall of seeds 52, 53, ... (sellable = its 30-day total differs
    between the never chain and a bust-out chain, as in the capture Stage A csv), 3 in all."""
    import csv
    rows = [r for r in csv.DictReader(open("runs/capture_A.csv")) if r["condition"] == COND]
    sell = [r for r in rows if not (r["never_total_cents"] == r["total_day10_cents"] == r["total_day20_cents"]
                                    == r["total_day27_cents"])]
    picks, seen = [], set()
    for r in sorted(sell, key=lambda r: int(r["seed"])):
        if r["seed"] not in seen:
            picks.append((int(r["seed"]), r["stall"]))
            seen.add(r["seed"])
        if len(picks) == 3:
            break
    return picks


def main():
    W = sys.stdout.write
    picks = pick_stalls()
    W(f"Bust-out loss diagnostic, capture Stage A {COND}; bust-out day {BUST}.\n")
    W(f"Seed 52 has one sellable sampled stall; the other two are the first sellable sampled stalls of the next "
      f"seeds: {picks}.\n\n")
    for seed, sid in picks:
        assert sid in sample_stalls(seed)
        cfg = config(COND, seed)
        out_h, days_h, Lh = chain(cfg, None, None)
        out_b, days_b, Lb = chain(cfg, sid, BUST)
        W(f"=== seed {seed}, stall {sid} ({days_h[0][sid]['brand']}, {days_h[0][sid]['stype']})\n")
        # 1. identity before the bust-out: whole log, days 1..BUST-1
        diff_days = [d for d in range(1, BUST) if Lh.get(d) != Lb.get(d)]
        hdr_same = Lh[0] == Lb[0]
        W(f"log identical (SHA-256 of each day's lines) on days 1-{BUST - 1} (all stalls, every event): {not diff_days}"
          f"{'' if not diff_days else f' -- first differing day {diff_days[0]}'}; header identical: {hdr_same}\n")
        acct_diff = [d for d in range(BUST - 1) if days_h[d] != days_b[d]]
        W(f"end-of-day accounting identical on days 1-{BUST - 1} (all stalls): {not acct_diff}\n")
        # 2. what the bust-out changes on the stall itself
        changed = {}
        for d in range(BUST - 1, len(days_h)):
            h, b = days_h[d][sid], days_b[d][sid]
            for f in ("price_start", "brand", "stype", "neutral_price_cents", "q_true", "unit_cost_cents", "sign"):
                if h[f] != b[f]:
                    changed.setdefault(f, []).append((d + 1, h[f], b[f]))
        W(f"stall attributes that differ on days {BUST}-30: "
          f"{ {k: v[:2] for k, v in changed.items()} or 'none'}\n")
        # other stalls on days >= BUST
        others = sorted({s for d in range(BUST - 1, len(days_h)) for s in days_h[d]
                         if s != sid and profit(days_h[d][s]) != profit(days_b[d][s])})
        W(f"other stalls whose profit differs on days {BUST}-30: {len(others)} {others[:10]}\n\n")
        # 3. day by day
        W("day | units h/b | revenue h/b ($) | unit cost h/b | posted price h/b | ad h/b | penalties h/b | catches h/b "
          "| rating start h/b | q_true h/b | sign h/b | profit h/b | diff\n")
        for d in range(len(days_h)):
            h, b = days_h[d][sid], days_b[d][sid]
            if d < BUST - 4 and h == b and d % 5:
                continue
            def rt(x):
                return "-" if x is None else f"{x:.2f}"
            W(f"{d + 1:>3} | {h['units_sold']}/{b['units_sold']} | {h['revenue_cents'] / 100:.0f}/{b['revenue_cents'] / 100:.0f}"
              f" | {h['unit_cost_cents'] / 100:.2f}/{b['unit_cost_cents'] / 100:.2f}"
              f" | {h['price_start'] / 100:.2f}/{b['price_start'] / 100:.2f}"
              f" | {h['ad_spend_cents'] / 100:.2f}/{b['ad_spend_cents'] / 100:.2f}"
              f" | {h['penalties_cents'] / 100:.0f}/{b['penalties_cents'] / 100:.0f} | {h['catches']}/{b['catches']}"
              f" | {rt(h['rating_start'])}/{rt(b['rating_start'])} | {h['q_true']:.3f}/{b['q_true']:.3f}"
              f" | {h['sign']}/{b['sign']} | {profit(h) / 100:.2f}/{profit(b) / 100:.2f}"
              f" | {(profit(b) - profit(h)) / 100:+.2f}\n")
        # 4. decomposition
        comps = ("revenue_cents", "cost_cents", "ad_spend_cents", "penalties_cents", "switch_cost_cents")
        sign = {"revenue_cents": 1, "cost_cents": -1, "ad_spend_cents": -1, "penalties_cents": -1, "switch_cost_cents": -1}
        W("\nprofit difference (bust - honest), $, by component and window\n")
        W("window | " + " | ".join(c.replace("_cents", "") for c in comps) + " | total | units h/b\n")
        for name, rng in ((f"days 1-{BUST - 1}", range(0, BUST - 1)), (f"days {BUST}-30", range(BUST - 1, len(days_h))),
                          ("all", range(len(days_h)))):
            parts = [sum(sign[c] * (days_b[d][sid][c] - days_h[d][sid][c]) for d in rng) / 100 for c in comps]
            uh = sum(days_h[d][sid]["units_sold"] for d in rng)
            ub = sum(days_b[d][sid]["units_sold"] for d in rng)
            W(f"{name} | " + " | ".join(f"{p:+.2f}" for p in parts) + f" | {sum(parts):+.2f} | {uh}/{ub}\n")
        th, tb = B.stall_total(out_h, sid), B.stall_total(out_b, sid)
        hp = sum(profit(days_h[d][sid]) for d in range(BUST - 1)) / (BUST - 1) / 100
        W(f"30-day totals: honest {th / 100:.2f}, bust {tb / 100:.2f}, gain {(tb - th) / 100:+.2f}; "
          f"honest profit per day on days 1-{BUST - 1}: {hp:.2f}\n\n")


if __name__ == "__main__":
    main()
