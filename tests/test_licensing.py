"""Engine 0.16.0: licensing (engine/licensing.py). A genuine owner licenses its brand to N non-genuine
stalls of its category from the start of day b; licensees bear the name, post the brand's price, claim
its quality, never rename, and pay a royalty per unit; reviews of their sales go to the brand;
licensing.owner_liable moves fines from catches at licensees to the owner.

Reference: outcomes_v0150_all.json (94 cells at engine 0.15.0, 5b60720): every cell of
outcomes_v0140_all.json plus four liability cells (penalty lag 3, exit, detect_scale 0.3). Defaults must
reproduce every cell byte for byte, with nothing stripped."""
import hashlib
import json
import os

import pytest

from analysis.verification import overrides as vov
from engine import bazaar, benchmark
from engine.bazaar import BazaarEngine
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from engine.runner import compare_logs, replay

HERE = os.path.join(os.path.dirname(__file__), "reference")
with open(os.path.join(HERE, "outcomes_v0150_all.json"), encoding="utf-8") as f:
    REF = json.load(f)
CELLS = REF["cells"]


def _run(ov, seed, keep=False):
    log = JsonlLog(keep=True)
    return bazaar.run(load(overrides=[*ov, f"seed={seed}"], mode="bazaar"), log=log), log.lines


def _check(o, lines, c):
    assert dumps(o) == c["outcome"]
    assert len(lines) == c["log_lines"]
    assert hashlib.sha256("\n".join(lines[1:]).encode()).hexdigest() == c["log_body_sha256"]


def test_reference_is_0150():
    assert REF["engine_version"] == "0.15.0" and REF["commit"] == "5b60720" and len(CELLS) == 94


@pytest.mark.parametrize("key", sorted(CELLS))
def test_defaults_reproduce_0150(key):
    c = CELLS[key]
    o, lines = _run(c["overrides"], c["seed"])
    _check(o, lines, c)
    assert "licensing" not in o and all("licensing" not in d["outcome"] for d in o.get("days", []))


@pytest.mark.parametrize("key", ["v0150_jp_t100|0", "v0140_bust_t40|1"])
def test_dials_without_a_schedule_change_nothing(key):
    """Quality, royalty and liability settings are inert while the schedule is empty."""
    c = CELLS[key]
    o, lines = _run([*c["overrides"], "licensing.quality=contract", "licensing.royalty=0.4",
                     "licensing.owner_liable=true"], c["seed"])
    _check(o, lines, c)


# ------------------------------------------------------------------ helpers

def _base(seed=0, days=4, quality="cheap", liable=False, cond="B|t100", extra=()):
    return load(overrides=[*vov(cond), f"market.days={days}", f"licensing.quality={quality}",
                           f"licensing.owner_liable={'true' if liable else 'false'}", *extra, f"seed={seed}"],
                mode="bazaar")


def _owner(cfg):
    return next(st.sid for st in sorted(BazaarEngine(cfg).stalls, key=lambda s: s.idx) if st.stype == "genuine")


def _lic(cfg, option, log=None):
    sid = _owner(cfg)
    return bazaar.run(benchmark.licence_config(cfg, sid, option), log=log), sid


def _licensees(o, sid):
    for d in o["days"]:
        L = d["outcome"].get("licensing", {}).get("owners", {})
        if sid in L:
            return L[sid]["licensees"]
    return []


# ------------------------------------------------------------------ licences

def test_licensees_take_name_price_and_claim_from_day_b():
    cfg = _base()
    o, sid = _lic(cfg, (2, 3))
    never = bazaar.run(benchmark.licence_config(cfg, sid, benchmark.NEVER))
    lic = _licensees(o, sid)
    assert len(lic) == 2 and sid not in lic
    brand = o["days"][0]["brands"][sid]
    for d, dn in zip(o["days"], never["days"]):
        if d["day"] < 3:                      # before the licence, trading is the never run's
            for k in ("brands", "prices", "brand_ratings"):
                assert d[k] == dn[k]
            for k in ("brands", "purchases", "catches", "buyer_surplus_total_cents", "liability"):
                assert d["outcome"][k] == dn["outcome"][k]
            assert d["outcome"]["licensing"] == {"owners": {}}
            assert all(d["brands"][s] != brand for s in lic)
        else:
            assert all(d["brands"][s] == brand for s in lic)
            assert all(d["prices"][s] == d["prices"][sid] for s in lic)
            assert d["outcome"]["licensing"]["owners"][sid]["licensees"] == lic
    assert not any(r["stall"] in lic for d in o["days"] if d["day"] >= 3 for r in d["renames"])


