"""Run a configuration in either mode, optionally writing a JSONL log, and replay logs."""
from __future__ import annotations

import json
from contextlib import nullcontext

from . import bazaar, m0
from .config import from_dict, to_dict
from .jsonlog import JsonlLog, dumps
from .metrics import reference_configs, relative_outcomes


def run_config(cfg, log_path: str | None = None, normalize: bool = False, keep_lines: bool = False,
               agent_factory=None, allow_spend: bool = False, dry_run_cost: bool = False) -> tuple[dict, JsonlLog]:
    """allow_spend / dry_run_cost (1.2.0, bazaar mode): the run's LLM spend tracker (engine/budget.py); the result
    gains "spend" when either is set. Without allow_spend no LLM call can be made."""
    from . import budget as BUDGET
    ctx = open(log_path, "w", encoding="utf-8") if log_path else nullcontext(None)
    spend = BUDGET.session(cfg, allow_spend=allow_spend, dry_run=dry_run_cost) if cfg.mode == "bazaar" \
        else nullcontext(None)
    with ctx as sink, spend as tracker:
        log = JsonlLog(sink, keep=keep_lines)
        if cfg.mode == "m0":
            hist = m0.run(cfg, log=log)
            out = {"dec_share_imp_last": m0.summary(hist, cfg.summary_last), "last": cfg.summary_last,
                   "final_dec_pop": hist[-1]["dec_pop"], "final_fill": hist[-1]["fill"]}
        else:
            out = bazaar.run(cfg, log=log, agent_factory=agent_factory)
            if tracker is not None and (allow_spend or dry_run_cost):
                out = {**out, "spend": tracker.summary()}
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

    # Raw outputs per (day, agent); single-day logs are all day 1. Multi-day logs mark each
    # day with a day_start event, and every day has fresh agents.
    raws: dict[tuple, list] = {}
    attempts: dict[tuple, list] = {}
    errors: dict[tuple, list] = {}
    day = 1
    for e in events:
        if e["ev"] == "day_start":
            day = e["day"]
        elif e["ev"] == "raw":
            k = (day, e["agent"])
            raws.setdefault(k, []).append(e["raw"])
            errors.setdefault(k, []).append(e.get("agent_error"))
            if "attempts" in e:
                attempts.setdefault(k, []).append(e["attempts"])
    metas = head["agents"]

    def day_factory(d):
        def factory(role, policy, key, idx):
            k = (d, key)
            return ReplayAgent(raws.get(k, []), metas[f"{role}:{policy}"], attempts.get(k), errors.get(k))
        return factory

    if cfg.market.days > 1:
        bazaar.run(cfg, log=log, day_factories=day_factory)
    else:
        bazaar.run(cfg, log=log, agent_factory=day_factory(1))
    return lines, log


# Words renamed between engine versions: {log version: (old word, new word)}.
VOCAB_RENAMES = {"0.8.0": ("lookalike", "counterfeit")}


GUARD_KEYS = ("stuck_buyers", "idle_choosers")
LIABILITY_KEYS = ("liability",)     # 0.15.0 outcome key


def _before(v: str | None, ref: tuple) -> bool:
    try:
        return tuple(int(x) for x in str(v).split(".")) < ref
    except ValueError:
        return False


def _strip_guard(line: str, keys=GUARD_KEYS) -> str:
    if '"ev":"outcome"' not in line:
        return line
    e = json.loads(line)
    return dumps({k: v for k, v in e.items() if k not in keys})


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
    if version_differs and "config" in o0:
        # Config keys added since the log was written take their defaults (which reproduce the
        # old engine), so compare against the old config with those defaults filled in.
        o0["config"] = to_dict(from_dict(o0["config"]))
        # Likewise placeholder notes for settings added since (0.11.0: critics, capture) are not
        # in an older header: compare only the entries the old header has.
        if isinstance(o0.get("placeholders"), dict) and isinstance(n0.get("placeholders"), dict):
            n0["placeholders"] = {k: v for k, v in n0["placeholders"].items() if k in o0["placeholders"]}
    if v_old in VOCAB_RENAMES:
        # 0.8.0 called counterfeits "lookalike"; 0.9.0 accepts that name and logs "counterfeit".
        # Compare with the old name mapped to the new one on both sides (no brand name or other
        # logged text contains either word), re-serialised because renamed keys sort differently.
        a, b = VOCAB_RENAMES[v_old]
        old = [dumps(json.loads(x.replace(a, b))) if a in x else x for x in old]
        new = [dumps(json.loads(x.replace(a, b))) if a in x else x for x in new]
        o0, n0 = json.loads(json.dumps(o0).replace(a, b)), json.loads(json.dumps(n0).replace(a, b))
    if version_differs and _before(v_old, (0, 14, 0)):
        # 0.14.0 added the stuck-buyer guard (stuck_buyers, idle_choosers) to every outcome event;
        # an older log has no such keys, so compare without them (on both sides; a no-op on old lines).
        old = [_strip_guard(x) for x in old]
        new = [_strip_guard(x) for x in new]
    if version_differs and _before(v_old, (0, 15, 0)):
        # 0.15.0 added the outcome key "liability" (fines and enforcement intensity); likewise.
        old = [_strip_guard(x, LIABILITY_KEYS) for x in old]
        new = [_strip_guard(x, LIABILITY_KEYS) for x in new]

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
