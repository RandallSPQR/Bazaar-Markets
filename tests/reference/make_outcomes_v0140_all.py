"""Writes tests/reference/outcomes_v0140_all.json: every cell of outcomes_v0130.json regenerated at
engine 0.14.0 (guard keys included), plus 0.14.0 cells for the liability dials (engine 0.15.0):
verification-run markets with 2 patrolling inspectors and one genuine stall busting out on day 2
(rule_genuine_bust_at), at tourist shares 0.4 and 1.0. Run from the repo root at commit 445c654
(engine 0.14.0): PYTHONPATH=. python tests/reference/make_outcomes_v0140_all.py"""
import hashlib, json, os, subprocess
from engine import ENGINE_VERSION, bazaar
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from analysis.verification import overrides as vov

HERE = os.path.dirname(os.path.abspath(__file__))
V0130 = json.load(open(os.path.join(HERE, "outcomes_v0130.json")))["cells"]
CELLS = {k: (c["overrides"], c["seed"]) for k, c in V0130.items()}
for cond, tag in (("B|t40|l1", "t40"), ("B|t100", "t100")):
    for seed in (0, 1):
        base = [*vov(cond), "market.days=4"]
        eng = bazaar.BazaarEngine(load(overrides=[*base, f"seed={seed}"], mode="bazaar"))
        sid = next(st.sid for st in sorted(eng.stalls, key=lambda s: s.idx) if st.stype == "genuine")
        ov = [*base, "agents.seller.genuine=rule_genuine_bust_at",
              f'agents.params.rule_genuine_bust_at.schedule={{"{sid}":2}}']
        CELLS[f"v0140_bust_{tag}|{seed}"] = (ov, seed)


def catches(o):
    return sum(d["outcome"]["catches"] for d in o["days"]) if "days" in o else o["catches"]


out = {"engine_version": ENGINE_VERSION,
       "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip(),
       "cells": {}}
for key, (ov, seed) in sorted(CELLS.items()):
    log = JsonlLog(keep=True)
    o = bazaar.run(load(overrides=[*ov, f"seed={seed}"], mode="bazaar"), log=log)
    body = hashlib.sha256("\n".join(log.lines[1:]).encode()).hexdigest()
    out["cells"][key] = {"overrides": ov, "seed": seed, "outcome": dumps(o), "log_body_sha256": body,
                         "log_lines": len(log.lines), "catches": catches(o)}
json.dump(out, open(os.path.join(HERE, "outcomes_v0140_all.json"), "w"), indent=1, sort_keys=True)
print(ENGINE_VERSION, out["commit"], len(out["cells"]))