def test_licensees_claim_the_owners_quality():
    cfg = _base()
    sid = _owner(cfg)
    c = benchmark.licence_config(cfg, sid, (2, 2))
    log = JsonlLog(keep=True)
    o = bazaar.run(c, log=log)
    lic = _licensees(o, sid)
    world = [json.loads(x) for x in log.lines if '"ev":"world"' in x]
    q_owner = next(s["q_true"] for s in world[1]["stalls"] if s["sid"] == sid)
    for w in world[1:]:
        rows = {s["sid"]: s for s in w["stalls"]}
        for s in lic:
            assert rows[s]["q_pitch"] == q_owner and rows[s]["q_true"] < q_owner and rows[s]["sign"] == "pitch"


def test_licence_draw_is_nested_and_owner_specific():
    cfg = _base()
    o2, sid = _lic(cfg, (2, 2))
    o6, _ = _lic(cfg, (6, 2))
    l2, l6 = _licensees(o2, sid), _licensees(o6, sid)
    assert len(l6) == 6 and set(l2) <= set(l6)
    cat = {st.sid: (st.category, st.stype) for st in BazaarEngine(cfg).stalls}
    assert all(cat[s][0] == cat[sid][0] and cat[s][1] != "genuine" for s in l6)


def test_royalties_are_rho_times_licensee_revenue():
    cfg = _base(extra=["licensing.royalty=0.15"])
    o, sid = _lic(cfg, (2, 2))
    for d in o["days"][1:]:
        L = d["outcome"]["licensing"]["owners"][sid]
        price = d["prices"][sid]
        assert L["royalties_cents"] == L["licensee_units"] * round(0.15 * price)
        assert L["licensee_revenue_cents"] == L["licensee_units"] * price
        bt = d["outcome"]["seller_by_type"]
        assert sum(v["royalty_paid_cents"] for v in bt.values()) == sum(v["royalty_received_cents"] for v in bt.values()) \
            == L["royalties_cents"]
    # the owner's profit includes its royalties
    never = bazaar.run(benchmark.licence_config(cfg, sid, benchmark.NEVER))
    assert benchmark.stall_total(o, sid) != benchmark.stall_total(never, sid)


def test_reviews_of_licensee_sales_land_on_the_brand():
    cfg = _base(cond="B|t40|l1")
    sid = _owner(cfg)
    log = JsonlLog(keep=True)
    o = bazaar.run(benchmark.licence_config(cfg, sid, (2, 2)), log=log)
    lic = set(_licensees(o, sid))
    brand = o["days"][0]["brands"][sid]
    buys = [b for x in log.lines if '"ev":"delta"' in x for b in json.loads(x)["buys"] if b["stall"] in lic]
    day = 0
    seen_profiles = set()
    for x in log.lines:
        if '"ev":"day_start"' in x:
            day = json.loads(x)["day"]
        if day >= 2 and '"ev":"delta"' in x:
            for b in json.loads(x)["buys"]:
                if b["stall"] in lic:
                    assert b["brand"] == brand and b["filed_under"] == brand
                    seen_profiles.add(b["buyer_profile"])
    assert buys and len(seen_profiles) >= 2
    assert o["days"][1]["reviews"][brand][1] > 0
    assert o["days"][-1]["brand_ratings"][brand] < 1.0          # cheap licensees drag the rating down


