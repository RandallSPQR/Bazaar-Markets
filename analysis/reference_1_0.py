"""Engine 1.0.0: the reference config, its named variants, and the v1_0_0 regression digests (plan Stage 2, steps 2-3).

Reference config (`configs/reference_1_0.json`). The licensing market at its headline cell (tourist share 0.4,
locals inspect, detect_scale 1): choice-set demand (m 3, position rent gamma 0), 150 buyers, budget 1.25 x base,
bargain hunters 0.2, public ratings with memory 0.7 shown as stars at step 0.02, random tie-break, brands on with
premium 0.4, 2 patrolling inspectors not uniformed, detect_scale 1, collectible fines (penalty lag 0), 30 days, rule
sellers (deceptive: fresh name at reopening; genuine: honest). The file is the full config, written by `--write`;
`python -m cli.run --config configs/reference_1_0.json` runs it. The file is JSON, which the engine's loader reads, so
no YAML dependency is added to the frozen engine (the plan named a .yaml file; deviation D5).

Variants (`configs/reference_1_0_variants.json`). One per published run from verification on (12 runs). A variant
holds `overrides` (from the reference to the run's market at its first cell) and `cells` (from there to each other
market the run built), all as dotted key=value overrides, so that

    load("configs/reference_1_0.json", [*variant["overrides"], *variant["cells"][cell], f"seed={seed}"])

is the config the run's own builder made for that cell and seed. They are derived from the configs each run's own
builder makes (every chain of 2 seeds, captured before its engine runs) and are checked: every captured config must
be rebuilt from the reference exactly (canonical JSON, so 1 and 1.0 differ). Chain-level settings that the scripts
apply after loading (benchmark.bust_config, benchmark.licence_config: bust-out schedules, licensing schedules) stay
with the chain, as in the run scripts.

Regression (`tests/reference/v1_0_0/digests.json`). For every published run since engine 0.14.0 (all of the above;
verification Stage A ran at 0.13.0 with no catches, so the 0.14.0 fixes cannot reach it), the first 2 seeds of the
main run, and for each seed the first chain (in the run's own job order) of every kind x market cell: never and
bust-out chains of every condition, licence chains, every brand-equity arm and level, check-vs-read's A, B and D
chains. Each chain is rerun at the current engine with every config built from the reference file and its variant
(the run modules' `load` is replaced for the rerun), compared field by field with the saved cache record (all
fields, except timing `secs` and the `engine_version` stamp), and stored as the sha256 of its canonical record.

    .venv/bin/python -m analysis.reference_1_0 --write            # reference file and variants (fast)
    .venv/bin/python -m analysis.reference_1_0 --generate         # rerun, compare with the saved caches, write digests
    .venv/bin/python -m analysis.reference_1_0 --check [--quick]  # rerun and compare with the digests
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import engine.config as EC
from engine import ENGINE_VERSION
from engine import bazaar as EB

REF_PATH = "configs/reference_1_0.json"
VAR_PATH = "configs/reference_1_0_variants.json"
DIG_PATH = "tests/reference/v1_0_0/digests.json"
EXCLUDE = ("secs", "engine_version")
ORIG_LOAD = EC.load

REF_OV = ["buyers.demand_mode=choice_set", "buyers.consider=3", "buyers.position_rent=0", "buyers.count=150",
          "buyers.budget_factor_override=1.25", "buyers.bargain_share=0.2", "buyers.bargain_q_req=[0.15,0.40]",
          'buyers.profile_shares={"tourist":0.4,"local":0.3,"expert":0.3}',
          "agents.params.rule_buyer.local_inspect_prob=1.0",
          "ratings.mode=public", "ratings.memory=0.7", "ratings.display=stars", "ratings.display_step=0.02",
          "buyers.tie_break=random", "brands.enabled=true", "brands.premium=0.4",
          "inspectors.count=2", "inspectors.placement=patrolling", "inspectors.uniformed=false",
          "inspectors.detect_scale=1.0", "pricing.penalty_lag_days=0",
          "market.horizon_known=true", "market.days=30", "evolution.revise_prob=0", "evolution.mutation_prob=0",
          "agents.seller.deceptive=rule_deceptive", "agents.params.rule_deceptive.reopen=fresh",
          "agents.seller.genuine=rule_honest"]


def canon(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def reference_dict() -> dict:
    return EC.to_dict(ORIG_LOAD(None, REF_OV, mode="bazaar"))


def _noseed(d: dict) -> dict:
    d = dict(d)
    d.pop("seed", None)
    return d


# ------------------------------------------------------------------ studies

def _samples(mod, seeds):
    return {sd: mod.sample_stalls(sd) for sd in seeds}


def _saved_index(path: str, want=None) -> dict:
    out = {}
    rx = re.compile(r'^\{"key":"([^"]*)"')
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = rx.match(line)
            k = m.group(1) if m else json.loads(line)["key"]
            if want is None or want(k):
                out[k] = line
    return out


def studies() -> dict:
    """name -> {summary, engine, script, seeds, specs(), job, key, kind, cache(spec)}. Specs in the run's own order."""
    import analysis.brand_equity as BE
    import analysis.brand_equity_speed as S
    import analysis.brand_equity_stars as BES
    import analysis.brand_equity_tier as T
    import analysis.bustout_decomp as BD
    import analysis.canal_street as CS
    import analysis.check_vs_read as CVR
    import analysis.liability as LB
    import analysis.licensing as L
    import analysis.licensing_checks as LC
    import analysis.stars_sensitivity as SS
    import analysis.verification as V
    NEVER = V.NEVER

    def nv(b):
        return "never" if b == NEVER else "candidate"

    def ver_specs(seeds):
        sm = _samples(V, seeds)
        return [*V.jobs_for(V.CONDS["A"], seeds, sm), *V.jobs_for(V.CONDS["B"], seeds, sm)]

    def bust_specs(seeds):
        return [j for j in BD.jobs(BD.best_table()) if j[1] in seeds]

    def lc_specs(seeds):
        return [j for j in LC.jobs() if j[2] in seeds]

    def ss_specs(seeds_unused):
        out = []
        for st in ("verification", "liability", "bustout", "canal", "licensing"):
            sd = SS.ORIG_SEEDS[st][:2]
            best = SS.bust_best_saved() if st == "bustout" else None
            out += [(st, "stars", x) for x in SS.specs(st, sd, _samples(V, sd), "saved", best)]
        return out

    def cvr_specs(seeds):
        sm = _samples(L, seeds)
        main = CVR.jobs_main(seeds, sm)
        idx = _saved_index("runs/check_vs_read_cache.jsonl", lambda k: k.startswith("A|"))
        runs = [json.loads(v) for v in idx.values()]
        runs = [r for r in runs if r["seed"] in seeds]
        return [*main, *CVR.jobs_decomp(CVR.gains_by(runs, seeds, sm), seeds, sm)]

    def ss_kind(j):
        st, _, x = j
        b = {"verification": lambda: x[5], "liability": lambda: x[4], "bustout": lambda: x[4]}.get(st)
        return f"{st}:{nv(b()) if b else x[0] if st == 'licensing' else 'chain'}"

    return {
        "verification": dict(summary="runs/verification_summary.md", engine="0.13.0 (stage A), 0.14.0 (stage B)",
                             script="analysis/verification.py", seeds=[200, 201], specs=ver_specs, job=V._job,
                             key=V._key, kind=lambda j: nv(j[5]),
                             cache=lambda j: f"runs/verification_cache_{j[0]}.jsonl"),
        "liability": dict(summary="runs/liability_summary.md", engine="0.15.0", script="analysis/liability.py",
                          seeds=[230, 231],
                          specs=lambda sd: LB.jobs_for(LB.conds([0.0, 0.1, 1.0]), sd, _samples(LB, sd)),
                          job=LB._job, key=LB._key, kind=lambda j: nv(j[4]), cache=lambda j: "runs/liability_cache.jsonl"),
        "bustout_decomposition": dict(summary="runs/bustout_decomposition.md", engine="0.15.0",
                                      script="analysis/bustout_decomp.py", seeds=[230, 231], specs=bust_specs,
                                      job=BD._job, key=BD._key, kind=lambda j: nv(j[4]), cache=lambda j: BD.CACHE),
        "licensing": dict(summary="runs/licensing_summary.md", engine="0.16.0", script="analysis/licensing.py",
                          seeds=[250, 251], specs=lambda sd: L.jobs_for(L.LIC_CONDS, L.BASES, sd, _samples(L, sd)),
                          job=L._job, key=L._key, kind=lambda j: j[0],
                          cache=lambda j: "runs/licensing_cache.jsonl"),
        "licensing_checks": dict(summary="runs/licensing_checks.md", engine="0.16.0",
                                 script="analysis/licensing_checks.py", seeds=[250, 251], specs=lc_specs, job=LC._job,
                                 key=LC._key, kind=lambda j: j[0], cache=lambda j: LC.CACHE),
        "canal_street": dict(summary="runs/canal_street_summary.md", engine="0.17.0",
                             script="analysis/canal_street.py", seeds=[270, 271], specs=CS.jobs_for, job=CS.job,
                             key=CS.key, kind=lambda j: "chain", cache=lambda j: "runs/canal_street_cache.jsonl"),
        "brand_equity": dict(summary="runs/brand_equity_summary.md", engine="0.17.0",
                             script="analysis/brand_equity.py", seeds=[300, 301],
                             specs=lambda sd: BE.jobs_for(sd, _samples(L, sd)), job=BE.job, key=BE.key,
                             kind=lambda j: j[0], cache=lambda j: "runs/brand_equity_cache.jsonl"),
        "brand_equity_tier": dict(summary="runs/brand_equity_tier_summary.md", engine="0.18.0",
                                  script="analysis/brand_equity_tier.py", seeds=[300, 301],
                                  specs=lambda sd: T.jobs_for(sd, _samples(L, sd), T.LEVELS), job=T.job, key=T.key,
                                  kind=lambda j: j[0], cache=lambda j: "runs/brand_equity_tier_cache.jsonl"),
        "brand_equity_speed": dict(summary="runs/brand_equity_speed_summary.md", engine="0.19.0",
                                   script="analysis/brand_equity_speed.py", seeds=[330, 331],
                                   specs=lambda sd: S.jobs_for(sd, _samples(L, sd), S.LEVELS), job=S.job, key=S.key,
                                   kind=lambda j: j[0], cache=lambda j: "runs/brand_equity_speed_cache.jsonl"),
        "stars_sensitivity": dict(summary="runs/stars_sensitivity_summary.md", engine="0.20.0",
                                  script="analysis/stars_sensitivity.py", seeds=[], specs=ss_specs, job=SS.job,
                                  key=SS.key, kind=ss_kind, cache=lambda j: "runs/stars_sensitivity_cache.jsonl"),
        "brand_equity_stars": dict(summary="runs/brand_equity_stars_summary.md", engine="0.20.0",
                                   script="analysis/brand_equity_stars.py", seeds=[330, 331],
                                   specs=lambda sd: BES.jobs_for(sd, _samples(L, sd), True), job=BES.job,
                                   key=BES.key, kind=lambda j: j[0],
                                   cache=lambda j: "runs/brand_equity_stars_cache.jsonl"),
        "check_vs_read": dict(summary="runs/check_vs_read_summary.md", engine="0.21.0",
                              script="analysis/check_vs_read.py", seeds=[350, 351], specs=cvr_specs, job=CVR.job,
                              key=CVR.key, kind=lambda j: f"B:{j[4]}" if j[0] == "B" else f"{j[0]}:{nv(j[-1])}",
                              cache=lambda j: "runs/check_vs_read_cache.jsonl"),
    }


