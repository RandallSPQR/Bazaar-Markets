"""Writes tests/reference/outcomes_v090.json. Run at commit 5641701 (engine 0.9.0) from the repo
root: PYTHONPATH=. python tests/reference/make_outcomes_v090.py. The 0.8.0 cells (brands cells now
in 0.9.0 words) plus 0.9.0 cells: budget override, rational v2, counterfeit reopening."""
import hashlib, json, os, subprocess
from engine import ENGINE_VERSION, bazaar
from engine.config import load
from engine.jsonlog import JsonlLog, dumps

HERE = os.path.dirname(os.path.abspath(__file__))
V080 = json.load(open(os.path.join(HERE, "outcomes_v080.json")))
CELLS = {}
for k, c in V080["cells"].items():
    CELLS.setdefault(k.split("|")[0], [x.replace("reopen=lookalike", "reopen=counterfeit") for x in c["overrides"]])
BR = ["brands.enabled=true", "brands.premium=0.4", "ratings.mode=public", "inspectors.placement=patrolling",
      "evolution.revise_prob=0", "evolution.mutation_prob=0", "market.horizon_known=true", "market.days=4",
      "market.ticks=160"]
CELLS.update({
    "v090_budget_override": ["buyers.budget_factor_override=1.1", "inspectors.count=2", "inspectors.placement=patrolling"],
    "v090_v2_counterfeit_125": [*BR, "agents.params.rule_deceptive.reopen=counterfeit",
                                "agents.seller.genuine=rule_genuine_rational_v2", "buyers.budget_factor_override=1.25",
                                "inspectors.count=4"],
    "v090_v2_fresh_tourist60": [*BR, "agents.params.rule_deceptive.reopen=fresh",
                                "agents.seller.genuine=rule_genuine_rational_v2", "buyers.budget_factor_override=1.5",
                                'buyers.profile_shares={"tourist":0.6,"local":0.2,"expert":0.2}'],
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
json.dump(out, open(os.path.join(HERE, "outcomes_v090.json"), "w"), indent=1, sort_keys=True)
print(ENGINE_VERSION, out["commit"], len(out["cells"]))
