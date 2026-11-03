"""Run a configuration in either mode, optionally writing a JSONL log, and replay logs."""
from __future__ import annotations

import json
from contextlib import nullcontext

from . import bazaar, m0
from .config import from_dict
from .jsonlog import JsonlLog
from .metrics import reference_configs, relative_outcomes


def run_config(cfg, log_path: str | None = None, normalize: bool = False, keep_lines: bool = False,
               agent_factory=None) -> tuple[dict, JsonlLog]:
    ctx = open(log_path, "w", encoding="utf-8") if log_path else nullcontext(None)
    with ctx as sink:
        log = JsonlLog(sink, keep=keep_lines)
        if cfg.mode == "m0":
            hist = m0.run(cfg, log=log)
            out = {"dec_share_imp_last": m0.summary(hist, cfg.summary_last), "last": cfg.summary_last,
                   "final_dec_pop": hist[-1]["dec_pop"], "final_fill": hist[-1]["fill"]}
        else:
            out = bazaar.run(cfg, log=log, agent_factory=agent_factory)
    if normalize and cfg.mode == "bazaar":
        refs = {k: bazaar.run(c) for k, c in reference_configs(cfg).items()}
        out = {**out, **relative_outcomes(out, refs["random_ref"], refs["informed_ref"])}
    return out, log


def replay(lines: list[str]) -> tuple[list[str], JsonlLog]:
    """Re-run the engine from a log's header config, feeding back the logged raw
    agent outputs. Returns (original lines, new log)."""
    events = [json.loads(x) for x in lines]
    head = events[0]
    if head.get("ev") != "header":
        raise ValueError("first log line is not a header")
    cfg = from_dict(head["config"])
    log = JsonlLog(keep=True)
    if cfg.mode == "m0":
        m0.run(cfg, log=log)
        return lines, log

    from agents.registry import ReplayAgent

    raws: dict[str, list] = {}
    attempts: dict[str, list] = {}
    errors: dict[str, list] = {}
    for e in events:
        if e["ev"] == "raw":
            raws.setdefault(e["agent"], []).append(e["raw"])
            errors.setdefault(e["agent"], []).append(e.get("agent_error"))
            if "attempts" in e:
                attempts.setdefault(e["agent"], []).append(e["attempts"])
    metas = head["agents"]

    def factory(role, policy, key, idx):
        return ReplayAgent(raws.get(key, []), metas[f"{role}:{policy}"], attempts.get(key), errors.get(key))

    bazaar.run(cfg, log=log, agent_factory=factory)
    return lines, log


def compare_logs(old: list[str], new: list[str]) -> dict:
    """Byte comparison, line by line. The header's `env` and `engine_version` are
    compared separately: a difference there is a warning, not a mismatch, and the
    rest of the log decides. When a log from another engine version does not
    replay, the result says so, since that is the likely cause."""
    warnings = []
    o0, n0 = json.loads(old[0]), json.loads(new[0])
    if o0.get("env") != n0.get("env"):
        warnings.append(f"environment differs: logged {o0.get('env')} vs now {n0.get('env')}")
    v_old, v_new = o0.get("engine_version"), n0.get("engine_version")
    version_differs = v_old != v_new
    if version_differs:
        warnings.append(f"log written by engine {v_old}; this is engine {v_new}")
    for h in (o0, n0):
        h.pop("env", None); h.pop("engine_version", None)

    def mismatch(**kw) -> dict:
        res = {"identical": False, "warnings": warnings, **kw}
        if version_differs:
            res["likely_cause"] = (f"the log was written by engine {v_old}, this is {v_new}; "
                                   f"replay it with engine {v_old} or regenerate it")
        return res

    if o0 != n0:
        return mismatch(first_diff_line=1, old=old[0][:300], new=new[0][:300])
    for i, (a, b) in enumerate(zip(old[1:], new[1:]), start=2):
        if a != b:
            return mismatch(first_diff_line=i, old=a[:300], new=b[:300])
    if len(old) != len(new):
        return mismatch(first_diff_line=min(len(old), len(new)) + 1, old_lines=len(old), new_lines=len(new))
    return {"identical": True, "lines": len(old), "warnings": warnings}