# ------------------------------------------------------------------ load replacement

class _Stop(Exception):
    pass


_MODS: list = []


def _install(load_fn) -> None:
    """Replace `load` in every run module that imported engine.config.load (found once, then remembered)."""
    if not _MODS:
        _MODS.extend(m for n, m in sorted(sys.modules.items())
                     if n.startswith("analysis.") and getattr(m, "load", None) is ORIG_LOAD)
    for m in _MODS:
        m.load = load_fn


def capture(study: dict, spec) -> list[dict]:
    """The configs the chain's own builder loads before its first engine run (the run is stopped there)."""
    seen = []

    def rec_load(path=None, overrides=None, mode=None):
        c = ORIG_LOAD(path, overrides, mode=mode)
        seen.append(EC.to_dict(c))
        return c

    orig_run = EB.run

    def stop(*a, **k):
        raise _Stop

    _install(rec_load)
    EB.run = stop
    try:
        study["job"](spec)
    except _Stop:
        pass
    finally:
        EB.run = orig_run
        _install(ORIG_LOAD)
    return seen


# ------------------------------------------------------------------ variants

def diff_overrides(src: dict, dst: dict, prefix="") -> list[str]:
    """Dotted key=value overrides that turn src into dst under engine.config.load (merge rules included)."""
    out = []
    for k in sorted(set(src) | set(dst)):
        p = f"{prefix}{k}"
        if k not in dst:
            raise ValueError(f"{p} is in the source config but not the target: not expressible as an override")
        a, b = src.get(k, None), dst[k]
        if k in src and canon(a) == canon(b):
            continue
        if isinstance(b, dict) and isinstance(a, dict) and k not in EC._OPAQUE_DICTS:
            out += diff_overrides(a, b, p + ".")
        else:
            out.append(f"{p}={json.dumps(b, separators=(',', ':'))}")
    return out