def test_owner_liable_moves_fines_to_the_owner_and_only_then():
    cfg_n, cfg_y = _base(liable=False), _base(liable=True)
    on, sid = _lic(cfg_n, (2, 2))
    oy, _ = _lic(cfg_y, (2, 2))
    lic = set(_licensees(on, sid))
    caught = sum(d["outcome"]["licensing"]["owners"][sid]["catches_at_licensees"] for d in on["days"][1:])
    assert caught > 0
    assert [d["outcome"]["brands"]["units_by_stall"] for d in on["days"]] == \
           [d["outcome"]["brands"]["units_by_stall"] for d in oy["days"]]          # trading unchanged
    fine = sum(d["outcome"]["licensing"]["owners"][sid]["fines_at_licensees_to_owner_cents"] for d in oy["days"][1:])
    assert fine > 0 and oy["liability"]["by_stall"][sid]["charged_cents"] == fine
    assert sid not in on["liability"]["by_stall"]
    for dn, dy in zip(on["days"], oy["days"]):          # day by day, by payer
        bn, by = dn["outcome"]["liability"]["by_stall"], dy["outcome"]["liability"]["by_stall"]
        if dn["day"] == 1:
            assert bn == by
            continue
        assert sum(bn[s]["charged_cents"] for s in lic if s in bn) == by.get(sid, {}).get("charged_cents", 0)
        assert all(s not in by for s in lic)
        others = set(bn) - lic - {sid}
        assert {s: bn[s] for s in others} == {s: by[s] for s in set(by) - lic - {sid}}
    assert benchmark.stall_total(oy, sid) == benchmark.stall_total(on, sid) - fine


def test_contract_licensees_never_make_false_claims():
    cfg = _base(quality="contract")
    sid = _owner(cfg)
    log = JsonlLog(keep=True)
    o = bazaar.run(benchmark.licence_config(cfg, sid, (6, 2)), log=log)
    lic = set(_licensees(o, sid))
    assert len(lic) == 6
    day = 0
    for x in log.lines:
        if '"ev":"day_start"' in x:
            day = json.loads(x)["day"]
        if day >= 2 and '"ev":"delta"' in x:
            e = json.loads(x)
            assert not any(m["false"] for m in e["msgs"] if m["from"] in lic)
            assert not any(c["stall"] in lic for c in e["catches"])
    assert all(d["outcome"]["licensing"]["owners"][sid]["catches_at_licensees"] == 0 for d in o["days"][1:])


@pytest.mark.parametrize("quality,cond", [("cheap", "B|t100"), ("cheap", "B|t40|l1"), ("contract", "B|t40|l1")])
def test_guard_reads_zero(quality, cond):
    o, _ = _lic(_base(quality=quality, cond=cond), (6, 2))
    assert o["stuck_buyers"]["total"] == 0 and o["idle_choosers"]["total"] == 0
    assert sum(d["outcome"]["fallbacks"]["seller"] + d["outcome"]["fallbacks"]["buyer"] for d in o["days"]) == 0


# n = 0 is allowed from engine 0.17.0 (a schedule with no licensee equals never; tests/test_v0170.py).
@pytest.mark.parametrize("bad", [{"day": 1, "n": 2}, {"day": 2, "n": 11}, {"day": 2, "n": -1}, {"day": 5, "n": 2},
                                 {"day": 2}])
def test_bad_schedules_rejected(bad):
    cfg = _base()
    sid = _owner(cfg)
    cfg.licensing.schedule = {sid: bad}
    with pytest.raises(ValueError):
        bazaar.run(cfg)


@pytest.mark.parametrize("ov", ["licensing.quality=shoddy", "licensing.royalty=1.5"])
def test_bad_settings_rejected(ov):
    cfg = _base(extra=[ov])
    cfg.licensing.schedule = {_owner(cfg): {"day": 2, "n": 2}}
    with pytest.raises(ValueError):
        bazaar.run(cfg)


def test_owner_must_be_genuine():
    cfg = _base()
    dec = next(st.sid for st in BazaarEngine(cfg).stalls if st.stype == "deceptive")
    cfg.licensing.schedule = {dec: {"day": 2, "n": 2}}
    with pytest.raises(ValueError):
        bazaar.run(cfg)


def test_licence_options():
    assert benchmark.licence_options([2, 6], [10, 20], 30) == (benchmark.NEVER, (2, 10), (2, 20), (6, 10), (6, 20))
    with pytest.raises(ValueError):
        benchmark.licence_options([2], [31], 30)


def test_licensing_run_is_deterministic_and_replays():
    cfg = _base(days=3, liable=True, extra=["pricing.penalty_lag_days=1"])
    c = benchmark.licence_config(cfg, _owner(cfg), (2, 2))
    la, lb = JsonlLog(keep=True), JsonlLog(keep=True)
    a, b = bazaar.run(c, log=la), bazaar.run(c, log=lb)
    assert dumps(a) == dumps(b) and la.lines == lb.lines
    _, new = replay(la.lines)
    assert compare_logs(la.lines, new.lines)["identical"]
