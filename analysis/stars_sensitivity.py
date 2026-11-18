"""Run B: star-rating sensitivity of five earlier results (rule-based only; exploratory, no predictions).

Engine 0.20.0 adds ratings.display ("stars": every rating a buyer, a posted price or a seller decision reads is
rounded half up to ratings.display_step) and buyers.tie_break ("random": ties on (visible rating, price) broken by a
per-buyer, per-day random order of the stalls). Defaults reproduce 0.19.0 byte for byte. Background:
runs/brand_equity_speed_summary.md (buyers compared unrounded ratings, so 0.999 always lost to 1.0; price ties went
to the lower stall id).

Design. For each study below, the first 10 seeds of its original run are rerun under stars: the study's own config
plus STARS (ratings.display=stars, ratings.display_step=0.02, buyers.tie_break=random), everything else identical, and
paired by seed against the exact-rating chains saved in that study's cache. Each study's own config builder and chain
function are reused by import; the stars overrides are appended to every `engine.config.load` call the study's
config builder makes (the study module's `load` is wrapped for the duration of a stars chain), and every engine the
chain builds is checked to run with the intended display and tie-break. Only the chains each endpoint needs are run:
  verification (analysis/verification.py; seeds 200-209; caches runs/verification_cache_A.jsonl, _B.jsonl):
      A|t100, A|t40|l1, B|t100: per seed 1 never chain + 3 sampled stalls x 5 bust-out days = 16 chains per condition.
      Endpoints: Stage A gain at t100 (PV3), at t40|l1 (an endpoint of PV1), Stage B gain at t100 (PV3b), PV4 = B - A.
  liability (analysis/liability.py; seeds 230-239; runs/liability_cache.jsonl): col|t100|ds0.0 and col|t100|ds1.0,
      16 chains each per seed. Endpoints: the collectible gain at detect_scale 0 and 1, and their difference.
  bustout (analysis/bustout_decomp.py + bustout_report.py; seeds 230-239; runs/bustout_cache.jsonl): col|t40|ds0.0,
      the never chain and each sampled stall's best-candidate chain (best = the exact run's, runs/liability.csv; the
      stars arm decomposes the same candidate). Endpoints: "b. lost: inspected and walked away" and "b. lost: rating
      below threshold" (and the gain of that candidate).
  canal (analysis/canal_street.py; seeds 270-279; runs/canal_street_cache.jsonl): off, phi0.6, phi1.0 at t100, ds 1.
      Endpoints: PK3 (copied originals' day-30 rating, on - off, phi 0.6) and PK2 (gap at phi 1.0).
  licensing (analysis/licensing_checks.py; seeds 250-259; runs/licensing_checks_cache.jsonl): the never chain at
      t40|ds1.0 and contract|t40|ds1.0|free x 3 owners x 4 options (royalty 0.15, recomputed exactly at 0.10 as the
      study does). Endpoint: the owner's gain over the options every licensee accepts, royalty 0.10, unfloored.
Analysis: per seed as the study (mean over its 3 stalls / owners / deceptive stalls / copied originals); exact, stars,
and stars - exact paired by seed, mean and 95% t over seeds (engine.metrics.mean_ci); unadjusted; exploratory.

Checks built in: (1) endpoint definitions: every endpoint is recomputed from the saved chains over the study's full
original seed set and must equal the published value (to the printed precision) before anything runs; (2) --repro N
reruns N saved exact chains per study at the current engine with defaults and compares each with its cache record,
every field the record holds (including the full-outcome digest where the record has one); (3) guard counts (stuck,
parked, idle choosers, invalid actions), the display/tie-break of every engine, bust-out schedules and the study's own
identities, flagged; exit 2 on any flag.

    .venv/bin/python -m analysis.stars_sensitivity --seeds 900-902 --exact run --outdir runs/pilot_stars_sensitivity
    .venv/bin/python -m analysis.stars_sensitivity --repro 4      # writes runs/stars_sensitivity_repro.json, read by
                                                                  # the full run (or pass --repro-file)
    .venv/bin/python -m analysis.stars_sensitivity --timing --timing-chains 4                  # seconds per chain
    .venv/bin/python -m analysis.stars_sensitivity --tests "..." --gate "..."                     # full run
--seeds takes a range (900-902), a list (900,901) or one seed (900).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import platform
import re
import sys
import time

import numpy as np

import analysis.bustout_decomp as BD
import analysis.bustout_report as BR
import analysis.canal_street as CS
import analysis.chainrun as CR
import analysis.liability as LB
import analysis.licensing as L
import analysis.licensing_checks as LC
import analysis.verification as V
from analysis.capture import memory_state
from analysis.counterfeit import _ci, _d, _git, _load, _num, _t, _verdict
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, benchmark
from engine import bazaar as EB
from engine.metrics import mean_ci, paired_diff

NEVER = benchmark.NEVER
STARS = ["ratings.display=stars", "ratings.display_step=0.02", "buyers.tie_break=random"]
STARS_SEEN = ("stars", 0.02, "random")
EXACT_SEEN = ("exact", 0.02, "stall_id")
STUDIES = ("verification", "liability", "bustout", "canal", "licensing")
ORIG_SEEDS = {"verification": list(range(200, 220)), "liability": list(range(230, 250)),
              "bustout": list(range(230, 250)), "canal": list(range(270, 300)), "licensing": list(range(250, 270))}
ORIG_RUN = {"verification": "engine 0.13.0 (stage A) and 0.14.0 (stage B), seeds 200-219",
            "liability": "engine 0.15.0, seeds 230-249", "bustout": "engine 0.15.0 replay, seeds 230-249",
            "canal": "engine 0.17.0, seeds 270-299", "licensing": "engine 0.16.0 replay, seeds 250-269"}
SUMMARIES = {"verification": "runs/verification_summary.md", "liability": "runs/liability_summary.md",
             "bustout": "runs/bustout_decomposition.md", "canal": "runs/canal_street_summary.md",
             "licensing": "runs/licensing_checks.md"}
CACHES = {"verification": {"A": "runs/verification_cache_A.jsonl", "B": "runs/verification_cache_B.jsonl"},
          "liability": "runs/liability_cache.jsonl", "bustout": BD.CACHE, "canal": "runs/canal_street_cache.jsonl",
          "licensing": LC.CACHE}
VER_CONDS = ["A|t100", "A|t40|l1", "B|t100"]
LIAB_CONDS = ["col|t100|ds0.0", "col|t100|ds1.0"]
BUST_COND = "col|t40|ds0.0"
CANAL_CONDS = ["off|t100|ds1.0", "phi0.6|t100|ds1.0", "phi1.0|t100|ds1.0"]
LIC_COND = "contract|t40|ds1.0|free"
LIC_BASE = L.base_key("t40", 1.0)
LIC_RATE = LC.HEADLINE                    # 0.10
PATCHED = (V, LB, L, CS, LC)              # modules whose `load` builds the studies' configs
PER_SEED = {"verification": 48, "liability": 32, "bustout_saved": 4, "bustout_run": 16, "canal": 3, "licensing": 13}

# Endpoints: published value (display units: $ or rating) as the original summary prints it, the verdict it gives,
# the sign of the original prediction (0: none; the verdict is then the side of 0 the interval is on), and sources.
EP = {
    "verification": [
        dict(id="A_t100", label="Stage A, tourists 1.0 (t100): gain (PV3)", unit="$", sign=+1,
             pub=(565.27, 433.55, 697.00), pub_txt="+565.27 [+433.55, +697.00] *", pub_verdict="PV3: supported",
             src="analysis/verification.py:206 gains, :220 seed_mean, :304 PV3; runs/verification_summary.md:34, :44"),
        dict(id="A_t40l1", label="Stage A, tourists 0.4, locals inspect: gain (an endpoint of PV1)", unit="$", sign=0,
             pub=(-110.99, -147.32, -74.66), pub_txt="−110.99 [−147.32, −74.66] *",
             pub_verdict="no prediction on this cell (interval below 0); PV1, which uses it, supported",
             src="analysis/verification.py:206, :220, :253; runs/verification_summary.md:30, :42"),
        dict(id="B_t100", label="Stage B, t100: gain (PV3b, exploratory analogue)", unit="$", sign=+1,
             pub=(-435.74, -536.62, -334.87), pub_txt="−435.74 [−536.62, −334.87] *",
             pub_verdict="PV3b: contradicted (interval on the opposite side of 0)",
             src="analysis/verification.py:206, :220, :304; runs/verification_summary.md:109, :119"),
        dict(id="PV4", label="t100: Stage B − Stage A (PV4)", unit="$", sign=-1,
             pub=(-1001.02, -1212.14, -789.89), pub_txt="−1,001.02 [−1,212.14, −789.89] *",
             pub_verdict="PV4: supported", src="analysis/verification.py:330 cross_stage; runs/verification_summary.md:165"),
    ],
    "liability": [
        dict(id="col_t100_ds0", label="Collectible, t100, detect_scale 0: gain", unit="$", sign=0,
             pub=(564.45, 434.09, 694.81), pub_txt="+564.45 [+434.09, +694.81] *",
             pub_verdict="no prediction on this cell (interval above 0)",
             src="analysis/liability.py:263 gains, :277 seed_mean, :297; runs/liability_summary.md:31"),
        dict(id="col_t100_ds1", label="Collectible, t100, detect_scale 1: gain", unit="$", sign=0,
             pub=(-389.04, -492.70, -285.38), pub_txt="−389.04 [−492.70, −285.38] *",
             pub_verdict="no prediction on this cell (interval below 0)",
             src="analysis/liability.py:263, :277, :297; runs/liability_summary.md:33"),
        dict(id="col_t100_ds1_minus_ds0", label="Collectible, t100: gain at ds 1 − gain at ds 0 (two-level analogue of "
             "PL1; PL1 is a slope over {0, 0.1, 1})", unit="$", sign=-1, pub=None,
             pub_txt="not published (PL1 slope: −963.90 [−1,189.56, −738.24] * per 1.0 of detect_scale)",
             pub_verdict="PL1: supported (a different statistic)",
             src="per-seed difference of the two rows above; PL1 at analysis/liability.py:359, runs/liability_summary.md:47"),
    ],
    "bustout": [
        dict(id="lost_inspected", label="Collectible, t40, ds 0: b. lost: inspected and walked away", unit="$", sign=0,
             pub=(-131.93, -165.81, -98.04), pub_txt="−131.93 [−165.81, −98.04] *",
             pub_verdict="no prediction (interval below 0); the reading: the main cause of the loss",
             src="analysis/bustout_report.py:56 cause, :70 decompose, :175 by_cond; runs/bustout_decomposition.md:32"),
        dict(id="lost_rated_below", label="Collectible, t40, ds 0: b. lost: rating below threshold", unit="$", sign=0,
             pub=(-14.35, -42.50, 13.79), pub_txt="−14.35 [−42.50, +13.79]",
             pub_verdict="no prediction (interval includes 0); the reading: \"add little\"",
             src="analysis/bustout_report.py:56, :70, :175; runs/bustout_decomposition.md:33"),
        dict(id="gain", label="Collectible, t40, ds 0: gain of the decomposed candidate (context)", unit="$", sign=0,
             pub=(-93.57, -122.56, -64.59), pub_txt="−93.57 [−122.56, −64.59] *",
             pub_verdict="no prediction (interval below 0)",
             src="analysis/bustout_report.py:70, :175; runs/bustout_decomposition.md:40"),
    ],
    "canal": [
        dict(id="PK3", label="t100, ds 1, φ 0.6: copied originals' day-30 rating, on − off (PK3)", unit="rating",
             sign=-1, pub=(-0.379, -0.393, -0.365), pub_txt="−0.379 [−0.393, −0.365] *", pub_verdict="PK3: supported",
             src="analysis/canal_street.py:190, :196, :229; runs/canal_street_summary.md:39"),
        dict(id="PK2", label="t100, ds 1, φ 1.0: gap, 30-day (PK2)", unit="$", sign=-1,
             pub=(-369.83, -457.80, -281.86), pub_txt="−369.83 [−457.80, −281.86] *", pub_verdict="PK2: supported",
             src="analysis/canal_street.py:185, :227; runs/canal_street_summary.md:38"),
    ],
    "licensing": [
        dict(id="con_unf_0.10", label="Contract, t40, ds 1, not liable: owner's gain over the options every licensee "
             "accepts, royalty 0.10, unfloored", unit="$", sign=0,
             pub=(3442.72, 2768.04, 4117.41), pub_txt="+3,442.72 [+2,768.04, +4,117.41] *",
             pub_verdict="no prediction (interval above 0); the BLUF's headline",
             src="analysis/licensing_checks.py:339 _owner_rows, :443-452, :463; runs/licensing_checks.md:8, :435"),
    ],
}


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ study adapters

def skey(study, spec) -> str:
    """The study's own cache key of a chain."""
    return {"verification": V._key, "liability": LB._key, "bustout": BD._key, "canal": CS.key,
            "licensing": LC._key}[study](spec)