def build(variant: dict, cell: str, seed: int):
    return ORIG_LOAD(REF_PATH, [*variant["overrides"], *variant["cells"][cell], f"seed={seed}"], mode="bazaar")


def derive(log=print) -> tuple[dict, dict]:
    """Variants and the regression selection: {study: variant}, {study: [(spec, cell, seed)]}."""
    import analysis.verification as V
    ref = reference_dict()
    S = studies()
    variants, select = {}, {}
    sampler = _noseed(EC.to_dict(V.config("A|t40|l1", 0)))
    for name, st in S.items():
        t0 = time.time()
        specs = st["specs"](st["seeds"])
        cells: dict = {}            # canon(no-seed config) -> label
        dicts: dict = {}
        firsts: dict = {}           # (kind, cell label, seed) -> spec
        for j in specs:
            seen = capture(st, j)
            if not seen:
                raise RuntimeError(f"{name}: no config captured for {st['key'](j)}")
            for d in seen:
                cd = canon(_noseed(d))
                if cd not in cells:
                    lab = re.sub(r"\|?\b(" + str(d["seed"]) + r")\b", "", st["key"](j)) if d is seen[0] else "sampler"
                    lab = lab if lab not in cells.values() else f"{lab}#{len(cells)}"
                    cells[cd], dicts[cd] = lab, _noseed(d)
            c0 = canon(_noseed(seen[0]))
            firsts.setdefault((st["kind"](j), cells[c0], seen[0]["seed"]), j)
        if canon(sampler) not in cells:
            cells[canon(sampler)], dicts[canon(sampler)] = "sampler", sampler
        # every cell as overrides from the reference; the overrides all cells share become the variant's own
        per = {lab: diff_overrides(_noseed(ref), dicts[cd]) for cd, lab in cells.items()}
        common = [o for o in next(iter(per.values())) if all(o in v for v in per.values())]
        var = {"run": st["summary"], "script": st["script"], "engine": st["engine"], "overrides": common,
               "cells": {lab: [o for o in v if o not in common] for lab, v in per.items()}}
        for cd, lab in cells.items():
            got = canon(_noseed(EC.to_dict(build(var, lab, 0))))
            if got != cd:
                raise RuntimeError(f"{name} {lab}: the variant does not rebuild the run's config from the reference")
        var["cell_sha256"] = {lab: hashlib.sha256(cd.encode()).hexdigest() for cd, lab in cells.items()}
        variants[name] = var
        select[name] = [(j, lab, sd) for (k, lab, sd), j in firsts.items()]
        log(f"{name}: {len(specs)} chains captured, {len(cells)} market cells, {len(select[name])} selected "
            f"({time.time() - t0:.0f} s)")
    return variants, select


