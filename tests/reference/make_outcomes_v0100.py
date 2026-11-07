"""Writes tests/reference/outcomes_v0100.json. Run at commit e5d7818 (engine 0.10.0) from the repo
root: PYTHONPATH=. python tests/reference/make_outcomes_v0100.py. The 0.9.0 cells plus 0.10.0 cells:
search depth (with and without the search log), tourists at depth 1 with others searching, and a
brands chain in the style of the 2026-11-07 capture run (no inspectors, slow ratings, many tourists)."""
import hashlib, json, os, subprocess
from engine import ENGINE_VERSION, bazaar
from engine.config import load
from engine.jsonlog import JsonlLog, dumps

HERE = os.path.dirname(os.path.abspath(__file__))
V090 = json.load(open(os.path.join(HERE, "outcomes_v090.json")))
CELLS = {}
for k, c in V090["cells"].items():
    CELLS.setdefault(k.split("|")[0], c["overrides"])
BR = ["brands.enabled=true", "brands.premium=0.4", "ratings.mode=public", "inspectors.placement=patrolling",
      "evolution.revise_prob=0", "evolution.mutation_prob=0", "market.horizon_known=true", "market.days=4",
      "market.ticks=160", "buyers.budget_factor_override=1.25"]
D = lambda t, k: f'buyers.search_depth={{"tourist":{t},"local":{k},"expert":{k}}}'
CELLS.update({
    "v0100_depth2": [D(2, 2), "inspectors.count=2", "inspectors.placement=patrolling"],
    "v0100_depth4_log": [D(4, 4), "buyers.search_log=true", "inspectors.placement=posts"],
    "v0100_t1_others3_brands": [*BR, D(1, 3), "agents.params.rule_deceptive.reopen=counterfeit",
                                "agents.seller.genuine=rule_genuine_rational_v2"],
    "v0100_capture_style": [*BR, D(2, 2), "inspectors.count=0", "ratings.memory=0.9",
                            'buyers.profile_shares={"tourist":0.8,"local":0.1,"expert":0.1}',
                            "agents.params.rule_deceptive.reopen=fresh"],
})
out = {"engine_version": ENGINE_VERSION,
       "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip(),
       "cells": {}}
for name, ov in CELLS.items():
    for seed in (0, 1):
        log = JsonlLog(keep=True)
        o = bazaar.run(load(overrides=[*ov, f"seed={seed}"], mode="bazaar"), log=log)
        body = hashlib.sha256("\n".join(log.lines[1:]).encode()).hexdigest()
        out["cells"][f"{name}|{seed}"] = {"overrides": ov, "seed": seed, "outcome": dumps(o),
                                          "log_body_sha256": body, "log_lines": len(log.lines)}
json.dump(out, open(os.path.join(HERE, "outcomes_v0100.json"), "w"), indent=1, sort_keys=True)
print(ENGINE_VERSION, out["commit"], len(out["cells"]))