def seed_of(study, spec) -> int:
    return int(spec[2] if study in ("verification", "licensing") else spec[1])


def cache_of(study, spec) -> str:
    c = CACHES[study]
    return c[spec[0]] if study == "verification" else c


def _jobfn(study):
    return {"verification": V._job, "liability": LB._job, "bustout": BD._job, "canal": CS.job,
            "licensing": LC._job}[study]


def slim(study, r: dict) -> dict:
    """What the endpoints and checks need of a chain record (saved or new)."""
    if study == "verification":
        return {k: r[k] for k in ("key", "cond", "seed", "stall", "b", "totals", "busts", "fallbacks") if k in r}
    if study == "liability":
        return {k: r[k] for k in ("key", "cond", "seed", "stall", "b", "totals", "busts", "exited", "fallbacks",
                                  "guard") if k in r}
    if study == "bustout":
        return dict(r)
    if study == "canal":
        out = {k: r[k] for k in ("key", "cond", "seed", "stalls", "rating", "copied", "counterfeit_of", "cf_fixed_ok",
                                 "renames", "profit_mismatch", "guard") if k in r}
        out["profit30"] = {s: int(sum(v)) for s, v in r["series"]["profit"].items()}
        return out
    return {k: v for k, v in r.items() if k not in ("dig_trade", "dig_nonroy")}


