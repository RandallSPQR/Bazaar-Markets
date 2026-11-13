"""Writes tests/reference/outcomes_v0160_all.json: every cell of outcomes_v0150_all.json regenerated at
engine 0.16.0, plus 0.16.0 cells for licensing (cheap, contract, owner liable; tourist shares 0.4 with locals
inspecting and 1.0; 6 days) and for counterfeit reopening (rule_deceptive reopen=counterfeit, the path the
0.17.0 price factor touches). Used by the 0.17.0 tests (tests/test_v0170.py), whose defaults must reproduce
these byte for byte. Run from the repo root at a commit with engine 0.16.0:
    PYTHONPATH=. python tests/reference/make_outcomes_v0160_all.py"""
import hashlib, json, os, subprocess
from engine import ENGINE_VERSION, bazaar
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from analysis.verification import overrides as vov

HERE = os.path.dirname(os.path.abspath(__file__))
V0150 = json.load(open(os.path.join(HERE, "outcomes_v0150_all.json")))["cells"]
CELLS = {k: (c["overrides"], c["seed"]) for k, c in V0150.items()}
LIC = {"cheap": ("cheap", "false", 2, 3), "contract": ("contract", "false", 3, 2), "liable": ("cheap", "true", 2, 3)}
for cond, tag in (("B|t40|l1", "t40"), ("B|t100", "t100")):
    for seed in (0, 1):
        base = [*vov(cond), "market.days=6", "inspectors.detect_scale=1.0"]
        eng = bazaar.BazaarEngine(load(overrides=[*base, f"seed={seed}"], mode="bazaar"))
        sid = next(st.sid for st in sorted(eng.stalls, key=lambda s: s.idx) if st.stype == "genuine")
        for name, (q, lia, n, b) in LIC.items():
            ov = [*base, "agents.seller.genuine=rule_genuine_bust_at", f"licensing.quality={q}",
                  "licensing.royalty=0.1", f"licensing.owner_liable={lia}",
                  f'licensing.schedule={{"{sid}":{{"day":{b},"n":{n}}}}}']
            CELLS[f"v0160_lic_{name}_{tag}|{seed}"] = (ov, seed)
        CELLS[f"v0160_cf_reopen_{tag}|{seed}"] = ([*base, "agents.params.rule_deceptive.reopen=counterfeit"], seed)


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
json.dump(out, open(os.path.join(HERE, "outcomes_v0160_all.json"), "w"), indent=1, sort_keys=True)
print(ENGINE_VERSION, out["commit"], len(out["cells"]))
