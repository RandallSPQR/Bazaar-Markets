"""Writes tests/reference/outcomes_v0120.json. Run at commit 5ea5f24 (engine 0.12.0) from the repo
root: PYTHONPATH=. python tests/reference/make_outcomes_v0120.py. The 0.11.0 cells plus 0.12.0 cells:
choice-set demand (default m and gamma, position rent, m = 1, a brands chain with inspectors and
counterfeits in the style of the 2026-11-08 pilot)."""
import hashlib, json, os, subprocess
from engine import ENGINE_VERSION, bazaar
from engine.config import load
from engine.jsonlog import JsonlLog, dumps

HERE = os.path.dirname(os.path.abspath(__file__))
V0110 = json.load(open(os.path.join(HERE, "outcomes_v0110.json")))
CELLS = {}
for k, c in V0110["cells"].items():
    CELLS.setdefault(k.split("|")[0], c["overrides"])
CS = ["buyers.demand_mode=choice_set"]
BR = ["brands.enabled=true", "brands.premium=0.4", "ratings.mode=public", "inspectors.placement=patrolling",
      "evolution.revise_prob=0", "evolution.mutation_prob=0", "market.horizon_known=true", "market.days=4",
      "market.ticks=160", "buyers.budget_factor_override=1.25"]
CELLS.update({
    "v0120_choice_default": [*CS, "inspectors.count=2"],
    "v0120_choice_rent": [*CS, "buyers.consider=5", "buyers.position_rent=0.8", "inspectors.placement=posts"],
    "v0120_choice_m1": [*CS, "buyers.consider=1"],
    "v0120_choice_brands_cf": [*CS, *BR, "inspectors.count=2", "pricing.deceptive_price_factor=0.8",
                               "agents.params.rule_deceptive.reopen=counterfeit",
                               'buyers.profile_shares={"tourist":0.4,"local":0.3,"expert":0.3}'],
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
json.dump(out, open(os.path.join(HERE, "outcomes_v0120.json"), "w"), indent=1, sort_keys=True)
print(ENGINE_VERSION, out["commit"], len(out["cells"]))