def bust_best_saved() -> dict:
    """{(seed, stall): best candidate key} for BUST_COND from runs/liability.csv (the decomposition's own source)."""
    arm, t, ds = LB.parts(BUST_COND)
    return {(k[3], k[4]): v["best"] for k, v in BD.best_table().items() if k[:3] == (arm, t, ds)}


def specs(study, seeds, samples, kind, best=None) -> list[tuple]:
    """kind: "saved" (the exact chains the endpoints use), "run" (the exact chains to run when there are no saved
    ones; bustout: every candidate, so the best can be found), "stars" (bustout: never + `best`)."""
    if study == "verification":
        return V.jobs_for(VER_CONDS, seeds, samples)
    if study == "liability":
        return LB.jobs_for(LIAB_CONDS, seeds, samples)
    if study == "bustout":
        out = []
        for sd in seeds:
            w = samples[sd]
            out.append((BUST_COND, sd, w, None, NEVER))
            for s in w:
                if kind == "run":
                    out += [(BUST_COND, sd, [s], s, b) for b in LB.cands(BUST_COND)]
                else:
                    out.append((BUST_COND, sd, [s], s, BD.parse_cand(best[(sd, s)])))
        return out
    if study == "canal":
        return [(c, sd) for sd in seeds for c in CANAL_CONDS]
    out = []
    for sd in seeds:
        out.append(("never", LIC_BASE, sd, None, NEVER, LC.BASE_R))
        out += [("lic", LIC_COND, sd, s, o, LC.BASE_R) for s in samples[sd] for o in L.LIC_OPTS]
    return out


def bust_best_from(idx: dict, seeds, samples) -> dict:
    """The best candidate (unfloored, earliest on a tie: benchmark.gain) per stall-seed from exact chains of every
    candidate, as liability.gains finds it."""
    out = {}
    for sd in seeds:
        nv = idx[f"{BUST_COND}|{sd}|None|{NEVER}"]
        for s in samples[sd]:
            tot = {NEVER: nv["totals"][s],
                   **{LB.ck(b): idx[f"{BUST_COND}|{sd}|{s}|{LB.ck(b)}"]["totals"][s] for b in LB.cands(BUST_COND)}}
            out[(sd, s)] = benchmark.gain(tot)["best_day"]
    return out


# ------------------------------------------------------------------ worker

_ENG: list = []
_GUARD: list = []


def _hooks() -> None:
    """Observers that change nothing: every engine's (display, step, tie-break), and each run's guard counts."""
    if getattr(EB.BazaarEngine.__init__, "_stars_seen", False):
        return
    oi, orun = EB.BazaarEngine.__init__, EB.run

    def init(self, cfg, *a, **k):
        _ENG.append((cfg.ratings.display, float(cfg.ratings.display_step), cfg.buyers.tie_break))
        return oi(self, cfg, *a, **k)

    def run(cfg, *a, **k):
        out = orun(cfg, *a, **k)
        _GUARD.append(CR.guard(out))
        return out

    init._stars_seen = True
    EB.BazaarEngine.__init__ = init
    EB.run = run


@contextlib.contextmanager
def _arm(arm):
    """Stars: STARS appended to every load() the study's config builder makes. Exact: nothing changed."""
    orig = {m: m.load for m in PATCHED}
    if arm == "stars":
        for m in PATCHED:
            base = orig[m]
            m.load = lambda path=None, overrides=None, mode=None, _b=base: _b(path, [*(overrides or []), *STARS],
                                                                              mode=mode)
    try:
        yield
    finally:
        for m, f in orig.items():
            m.load = f


def _run_one(study, arm, spec) -> tuple[dict, dict]:
    _hooks()
    LB._PARKED.clear()
    _ENG.clear()
    _GUARD.clear()
    t0 = time.time()
    with _arm(arm):
        rec = _jobfn(study)(spec)
    secs = time.time() - t0
    want = STARS_SEEN if arm == "stars" else EXACT_SEEN
    seen = sorted(set(_ENG))
    g = {k: sum(x[k] for x in _GUARD) for k in ("stuck_buyers", "idle_choosers", "parked", "buyer_days", "fallbacks")}
    info = {"secs": round(secs, 2), "engines": len(_ENG), "seen": [list(x) for x in seen],
            "arm_ok": bool(_ENG) and seen == [want] and len(_GUARD) == 1, "runs": len(_GUARD), "guard": g}
    return rec, info


def key(j) -> str:
    if j[0] == "repro":
        return f"repro|{j[1]}|{skey(j[1], j[2])}"
    study, arm, spec = j
    return f"{study}|{arm}|{skey(study, spec)}"


def job(j) -> dict:
    """j = (study, arm, spec) -> slim record; or ("repro", study, spec, saved record) -> comparison."""
    if j[0] == "repro":
        _, study, spec, saved = j
        rec, info = _run_one(study, "exact", spec)
        return {"key": key(j), "study": study, "skey": skey(study, spec), **compare(rec, saved), **info}
    study, arm, spec = j
    rec, info = _run_one(study, arm, spec)
    rec = json.loads(json.dumps(rec))           # as the studies read their chains back from their caches
    return {"key": key(j), "study": study, "arm": arm, "seed": seed_of(study, spec), "skey": skey(study, spec),
            "engine_version": ENGINE_VERSION, "rec": slim(study, rec), **info}


def compare(new: dict, old: dict) -> dict:
    """Every top-level field the saved record holds, against the rerun (JSON-normalised)."""
    new = json.loads(json.dumps(new))
    common = sorted(set(new) & set(old))
    diff = [k for k in common if new[k] != old[k]]
    out = {"match": not diff and ("totals" in common or "digest" in common), "compared": common, "differs": diff,
           "only_new": sorted(set(new) - set(old)), "only_saved": sorted(set(old) - set(new)),
           "digest_compared": "digest" in common}
    if "totals" in diff:
        out["totals_new"], out["totals_saved"] = new["totals"], old["totals"]
    return out


