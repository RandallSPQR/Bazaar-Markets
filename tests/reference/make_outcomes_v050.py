"""Writes tests/reference/outcomes_v050.json. Run at commit 43964e6 (engine 0.5.0) from a clean
worktree: PYTHONPATH=<worktree> python make_outcomes_v050.py outcomes_v050.json"""
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