# ------------------------------------------------------------------ rerun from the reference

_INDEX: dict = {}          # study -> {canonical no-seed config: cell}


def _ref_load_factory(variants: dict, study: str):
    """`load` for a rerun of `study`: the config its script asks for, rebuilt from the reference file and the study's
    own variant (another variant's identical cell only if its own has none)."""
    if not _INDEX:
        for name, var in variants.items():
            _INDEX[name] = {canon(_noseed(EC.to_dict(build(var, lab, 0)))): lab for lab in var["cells"]}

    def ref_load(path=None, overrides=None, mode=None):
        c0 = ORIG_LOAD(path, overrides, mode=mode)
        d0 = EC.to_dict(c0)
        cd = canon(_noseed(d0))
        hit = next(((n, _INDEX[n][cd]) for n in [study, *_INDEX] if cd in _INDEX.get(n, {})), None)
        if hit is None:
            raise RuntimeError(f"a run built a config that no variant cell gives (overrides {overrides})")
        c1 = build(variants[hit[0]], hit[1], d0["seed"])
        if canon(EC.to_dict(c1)) != canon(d0):
            raise RuntimeError(f"variant {hit} does not rebuild the run's config")
        _USED.append(hit)
        return c1
    return ref_load


_USED: list = []
_VARIANTS: dict = {}