# ------------------------------------------------------------------ saved chains

_KEY_RE = re.compile(r'^\{"key":"([^"]*)"')


def read_saved(path: str, wanted: set, study: str) -> dict:
    """{study key: slim record} for the wanted keys of a study cache (streamed; full records only if asked)."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = _KEY_RE.match(line)
            k = m.group(1) if m else json.loads(line)["key"]
            if k in wanted:
                out[k] = slim(study, json.loads(line))
    return out


def read_saved_full(path: str, wanted: set) -> dict:
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = _KEY_RE.match(line)
            k = m.group(1) if m else json.loads(line)["key"]
            if k in wanted:
                out[k] = json.loads(line)
    return out


def saved_index(study, seeds, samples, best) -> tuple[dict, list]:
    """Saved exact chains of `seeds`: (index by study key, missing keys)."""
    sp = specs(study, seeds, samples, "saved", best)
    by_path: dict = {}
    for x in sp:
        by_path.setdefault(cache_of(study, x), set()).add(skey(study, x))
    idx = {}
    for p, ks in by_path.items():
        idx.update(read_saved(p, ks, study))
    return idx, [skey(study, x) for x in sp if skey(study, x) not in idx]


# ------------------------------------------------------------------ endpoints (per seed)

def _r05(x):
    return 0.5 if x is None else x


def endpoints(study, idx: dict, seeds, samples, best=None) -> dict:
    """{endpoint id: per-seed values} from an index {study key: slim record}, as the study computes them."""
    if study == "verification":
        runs = [r for r in idx.values() if r["cond"] in VER_CONDS and r["seed"] in seeds]
        G = V.gains(runs, samples)
        a, a40, b = (V.seed_mean(G, c, seeds, "gain_unfloored") for c in VER_CONDS)
        return {"A_t100": a, "A_t40l1": a40, "B_t100": b, "PV4": [y - x for x, y in zip(a, b)]}
    if study == "liability":
        runs = [r for r in idx.values() if r["cond"] in LIAB_CONDS and r["seed"] in seeds]
        G = LB.gains(runs, samples)
        d0, d1 = (LB.seed_mean(G, c, seeds, "gain_unfloored") for c in LIAB_CONDS)
        return {"col_t100_ds0": d0, "col_t100_ds1": d1, "col_t100_ds1_minus_ds0": [y - x for x, y in zip(d0, d1)]}
    if study == "bustout":
        per = {"lost_inspected": [], "lost_rated_below": [], "gain": []}
        extra = {"e_max_abs": 0, "pre_bust_differences": 0, "units_inspected": [], "units_rated_below": [],
                 "best": {}}
        for sd in seeds:
            N = idx[f"{BUST_COND}|{sd}|None|{NEVER}"]
            rows = []
            for s in samples[sd]:
                cand = best[(sd, s)]
                B = idx[f"{BUST_COND}|{sd}|{s}|{cand}"]
                b0 = int(cand.split("h")[0])
                ex = b0 + int(cand.split("h")[1]) - 1 if "h" in cand else None
                rows.append(BR.decompose(N, B, s, b0, ex))
                extra["best"][f"{sd}|{s}"] = cand
            per["lost_inspected"].append(float(np.mean([r["comp"]["lost_inspected"] for r in rows])))
            per["lost_rated_below"].append(float(np.mean([r["comp"]["lost_rated_below"] for r in rows])))
            per["gain"].append(float(np.mean([r["gain"] for r in rows])))
            extra["e_max_abs"] = max(extra["e_max_abs"], *[abs(r["e"]) for r in rows])
            extra["pre_bust_differences"] += sum(r["pre_bust_differences"] for r in rows)
            extra["units_inspected"] += [r["lost_units"].get("inspected", 0) for r in rows]
            extra["units_rated_below"] += [r["lost_units"].get("rated_below", 0) for r in rows]
        per["_extra"] = extra
        return per
    if study == "canal":
        pk3, pk2 = [], []
        for sd in seeds:
            o = idx[f"{CANAL_CONDS[0]}|{sd}"]
            r6, r1 = idx[f"{CANAL_CONDS[1]}|{sd}"], idx[f"{CANAL_CONDS[2]}|{sd}"]
            orig = sorted({x for x in r6["copied"].values() if x is not None})
            pk3.append(float(np.mean([_r05(r6["rating"][s][CS.DAYS - 1]) - _r05(o["rating"][s][CS.DAYS - 1])
                                      for s in orig])))
            dec = [s for s, v in r1["stalls"].items() if v["stype"] == "deceptive"]
            pk2.append(float(np.mean([r1["profit30"][s] - o["profit30"][s] for s in dec])))
        return {"PK3": pk3, "PK2": pk2}
    # licensing: the study's own per-owner recompute (licensing_checks._owner_rows), aggregated as its analyse()
    opts = [L.ok(o) for o in L.LIC_OPTS]
    data = {"never": {}, "lic": {}}
    for sd in seeds:
        data["never"][(LIC_BASE, sd)] = idx[LC._key(("never", LIC_BASE, sd, None, NEVER, LC.BASE_R))]
        for s in samples[sd]:
            for o in L.LIC_OPTS:
                data["lic"][(LIC_COND, sd, s, L.ok(o))] = idx[LC._key(("lic", LIC_COND, sd, s, o, LC.BASE_R))]
    per, acc_share = [], []
    for sd in seeds:
        vals = []
        for s in samples[sd]:
            nv = data["never"][(LIC_BASE, sd)]["totals"][s]
            tot, ok_ = {}, {}
            for o in opts:
                lic, _grp, tr = LC._owner_rows(data, LIC_COND, sd, s, o, LIC_RATE)
                tot[o], ok_[o] = tr, all(x["accept"] for x in lic)
                acc_share += [x["accept"] for x in lic]
            okd = {o: tot[o] for o in opts if ok_[o]}
            vals.append(benchmark.gain({NEVER: nv, **okd})["gain_unfloored"] if okd else 0)
        per.append(float(np.mean(vals)))
    return {"con_unf_0.10": per, "_extra": {"licensee_accept_share": float(np.mean(acc_share)) if acc_share else None}}


def _pub_ok(ep, stat) -> bool | None:
    if ep["pub"] is None:
        return None
    sc = 100.0 if ep["unit"] == "$" else 1.0
    dp = 2 if ep["unit"] == "$" else 3
    got = [stat[k] for k in ("mean", "lo", "hi")]
    return all(g is not None and abs(round(g / sc, dp) - p) < 0.5 * 10 ** -dp + 1e-9 for g, p in zip(got, ep["pub"]))


def definition_check(study, samples, log) -> dict:
    """Every endpoint over the study's full original seed set, from its saved chains, against the published value."""
    seeds = ORIG_SEEDS[study]
    best = bust_best_saved() if study == "bustout" else None
    idx, missing = saved_index(study, seeds, samples, best)
    if missing:
        return {"pass": False, "missing": len(missing), "rows": []}
    per = endpoints(study, idx, seeds, samples, best)
    rows = []
    for ep in EP[study]:
        st = mean_ci(per[ep["id"]])
        rows.append({"id": ep["id"], "computed": st, "published": ep["pub_txt"], "match": _pub_ok(ep, st)})
    ok = all(r["match"] is not False for r in rows)
    log(f"definition check {study}: {'pass' if ok else 'FAIL'} ({len(seeds)} seeds, {len(idx)} saved chains)")
    return {"pass": ok, "missing": 0, "rows": rows, "seeds": f"{seeds[0]}-{seeds[-1]}"}


