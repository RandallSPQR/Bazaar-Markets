"""Writes tests/reference/outcomes_v070.json. Run at commit 856d6f5 (engine 0.7.0) from a clean
worktree: PYTHONPATH=<worktree> python make_outcomes_v070.py outcomes_v070.json"""
import hashlib, json, subprocess, sys
from engine import ENGINE_VERSION, bazaar
from engine.config import load
from engine.jsonlog import JsonlLog, dumps

CELLS = {
    "naive_posts2": ["inspectors.count=2", "inspectors.placement=posts"],
    "naive_patrol6": ["inspectors.count=6", "inspectors.placement=patrolling"],
    "adaptive_posts2_r1": ["inspectors.count=2", "inspectors.placement=posts", "inspectors.uniformed=true",
                           "inspectors.recognition_range=1.0", "agents.seller.deceptive=rule_deceptive_adaptive"],
    "adaptive_patrol2_r2": ["inspectors.count=2", "inspectors.placement=patrolling", "inspectors.uniformed=true",
                            "inspectors.recognition_range=2.0", "agents.seller.deceptive=rule_deceptive_adaptive"],
    "adaptive_disguised_fs2": ["inspectors.count=2", "inspectors.placement=disguised",
                               "inspectors.disguised_shift=full_shift", "agents.seller.deceptive=rule_deceptive_adaptive"],
    "disguised_single6": ["inspectors.count=6", "inspectors.placement=disguised"],
    "clustered_hazard": ["inspectors.count=4", "inspectors.placement=clustered", "detection.form=hazard"],
    "inspector_buyers_mixed": ["inspectors.count=0", "buyers.inspector_fraction=0.2", "buyers.budget_level=mixed"],
    "whisper3": ["inspectors.count=2", "inspectors.placement=patrolling", "market.whisper_range=3.0",
                 "agents.seller.deceptive=rule_deceptive_adaptive", "inspectors.uniformed=true"],
    "k2_adaptive_patrol2_r1": ["market.scale=2", "inspectors.count=2", "inspectors.placement=patrolling",
                               "inspectors.uniformed=true", "inspectors.recognition_range=1.0",
                               "agents.seller.deceptive=rule_deceptive_adaptive"],
    "k2_disguised_fs2": ["market.scale=2", "inspectors.count=2", "inspectors.placement=disguised",
                         "inspectors.disguised_shift=full_shift"],
    "days3_posts_mut": ["market.days=3", "market.ticks=120", "evolution.mutation_prob=0.3"],
    "days3_adaptive_patrol": ["market.days=3", "market.ticks=120", "inspectors.placement=patrolling",
                              "inspectors.uniformed=true", "inspectors.recognition_range=0",
                              "agents.seller.deceptive=rule_deceptive_adaptive"],
    "days3_control_nowhisper_ok": ["market.days=3", "market.ticks=120", "inspectors.count=0"],
    # 0.7.0 features
    "days3_public_ratings": ["market.days=3", "market.ticks=120", "ratings.mode=public", "inspectors.count=0"],
    "days3_hidden_mut_cost": ["market.days=3", "market.ticks=120", "ratings.mode=hidden", "evolution.mutation_prob=0.3",
                              "pricing.switch_cost_to_genuine=0.5", "pricing.switch_cost_to_deceptive=0.25"],
    "days3_nowhisper_public": ["market.days=3", "market.ticks=120", "ratings.mode=public", "market.whispers_allowed=false"],
    "days3_public_patrol_tourist": ["market.days=3", "market.ticks=160", "ratings.mode=public", "inspectors.placement=patrolling",
                                    'buyers.profile_shares={"tourist":0.4,"local":0.3,"expert":0.3}'],
}
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
json.dump(out, open(sys.argv[1], "w"), indent=1, sort_keys=True)
print(ENGINE_VERSION, len(out["cells"]))
