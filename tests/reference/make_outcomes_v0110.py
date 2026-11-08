"""Writes tests/reference/outcomes_v0110.json. Run at commit 66d917d (engine 0.11.0; the engine is
unchanged since 690f58c) from the repo root: PYTHONPATH=. python tests/reference/make_outcomes_v0110.py.
The 0.10.0 cells plus 0.11.0 cells: critics with ties and embarrassment, inspector capture, bargain
hunters, the scheduled bust-out policy, and a chain in the style of the 2026-11-07 capture run."""
import hashlib, json, os, subprocess
from engine import ENGINE_VERSION, bazaar
from engine.config import load
from engine.jsonlog import JsonlLog, dumps

HERE = os.path.dirname(os.path.abspath(__file__))
V0100 = json.load(open(os.path.join(HERE, "outcomes_v0100.json")))
CELLS = {}
for k, c in V0100["cells"].items():
    CELLS.setdefault(k.split("|")[0], c["overrides"])
BR = ["brands.enabled=true", "brands.premium=0.4", "ratings.mode=public", "inspectors.placement=patrolling",
      "evolution.revise_prob=0", "evolution.mutation_prob=0", "market.horizon_known=true", "market.days=4",
      "market.ticks=160", "buyers.budget_factor_override=1.25", "agents.params.rule_deceptive.reopen=fresh"]
D2 = 'buyers.search_depth={"tourist":2,"local":2,"expert":2}'
CELLS.update({
    "v0110_critics_ties_emb": [*BR, D2, "inspectors.count=2", "critics.count=4", "critics.sample=6",
                               "critics.tie_share=0.6", "critics.tie_delay=2", "critics.embarrassment=true",
                               "critics.emb_max=3"],
    "v0110_capture": [*BR, D2, "inspectors.count=2", "inspectors.capture=0.5", "inspectors.capture_effect=0.8",
                      "critics.count=2"],
    "v0110_bargain": [*BR, D2, "buyers.bargain_share=0.2"],
    "v0110_bargain_walk_depth1": ["buyers.bargain_share=0.3", "inspectors.count=2"],
    "v0110_bust_at": [*BR, D2, "agents.seller.genuine=rule_genuine_bust_at",
                      'agents.params.rule_genuine_bust_at.schedule={"s08":2,"s32":3}'],
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
json.dump(out, open(os.path.join(HERE, "outcomes_v0110.json"), "w"), indent=1, sort_keys=True)
print(ENGINE_VERSION, out["commit"], len(out["cells"]))