# ------------------------------------------------------------------ reproduction check

def repro(a, studies, samples_for, log) -> dict:
    out = {"engine_version": ENGINE_VERSION, "git": _git()["commit"], "time": time.strftime("%Y-%m-%d %H:%M:%S"),
           "n_per_study": a.repro, "studies": {}}
    jobs = []
    for st in studies:
        seeds = ORIG_SEEDS[st][:a.seeds_per_study]
        samples = samples_for(seeds)
        best = bust_best_saved() if st == "bustout" else None
        sp = specs(st, seeds, samples, "saved", best)
        pick = sorted({int(round(x)) for x in np.linspace(0, len(sp) - 1, min(a.repro, len(sp)))})
        sel = [sp[i] for i in pick]
        by_path: dict = {}
        for x in sel:
            by_path.setdefault(cache_of(st, x), set()).add(skey(st, x))
        saved = {}
        for p, ks in by_path.items():
            saved.update(read_saved_full(p, ks))
        for x in sel:
            if skey(st, x) not in saved:
                raise SystemExit(f"repro: {st}: saved chain {skey(st, x)} not in {cache_of(st, x)}")
            jobs.append(("repro", st, x, saved[skey(st, x)]))
    log(f"reproduction check: {len(jobs)} saved exact chains rerun at engine {ENGINE_VERSION} with defaults")
    res, _ = CR.run_chains(a, jobs, None, log, job, key)
    for r in res:
        s = out["studies"].setdefault(r["study"], {"chains": 0, "reproduced": 0, "rows": []})
        s["chains"] += 1
        ok = r["match"] and r["arm_ok"]
        s["reproduced"] += ok
        s["rows"].append({k: r.get(k) for k in ("skey", "match", "arm_ok", "compared", "differs", "only_new",
                                                "only_saved", "digest_compared", "secs", "totals_new", "totals_saved")})
        log(f"repro {r['study']} {r['skey']}: {'reproduces' if ok else 'DOES NOT REPRODUCE'}; fields compared "
            f"{len(r['compared'])}{' (incl. full-outcome digest)' if r['digest_compared'] else ''}; differ "
            f"{r['differs'] or 'none'}; {r['secs']} s")
    for st, s in out["studies"].items():
        s["pass"] = s["reproduced"] == s["chains"]
        if not s["pass"]:
            log(f"*** {st}: {s['chains'] - s['reproduced']} of {s['chains']} saved chains DO NOT REPRODUCE at engine "
                f"{ENGINE_VERSION}: pairing stars against this study's saved chains is not valid. Use --exact run "
                f"(fresh exact chains) for it, or investigate.")
    out["pass"] = all(s["pass"] for s in out["studies"].values())
    return out


# ------------------------------------------------------------------ analysis

def _side(st) -> str:
    if st.get("lo") is None:
        return "not testable"
    return "interval above 0" if st["lo"] > 0 else ("interval below 0" if st["hi"] < 0 else "interval includes 0")


def _vd(ep, st) -> str:
    return _verdict(st, ep["sign"]) if ep["sign"] else _side(st)


def _sgn(x):
    return None if x is None else (0 if x == 0 else (1 if x > 0 else -1))


def analyse(studies, idx_e, idx_s, seeds, samples, best) -> dict:
    res = {}
    for st in studies:
        pe = endpoints(st, idx_e[st], seeds[st], samples, best.get(st))
        ps = endpoints(st, idx_s[st], seeds[st], samples, best.get(st))
        rows = []
        for ep in EP[st]:
            e, s = mean_ci(pe[ep["id"]]), mean_ci(ps[ep["id"]])
            d = paired_diff(pe[ep["id"]], ps[ep["id"]])
            ve, vs = _vd(ep, e), _vd(ep, s)
            rows.append({**{k: ep[k] for k in ("id", "label", "unit", "sign", "pub_txt", "pub_verdict", "src")},
                         "exact": e, "stars": s, "diff": d, "per_seed_exact": pe[ep["id"]],
                         "per_seed_stars": ps[ep["id"]], "verdict_exact": ve, "verdict_stars": vs,
                         "sign_change": _sgn(e["mean"]) != _sgn(s["mean"]), "verdict_change": ve != vs})
        res[st] = {"seeds": seeds[st], "rows": rows, "extra_exact": pe.get("_extra"), "extra_stars": ps.get("_extra")}
    return res