def _worker_init(variants):
    _VARIANTS.update(variants)
    try:
        os.nice(19)
    except OSError:
        pass
    studies()   # import every run module so its `load` can be replaced


def rerun(task) -> dict:
    """task = (study, spec) -> {key, record digest, fields, used cells}. Every config comes from the reference file."""
    name, spec = task
    st = studies()[name]
    _USED.clear()
    _install(_ref_load_factory(_VARIANTS, name))
    try:
        rec = json.loads(json.dumps(st["job"](spec)))
    finally:
        _install(ORIG_LOAD)
    k = st["key"](spec)
    body = {f: v for f, v in rec.items() if f not in EXCLUDE}
    return {"study": name, "key": k, "sha256": hashlib.sha256(canon(body).encode()).hexdigest(), "rec": body,
            "used": sorted({f"{a}/{b}" for a, b in _USED})}


def _compare(new: dict, saved_line: str) -> list[str]:
    old = {f: v for f, v in json.loads(saved_line).items() if f not in EXCLUDE}
    return sorted(f for f in set(new) | set(old) if canon(new.get(f)) != canon(old.get(f)))


def _pool(tasks, variants, workers, log):
    out = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init, initargs=(variants,)) as ex:
        for i, r in enumerate(ex.map(rerun, tasks), 1):
            out.append(r)
            if i % 25 == 0 or i == len(tasks):
                log(f"{i}/{len(tasks)} chains rerun")
    return out


