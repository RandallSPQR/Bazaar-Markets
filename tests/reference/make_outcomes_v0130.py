"""Writes tests/reference/outcomes_v0130.json. Run at commit 56f0574 (engine 0.13.0) from the repo
root: PYTHONPATH=. python tests/reference/make_outcomes_v0130.py. The 0.12.0 cells plus 0.13.0 cells
for the trapped-buyer fix (engine 0.14.0): verification-run conditions with and without inspectors
(choice-set demand, a few days), a walk-mode search market with inspectors, and a single-day
choice-set market with inspectors at posts. Each cell records whether any stall was closed (a catch)."""
import hashlib, json, os, subprocess
from engine import ENGINE_VERSION, bazaar
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from analysis.verification import overrides as vov

HERE = os.path.dirname(os.path.abspath(__file__))
V0120 = json.load(open(os.path.join(HERE, "outcomes_v0120.json")))
CELLS = {}
for k, c in V0120["cells"].items():
    CELLS.setdefault(k.split("|")[0], c["overrides"])
BR = ["brands.enabled=true", "brands.premium=0.4", "ratings.mode=public", "inspectors.placement=patrolling",
      "evolution.revise_prob=0", "evolution.mutation_prob=0", "market.horizon_known=true",
      "buyers.budget_factor_override=1.25", "agents.params.rule_deceptive.reopen=fresh"]
CELLS.update({
    "v0130_verif_A_t40": [*vov("A|t40|l1"), "market.days=3"],
    "v0130_verif_B_t40": [*vov("B|t40|l1"), "market.days=3"],
    "v0130_verif_B_t100": [*vov("B|t100"), "market.days=2"],
    "v0130_walk_search_insp": [*BR, "inspectors.count=2", "market.days=3",
                               'buyers.search_depth={"tourist":3,"local":3,"expert":3}'],
    "v0130_choice_posts_1day": ["buyers.demand_mode=choice_set", "inspectors.count=2", "inspectors.placement=posts"],
})


def catches(o):
    return sum(d["outcome"]["catches"] for d in o["days"]) if "days" in o else o["catches"]


out = {"engine_version": ENGINE_VERSION,
       "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip(),
       "cells": {}}
for name, ov in CELLS.items():
    for seed in (0, 1):
        log = JsonlLog(keep=True)
        o = bazaar.run(load(overrides=[*ov, f"seed={seed}"], mode="bazaar"), log=log)
        body = hashlib.sha256("\n".join(log.lines[1:]).encode()).hexdigest()
        out["cells"][f"{name}|{seed}"] = {"overrides": ov, "seed": seed, "outcome": dumps(o),
                                          "log_body_sha256": body, "log_lines": len(log.lines),
                                          "catches": catches(o)}
json.dump(out, open(os.path.join(HERE, "outcomes_v0130.json"), "w"), indent=1, sort_keys=True)
print(ENGINE_VERSION, out["commit"], len(out["cells"]))