def checks(studies, recs_run: list, res: dict, defs: dict, rep: dict | None, exact_mode: str) -> tuple[dict, list]:
    flags = []
    guard: dict = {}
    for r in recs_run:
        g = guard.setdefault(f"{r['study']} · {r['arm']}", {"chains": 0, "stuck_buyers": 0, "parked": 0,
                                                            "idle_choosers": 0, "fallbacks": 0, "buyer_days": 0,
                                                            "arm_bad": 0, "schedule_bad": 0, "secs": 0.0})
        g["chains"] += 1
        for k in ("stuck_buyers", "parked", "idle_choosers", "fallbacks", "buyer_days"):
            g[k] += r["guard"][k]
        g["arm_bad"] += not r["arm_ok"]
        g["secs"] += r["secs"]
        x = r["rec"]
        if r["study"] in ("verification", "liability", "bustout"):
            b = x["b"]
            want = [] if b == NEVER else [[x["stall"], int(str(b).split("h")[0])]]
            if [list(y) for y in (x.get("busts") or [])] != want and "busts" in x:
                g["schedule_bad"] += 1
            if r["study"] == "bustout":
                dd = [d["stalls"][x["stall"]]["busted_day"] for d in x["days"]] if x["stall"] else []
                if x["stall"] and (dd[-1] != int(str(b).split("h")[0])):
                    g["schedule_bad"] += 1
        if r["study"] == "canal":
            g["schedule_bad"] += int(bool(x.get("profit_mismatch")))
            if x["cond"].startswith("phi"):
                dec = {s for s, v in x["stalls"].items() if v["stype"] == "deceptive"}
                if set(x["counterfeit_of"]) != dec or not x["cf_fixed_ok"] or any(x["renames"][1:]) \
                        or any(v is None for v in x["copied"].values()):
                    g["schedule_bad"] += 1
        if r["study"] == "licensing":
            g["schedule_bad"] += int(bool(x.get("roy_mismatch") or x.get("profit_mismatch")))
    for k, g in guard.items():
        for f in ("stuck_buyers", "parked", "idle_choosers", "fallbacks"):
            if g[f]:
                flags.append(f"{k}: {f} {g[f]}")
        if g["arm_bad"]:
            flags.append(f"{k}: {g['arm_bad']} chains whose engines did not run with the intended display/tie-break")
        if g["schedule_bad"]:
            flags.append(f"{k}: {g['schedule_bad']} chains failing the study's schedule or identity check")
    if "bustout" in res:
        for arm, ex in (("exact", res["bustout"]["extra_exact"]), ("stars", res["bustout"]["extra_stars"])):
            if ex["e_max_abs"]:
                flags.append(f"bustout {arm}: decomposition leaves {ex['e_max_abs']} cents unexplained")
            if ex["pre_bust_differences"]:
                flags.append(f"bustout {arm}: {ex['pre_bust_differences']} buyer records differ before the bust-out")
    for st, d in defs.items():
        if not d["pass"]:
            flags.append(f"{st}: endpoint definitions do not reproduce the published values")
    if exact_mode == "saved":
        for st in studies:
            s = (rep or {}).get("studies", {}).get(st)
            if s is None:
                flags.append(f"{st}: reproduction of the saved exact chains at engine {ENGINE_VERSION} not checked "
                             f"(run --repro N)")
            elif not s["pass"]:
                flags.append(f"{st}: saved exact chains DO NOT REPRODUCE at engine {ENGINE_VERSION}")
    return guard, flags


# ------------------------------------------------------------------ report

def _fmt(unit):
    return _d if unit == "$" else _num(3)


def report(res, defs, rep, guard, flags, meta, old) -> str:
    ex_lab = ("saved chains (the original run's engine; reproduction at " + ENGINE_VERSION + " checked below)"
              if meta["exact_mode"] == "saved" else f"run fresh by this script at engine {ENGINE_VERSION}")
    L_ = ["# Star ratings: sensitivity of five earlier results (Run B)", "",
          "**Exploratory. No predictions. Intervals are 95% t over seeds, unadjusted.**", "",
          "## Design", "",
          f"- Engine {ENGINE_VERSION}: `ratings.display` stars rounds every rating a buyer, a posted price or a seller "
          "decision reads half up to `ratings.display_step`; `buyers.tie_break` random breaks ties on (visible rating, "
          "price) by a per-buyer, per-day random order of the stalls. Defaults reproduce 0.19.0 byte for byte. "
          "Background: `runs/brand_equity_speed_summary.md`.",
          "- Stars arm: each study's own config plus `" + "`, `".join(STARS) + "`; everything else identical. The "
          "studies' own config builders and chain functions are used by import; the overrides are appended to every "
          "`load` call the study's config builder makes, and every engine a chain builds was checked to run with "
          "display stars, step 0.02, tie-break random (exact arm: exact, stall_id).",
          f"- Exact arm: {ex_lab}. Paired by seed: the stars chain for seed s has the same seed, stalls under test, "
          "candidates and options as the exact chain.",
          "- Seeds: " + "; ".join(f"{st} {meta['seeds_txt'][st]}" for st in res) + ".",
          "- Chains per seed: verification 48 (A|t100, A|t40|l1, B|t100: never + 3 stalls × 5 bust-out days); "
          "liability 32 (collectible, t100, ds 0 and 1: never + 3 × 5); bust-out decomposition 4 (collectible, t40, "
          "ds 0: never + each stall's best candidate of the exact run, the same candidate in both arms"
          + ("; the exact arm runs all 5 candidates to find it" if meta["exact_mode"] == "run" else "") +
          "); Canal Street 3 (off, φ 0.6, φ 1.0 at t100, ds 1); licensing 13 (never at t40, ds 1 + contract × 3 owners "
          "× 4 options at royalty 0.15, recomputed exactly at 0.10 as `analysis/licensing_checks.py` does).",
          "- Endpoints and their sources are listed per study. Per seed as each study (mean over its 3 stalls, owners, "
          "deceptive stalls or copied originals); exact, stars and stars − exact paired by seed.",
          "- Sign change: the means of exact and stars on opposite sides of 0. Verdict: the original rule applied to "
          "the 10-seed estimate (for endpoints without a prediction, the side of 0 the interval is on); verdict change "
          "compares exact and stars on the same seeds. The published estimate (more seeds) is shown for reference.", ""]
    L_ += ["## Run record", "",
           f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
           f"{meta['git']['status_porcelain'] or 'none'}",
           f"- Script sha256 `{meta['script_sha256']}`",
           f"- Command: `{meta['command']}`",
           f"- Tests: {meta['tests'] or '–'}",
           f"- Gate: {meta['gate'] or '–'}",
           f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
           f"- Chains run by this script: {meta['chains_run']} ({meta['chains_cached']} of them from its cache); saved "
           f"exact chains used: {meta['chains_saved']}; {meta['workers']} workers (nice 19); wall clock "
           f"{meta['wall_h']:.2f} h; load average {meta['load_start']} at start, {meta['load_end']} at end; memory at "
           f"start {meta['mem_start']}, at end {meta['mem_end']}; memory-guard pauses: {meta['pauses']}",
           f"- Flags: {len(flags)}", ""]
    L_ += ["## Checks", "", "**Endpoint definitions.** Each endpoint recomputed by this script from the saved chains "
           "over the study's full original seed set, against the published value:", "",
           *_t(["Study", "Endpoint", "Seeds", "Recomputed", "Published", "Equal"],
               [[st, r["id"], d.get("seeds", "–"),
                 _ci(r["computed"], _fmt(next(e["unit"] for e in EP[st] if e["id"] == r["id"]))), r["published"],
                 "–" if r["match"] is None else ("yes" if r["match"] else "**no**")]
                for st, d in defs.items() for r in d["rows"]]), ""]
    if meta["exact_mode"] == "saved":
        if rep:
            L_ += [f"**Reproduction of the saved exact chains at engine {rep['engine_version']}** (`--repro "
                   f"{rep['n_per_study']}`, {rep['time']}, commit {rep['git'][:7]}): each chain rerun with defaults and "
                   "compared with its cache record field by field (canal: including the sha256 of the full outcome).", "",
                   *_t(["Study", "Chains", "Reproduced", "Fields compared", "Not in the saved record"],
                       [[st, str(s["chains"]), str(s["reproduced"]) if s["pass"] else f"**{s['reproduced']}**",
                         ", ".join(sorted({c for r in s["rows"] for c in r["compared"]})),
                         ", ".join(sorted({c for r in s["rows"] for c in r["only_new"]})) or "–"]
                        for st, s in rep["studies"].items() if st in res]), ""]
        else:
            L_ += ["**Reproduction of the saved exact chains: not checked** (no `--repro` result in this outdir).", ""]
    for st, R in res.items():
        L_ += [f"## {st.capitalize()}", "",
               f"Original: `{SUMMARIES[st]}` ({ORIG_RUN[st]}). Seeds here: {meta['seeds_txt'][st]}.", "",
               *_t(["Endpoint", "Published (original seeds)", "Exact", "Stars", "Stars − exact [95% t]", "Sign change",
                    "Verdict: exact → stars", "Verdict change"],
                   [[r["label"], f"{r['pub_txt']}; {r['pub_verdict']}", _ci(r["exact"], _fmt(r["unit"])),
                     _ci(r["stars"], _fmt(r["unit"])), _ci(r["diff"], _fmt(r["unit"])),
                     "**yes**" if r["sign_change"] else "no", f"{r['verdict_exact']} → {r['verdict_stars']}",
                     "**yes**" if r["verdict_change"] else "no"] for r in R["rows"]]), "",
               "Sources: " + "; ".join(f"{r['id']}: {r['src']}" for r in R["rows"]) + ".", ""]
        if st == "bustout":
            ee, es = R["extra_exact"], R["extra_stars"]
            L_ += [f"Units lost per stall-seed (exact / stars): inspected and walked away "
                   f"{np.mean(ee['units_inspected']):.1f} / {np.mean(es['units_inspected']):.1f}; rating below threshold "
                   f"{np.mean(ee['units_rated_below']):.1f} / {np.mean(es['units_rated_below']):.1f}. Largest |e| "
                   f"{ee['e_max_abs']} / {es['e_max_abs']} cents; buyer records differing before the bust-out "
                   f"{ee['pre_bust_differences']} / {es['pre_bust_differences']}.", ""]
        if st == "licensing":
            L_ += [f"Share of licensees accepting at 0.10 (exact / stars): "
                   f"{_num(3)(R['extra_exact']['licensee_accept_share'])} / "
                   f"{_num(3)(R['extra_stars']['licensee_accept_share'])}.", ""]
    L_ += ["## Stuck, parked and idle buyers; invalid actions", "", "Chains run by this script.", "",
           *_t(["Study · arm", "Chains", "Buyer-days", "Stuck", "Parked", "Idle choosers", "Invalid actions",
                "Display/tie-break wrong", "Schedule or identity fails", "Seconds per chain"],
               [[k, str(g["chains"]), f"{g['buyer_days']:,}", str(g["stuck_buyers"]), str(g["parked"]),
                 str(g["idle_choosers"]), str(g["fallbacks"]), str(g["arm_bad"]), str(g["schedule_bad"]),
                 f"{g['secs'] / g['chains']:.1f}"] for k, g in guard.items()]), "",
           "## Flags", "", *([f"- {f}" for f in flags] or ["- none"]), ""]
    reading, caveats = "READING_PLACEHOLDER", "CAVEATS_PLACEHOLDER"
    if old:
        if "## Reading (written after the results)\n\n" in old:
            reading = old.split("## Reading (written after the results)\n\n", 1)[1].split("\n\n## Caveats", 1)[0]
        if "## Caveats\n\n" in old:
            caveats = old.split("## Caveats\n\n", 1)[1].rstrip()
    L_ += ["## Reading (written after the results)", "", reading, "", "## Caveats", "", caveats, ""]
    return "\n".join(L_)