def _spec_json(spec):
    return json.loads(json.dumps(spec))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--generate", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--quick", action="store_true", help="--check: the first chain of each run only")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)

    def log(m):
        print(f"{time.strftime('%F %T')} {m}", flush=True)

    if a.write or a.generate:
        ref = reference_dict()
        with open(REF_PATH, "w", encoding="utf-8") as f:
            json.dump(ref, f, indent=2, sort_keys=True)
            f.write("\n")
        variants, select = derive(log)
        with open(VAR_PATH, "w", encoding="utf-8") as f:
            json.dump({"engine_version": ENGINE_VERSION, "reference": REF_PATH,
                       "use": "load(reference, [*overrides, *cells[cell], 'seed=N']); chain-level bust-out and "
                              "licensing schedules are applied by the run's script (benchmark.bust_config, "
                              "licence_config)", "variants": variants}, f, indent=1)
            f.write("\n")
        log(f"wrote {REF_PATH} and {VAR_PATH} ({len(variants)} variants)")
        sel_path = DIG_PATH.replace("digests.json", "selection.json")
        os.makedirs(os.path.dirname(DIG_PATH), exist_ok=True)
        with open(sel_path, "w", encoding="utf-8") as f:
            S0 = studies()
            json.dump({n: [{"key": S0[n]["key"](j), "spec": _spec_json(j), "cell": lab, "seed": sd} for j, lab, sd in xs]
                       for n, xs in select.items()}, f, indent=1)
            f.write("\n")
    if a.generate or a.check:
        with open(VAR_PATH, encoding="utf-8") as f:
            variants = json.load(f)["variants"]
        with open(DIG_PATH.replace("digests.json", "selection.json"), encoding="utf-8") as f:
            sel = json.load(f)
        tasks = [(n, _tuple(n, x["spec"])) for n, xs in sel.items() for x in (xs[:1] if a.quick else xs)]
        S0 = studies()
        keys = [x["key"] for n, xs in sel.items() for x in (xs[:1] if a.quick else xs)]
        if [S0[n]["key"](j) for n, j in tasks] != keys:
            raise SystemExit("selection.json: specs do not rebuild their keys")
        log(f"{len(tasks)} chains to rerun from the reference config at engine {ENGINE_VERSION}")
        res = _pool(tasks, variants, a.workers, log)
        S = studies()
        bad = 0
        if a.generate:
            by_cache: dict = {}
            for (n, spec), r in zip(tasks, res):
                by_cache.setdefault(S[n]["cache"](spec), set()).add(r["key"])
            saved = {}
            for p, ks in by_cache.items():
                saved[p] = _saved_index(p, lambda k, ks=ks: k in ks)
            dig = {}
            for (n, spec), r in zip(tasks, res):
                line = saved[S[n]["cache"](spec)].get(r["key"])
                d = ["(not in the saved cache)"] if line is None else _compare(r["rec"], line)
                if d:
                    bad += 1
                    log(f"*** {n} {r['key']}: DOES NOT REPRODUCE the saved chain; fields {d}")
                dig.setdefault(n, {})[r["key"]] = {"sha256": r["sha256"], "used": r["used"]}
            if bad:
                log(f"{bad} chains do not reproduce; digests not written")
                return 2
            with open(DIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"engine_version": ENGINE_VERSION, "chains": len(res), "excluded_fields": list(EXCLUDE),
                           "digests": dig}, f, indent=1, sort_keys=True)
                f.write("\n")
            log(f"all {len(res)} chains reproduce their saved records; digests written to {DIG_PATH}")
        else:
            with open(DIG_PATH, encoding="utf-8") as f:
                dig = json.load(f)["digests"]
            for r in res:
                if dig[r["study"]][r["key"]]["sha256"] != r["sha256"]:
                    bad += 1
                    log(f"*** {r['study']} {r['key']}: digest moved")
            log(f"{len(res) - bad}/{len(res)} digests unchanged")
            return 2 if bad else 0
    return 0


def _tuple(name, spec):
    """A spec read back from JSON, as the run scripts build it."""
    if name == "stars_sensitivity":
        st, arm, x = spec
        return (st, arm, _fix(st, x))
    return _fix(name, spec)


def _fix(name, x):
    """Rebuild one spec from JSON: the run scripts pass watch lists as lists, check_vs_read as tuples, candidates
    (b, h) as tuples."""
    x = list(x)
    if name in ("check_vs_read",):
        return tuple(tuple(v) if isinstance(v, list) else v for v in x)
    return tuple(tuple(v) if (isinstance(v, list) and len(v) == 2 and all(isinstance(i, int) for i in v)) else v
                 for v in x)


if __name__ == "__main__":
    sys.exit(main())
