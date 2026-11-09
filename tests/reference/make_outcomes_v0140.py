"""Writes tests/reference/outcomes_v0140.json: the reference cells of outcomes_v0130.json that engine
0.14.0 changes on purpose, regenerated at 0.14.0. Run from the repo root at the 0.14.0 engine commit:
PYTHONPATH=. python tests/reference/make_outcomes_v0140.py. A cell is regenerated only if its 0.14.0
run differs from 0.13.0 (guard keys removed); each records why: "trapped" (choice-set demand with
closures: fix 1) or "parked" (a walk-mode search buyer rejected its chosen stall on arrival: fix 2)."""
import hashlib, json, os, subprocess
from engine import ENGINE_VERSION, bazaar
from engine.bazaar import BazaarEngine, _dist
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from tests.guard_strip import strip_lines, strip_out

HERE = os.path.dirname(os.path.abspath(__file__))
V0130 = json.load(open(os.path.join(HERE, "outcomes_v0130.json")))["cells"]
out = {"engine_version": ENGINE_VERSION,
       "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
                 + ("+0.14.0 working tree" if subprocess.run(["git", "diff", "--quiet", "engine"]).returncode else ""),
       "cells": {}}
for key, c in sorted(V0130.items()):
    log = JsonlLog(keep=True)
    o = bazaar.run(load(overrides=[*c["overrides"], f"seed={c['seed']}"], mode="bazaar"), log=log)
    body = hashlib.sha256("\n".join(log.lines[1:]).encode()).hexdigest()
    old_body = hashlib.sha256("\n".join(strip_lines(log.lines[1:])).encode()).hexdigest()
    if dumps(strip_out(o)) == c["outcome"] and len(log.lines) == c["log_lines"] and old_body == c["log_body_sha256"]:
        continue
    why = "trapped" if ("buyers.demand_mode=choice_set" in c["overrides"] and c["catches"] > 0) else "parked"
    out["cells"][key] = {"overrides": c["overrides"], "seed": c["seed"], "outcome": dumps(o), "why": why,
                         "log_body_sha256": body, "log_lines": len(log.lines)}
json.dump(out, open(os.path.join(HERE, "outcomes_v0140.json"), "w"), indent=1, sort_keys=True)
print(ENGINE_VERSION, out["commit"], len(out["cells"]), sorted((k, v["why"]) for k, v in out["cells"].items()))