# ------------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds-per-study", type=int, default=10, help="the first N seeds of each original run")
    ap.add_argument("--seeds", default=None, help="the same seeds for every study instead (pilot: 900-902)")
    ap.add_argument("--exact", choices=("saved", "run"), default="saved",
                    help="saved: pair with the study caches' chains; run: run the exact arm here")
    ap.add_argument("--studies", default=",".join(STUDIES))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--outdir", default="runs")
    ap.add_argument("--tests", default="")
    ap.add_argument("--gate", default="")
    ap.add_argument("--timing", action="store_true", help="time a few stars chains per study and project the run")
    ap.add_argument("--timing-chains", type=int, default=2)
    ap.add_argument("--repro", type=int, default=0, help="rerun N saved exact chains per study and compare")
    ap.add_argument("--repro-file", default=None)
    ap.add_argument("--min-swap-mb", type=float, default=512)
    ap.add_argument("--min-free-pct", type=float, default=15)
    a = ap.parse_args(argv)
    studies = [s for s in a.studies.split(",") if s]
    if any(s not in STUDIES for s in studies):
        raise SystemExit(f"--studies: choose from {', '.join(STUDIES)}")
    if a.seeds and os.path.abspath(a.outdir) == os.path.abspath("runs") and not (a.timing or a.repro):
        raise SystemExit("--seeds is for the pilot: use an --outdir other than runs")
    LB._lower_priority()
    os.makedirs(a.outdir, exist_ok=True)
    log = CR.file_logger(os.path.join(a.outdir, "stars_sensitivity_run.log"))
    repro_file = a.repro_file or os.path.join(a.outdir, "stars_sensitivity_repro.json")
    _smp: dict = {}

    def samples_for(seeds):
        for sd in seeds:
            if sd not in _smp:
                _smp[sd] = V.sample_stalls(sd)
        return {sd: _smp[sd] for sd in seeds}

    # a single number is one seed here (cli.sweep.parse_seeds reads it as a count)
    given = ([int(a.seeds)] if a.seeds and a.seeds.strip().isdigit() else parse_seeds(a.seeds)) if a.seeds else None
    seeds = {st: (given if given else ORIG_SEEDS[st][:a.seeds_per_study]) for st in studies}
    log(f"stars sensitivity: engine {ENGINE_VERSION}, commit {_git()['commit'][:7]}, studies {studies}, exact "
        f"{a.exact}, seeds {({k: f'{v[0]}-{v[-1]}' for k, v in seeds.items()})}; load {_load()}, memory {memory_state()}")

    if a.repro:
        rep = repro(a, studies, samples_for, log)
        with open(repro_file, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1)
        log(f"reproduction check {'pass' if rep['pass'] else 'FAIL'}; written to {repro_file}")
        return 0 if rep["pass"] else 2

    if a.timing:
        jobs = []
        for st in studies:
            sd = seeds[st][:1]
            sm = samples_for(sd)
            sp = specs(st, sd, sm, "run")
            pick = sorted({int(round(x)) for x in np.linspace(0, len(sp) - 1, min(a.timing_chains, len(sp)))})
            jobs += [(st, "stars", sp[i]) for i in pick]
        recs, _ = CR.run_chains(a, jobs, None, log, job, key)
        tot_h = 0.0
        print(f"{'study':<14}{'timed':>6}{'s/chain':>10}{'chains':>8}{'hours at ' + str(a.workers) + ' workers':>22}")
        for st in studies:
            rs = [r for r in recs if r["study"] == st]
            sec = float(np.mean([r["secs"] for r in rs]))
            n = len(seeds[st]) * (PER_SEED["bustout_saved"] if st == "bustout" else PER_SEED[st])
            if a.exact == "run":
                n += len(seeds[st]) * (PER_SEED["bustout_run"] if st == "bustout" else PER_SEED[st])
            h = n * sec / a.workers / 3600
            tot_h += h
            bad = [r["key"] for r in rs if not r["arm_ok"] or any(r["guard"][k] for k in
                                                                    ("stuck_buyers", "parked", "idle_choosers", "fallbacks"))]
            line = f"{st:<14}{len(rs):>6}{sec:>10.1f}{n:>8}{h:>22.2f}" + (f"  FLAGGED: {bad}" if bad else "")
            print(line)
            log(f"timing {st}: {len(rs)} chains, {sec:.1f} s per chain, {n} chains in the run, {h:.2f} h at "
                f"{a.workers} workers" + (f"; flagged {bad}" if bad else ""))
        log(f"timing: projected {tot_h:.2f} h in all ({'exact + stars' if a.exact == 'run' else 'stars only'}), "
            f"load {_load()}")
        return 0

    t0 = time.time()
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join(["python -m analysis.stars_sensitivity", *sys.argv[1:]]), "tests": a.tests,
            "gate": a.gate, "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "workers": a.workers, "load_start": _load(), "mem_start": memory_state(),
            "exact_mode": a.exact, "seeds_txt": {k: f"{v[0]}-{v[-1]} ({len(v)})" for k, v in seeds.items()},
            "stars_overrides": STARS}
    # 1. endpoint definitions against the published values
    defs = {}
    for st in studies:
        defs[st] = definition_check(st, samples_for(ORIG_SEEDS[st]), log)
    if not all(d["pass"] for d in defs.values()):
        with open(os.path.join(a.outdir, "stars_sensitivity_defcheck.json"), "w", encoding="utf-8") as f:
            json.dump(defs, f, indent=1)
        raise SystemExit("endpoint definitions do not reproduce the published values: stop (see "
                         "stars_sensitivity_defcheck.json)")
    rep = None
    if a.exact == "saved":
        if os.path.exists(repro_file):
            with open(repro_file, encoding="utf-8") as f:
                rep = json.load(f)
            bad = [st for st in studies if st in rep["studies"] and not rep["studies"][st]["pass"]]
            if bad:
                raise SystemExit(f"saved exact chains of {bad} DO NOT REPRODUCE at engine {ENGINE_VERSION} "
                                 f"({repro_file}): pairing against them is not valid. Rerun with --exact run, or "
                                 "investigate. Nothing was run.")
        else:
            log(f"WARNING: no reproduction check in {repro_file}; run --repro N first (flagged)")
    # 2. exact arm
    cache = os.path.join(a.outdir, "stars_sensitivity_cache.jsonl")
    pre = set()
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            pre = {json.loads(x)["key"] for x in f}
    idx_e, idx_s, best, recs_run, pauses, n_saved = {}, {}, {}, [], 0, 0
    for st in studies:
        sm = samples_for(seeds[st])
        if a.exact == "saved":
            b = bust_best_saved() if st == "bustout" else None
            idx, missing = saved_index(st, seeds[st], sm, b)
            if missing:
                raise SystemExit(f"{st}: {len(missing)} saved exact chains missing for seeds {meta['seeds_txt'][st]} "
                                 f"(e.g. {missing[0]}); use --exact run for seeds without saved chains")
            idx_e[st], n_saved = idx, n_saved + len(idx)
            if st == "bustout":
                best[st] = b
        else:
            jobs = [(st, "exact", x) for x in specs(st, seeds[st], sm, "run")]
            rs, p = CR.run_chains(a, jobs, cache, log, job, key)
            pauses += p
            recs_run += rs
            idx_e[st] = {r["skey"]: r["rec"] for r in rs}
            if st == "bustout":
                best[st] = bust_best_from(idx_e[st], seeds[st], sm)
    # 3. stars arm
    for st in studies:
        sm = samples_for(seeds[st])
        jobs = [(st, "stars", x) for x in specs(st, seeds[st], sm, "stars", best.get(st))]
        rs, p = CR.run_chains(a, jobs, cache, log, job, key)
        pauses += p
        recs_run += rs
        idx_s[st] = {r["skey"]: r["rec"] for r in rs}
    res = analyse(studies, idx_e, idx_s, seeds, {sd: _smp[sd] for sd in _smp}, best)
    guard, flags = checks(studies, recs_run, res, defs, rep, a.exact)
    meta.update(chains_run=len(recs_run), chains_cached=sum(r["key"] in pre for r in recs_run), chains_saved=n_saved,
                pauses=pauses, wall_h=(time.time() - t0) / 3600, load_end=_load(), mem_end=memory_state())
    with open(os.path.join(a.outdir, "stars_sensitivity_results.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "definition_check": defs, "repro": rep, "results": res, "guard": guard,
                   "flags": flags, "bust_best": {st: {f"{k[0]}|{k[1]}": v for k, v in b.items()}
                                                 for st, b in best.items()}}, f, indent=1, default=str)
    sp = os.path.join(a.outdir, "stars_sensitivity_summary.md")
    old = open(sp, encoding="utf-8").read() if os.path.exists(sp) else None
    with open(sp, "w", encoding="utf-8") as f:
        f.write(report(res, defs, rep, guard, flags, meta, old))
    for st, R in res.items():
        for r in R["rows"]:
            log(f"{st} {r['id']}: exact {_ci(r['exact'], _fmt(r['unit']))}, stars {_ci(r['stars'], _fmt(r['unit']))}, "
                f"stars − exact {_ci(r['diff'], _fmt(r['unit']))}; sign change {r['sign_change']}, verdict change "
                f"{r['verdict_change']}")
    log(f"done; {len(flags)} flags; wall {meta['wall_h']:.2f} h; load {_load()}")
    for fl in flags:
        log(f"FLAG: {fl}")
    return 2 if flags else 0


if __name__ == "__main__":
    raise SystemExit(main())
