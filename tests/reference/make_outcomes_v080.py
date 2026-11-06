"""Writes tests/reference/outcomes_v080.json and log_v080_brands.jsonl.gz. Run at commit dc548e5
(engine 0.8.0) from the repo root: python -m tests.reference.make_outcomes_v080 (or with
PYTHONPATH=<worktree>). The 0.7.0 cells plus brands cells (look-alike, fresh, rational, budget
above). Brands cells are compared in 0.9.0 after mapping "counterfeit" back to "lookalike"."""
import hashlib, json, os, subprocess, sys
from engine import ENGINE_VERSION, bazaar
from engine.config import load
from engine.jsonlog import JsonlLog, dumps

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
V070 = json.load(open(os.path.join(HERE, "outcomes_v070.json")))
CELLS = {}
for k, c in V070["cells"].items():
    CELLS.setdefault(k.split("|")[0], c["overrides"])
BR = ["brands.enabled=true", "brands.premium=0.4", "ratings.mode=public", "inspectors.placement=patrolling",
      "evolution.revise_prob=0", "evolution.mutation_prob=0", "market.horizon_known=true", "market.days=4",
      "market.ticks=160"]
CELLS.update({
    "brands_lookalike": [*BR, "agents.params.rule_deceptive.reopen=lookalike"],
    "brands_fresh_rational": [*BR, "agents.params.rule_deceptive.reopen=fresh",
                              "agents.seller.genuine=rule_genuine_rational"],
    "brands_lookalike_rational_above": [*BR, "agents.params.rule_deceptive.reopen=lookalike",
                                        "agents.seller.genuine=rule_genuine_rational", "buyers.budget_level=above",
                                        'buyers.profile_shares={"tourist":0.6,"local":0.2,"expert":0.2}'],
    "brands_keep_premium0": [*BR, "brands.premium=0"],
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
json.dump(out, open(os.path.join(HERE, "outcomes_v080.json"), "w"), indent=1, sort_keys=True)
# one full brands log (gzipped), for the replay test
import gzip
ov = [*BR[:-2], "market.days=2", "market.ticks=70", "buyers.count=40",
      "agents.params.rule_deceptive.reopen=lookalike", "agents.seller.genuine=rule_genuine_rational",
      "inspectors.count=6", "seed=3"]
log = JsonlLog(keep=True)
bazaar.run(load(overrides=ov, mode="bazaar"), log=log)
with gzip.open(os.path.join(HERE, "log_v080_brands.jsonl.gz"), "wt", encoding="utf-8") as f:
    f.write("\n".join(log.lines) + "\n")
print(ENGINE_VERSION, len(out["cells"]))
