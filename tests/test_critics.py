"""Engine 0.11.0: critics, ties, embarrassment, inspector capture, bargain hunters, the scheduled bust-out policy and the ex-post best bust-out benchmark."""
import hashlib
import json
import os
from types import SimpleNamespace

import pytest

from engine import bazaar, benchmark
from engine import critics as C
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from engine.runner import compare_logs, replay
from tests.guard_strip import changed_in_0140, strip_lines, strip_out

REF = os.path.join(os.path.dirname(__file__), "reference", "outcomes_v0100.json")
BR = ["brands.enabled=true", "brands.premium=0.4", "ratings.mode=public", "inspectors.placement=patrolling",
      "evolution.revise_prob=0", "evolution.mutation_prob=0", "market.horizon_known=true",
      "buyers.budget_factor_override=1.25", "market.ticks=160", "agents.params.rule_deceptive.reopen=fresh"]


def cfg(*ov, seed=0):
    return load(overrides=[*ov, f"seed={seed}"], mode="bazaar")


def _run(c):
    log = JsonlLog(keep=True)
    return bazaar.run(c, log=log), log.lines


def _ref_cells():
    with open(REF, encoding="utf-8") as f:
        return sorted(json.load(f)["cells"].items())


@pytest.mark.parametrize("key,cell", _ref_cells())
def test_defaults_reproduce_engine_0100(key, cell):
    if changed_in_0140(cell):
        pytest.skip("changed on purpose by engine 0.14.0; checked in tests/test_trapped_buyers.py")
    out, lines = _run(cfg(*cell["overrides"], seed=cell["seed"]))
    assert dumps(strip_out(out)) == cell["outcome"]
    assert len(lines) == cell["log_lines"]
    assert hashlib.sha256("\n".join(strip_lines(lines[1:])).encode()).hexdigest() == cell["log_body_sha256"]


def test_inert_settings_change_nothing():
    """Knobs that only matter when their feature is on leave the run unchanged."""
    a, la = _run(cfg(*BR, "market.days=3", seed=2))
    b, lb = _run(cfg(*BR, "market.days=3", "critics.tie_share=0.6", "critics.embarrassment=true",
                     "inspectors.capture_effect=0.5", "buyers.bargain_q_req=[0.3,0.4]", seed=2))
    assert dumps(a) == dumps(b) and la[1:] == lb[1:]


# ------------------------------------------------------------------ critics

def _bust(sid, day):
    return ["agents.seller.genuine=rule_genuine_bust_at",
            f'agents.params.rule_genuine_bust_at.schedule={{"{sid}":{day}}}']


def _genuine(c):
    return [st for st in bazaar.BazaarEngine(c).stalls if st.stype == "genuine"]


def test_critics_observe_true_quality():
    base = cfg(*BR, "market.days=6", seed=3)
    target = _genuine(base)[0]
    c = cfg(*BR, "market.days=6", "critics.count=4", "critics.sample=12", *_bust(target.sid, 3), seed=3)
    q0 = {st.sid: st.q_true for st in bazaar.BazaarEngine(c).stalls}
    out = bazaar.run(c)
    busted = {}
    n = 0
    for d in out["days"]:
        for b in d["bust_outs"]:
            busted[b["stall"]] = (b["day"], b["q_true"])
        for r in d["critic_reviews"]["written"]:
            bd = busted.get(r["stall"])
            expect = bd[1] if bd and bd[0] <= r["day"] else q0[r["stall"]]
            assert r["q_true"] == expect
            assert r["positive"] == (r["q_true"] >= r["claim"] - 1e-12)
            n += 1
    assert n > 100
    assert target.sid in busted and busted[target.sid][0] == 3


def test_tied_critic_negative_review_is_exactly_tie_delay_days_late():
    base = cfg(*BR, "market.days=9", seed=4)
    target = _genuine(base)[1]
    c = cfg(*BR, "market.days=9", "critics.count=3", "critics.sample=48", "critics.tie_share=1",
            "critics.tie_delay=3", *_bust(target.sid, 2), seed=4)
    out = bazaar.run(c)
    filed = {}
    for d in out["days"]:
        for r in d["critic_reviews"]["filed"]:
            filed.setdefault((r["day"], r["critic"], r["stall"]), []).append(d["day"])
    tied_neg = untied_neg = 0
    for d in out["days"]:
        for r in d["critic_reviews"]["written"]:
            key = (r["day"], r["critic"], r["stall"])
            if r["positive"]:
                assert r["delay"] == 0 and filed[key] == [r["day"]]
            elif r["tied"]:
                tied_neg += 1
                assert r["delay"] == 3
                assert filed.get(key, []) == ([r["day"] + 3] if r["day"] + 3 <= 9 else [])
            else:
                untied_neg += 1
                assert r["delay"] == 0 and filed[key] == [r["day"]]
    assert tied_neg >= 3 * 6 and untied_neg > 0          # the busted stall, every critic, days 2-9
    # a review held for 3 days enters the rating update of the day it is filed
    first = min(d for (d0, c0, s), ds in filed.items() for d in ds if s == target.sid and d0 >= 2
                and not next(r for x in out["days"] for r in x["critic_reviews"]["filed"]
                             if (r["day"], r["critic"], r["stall"]) == (d0, c0, s))["positive"])
    assert first == 5


def test_embarrassment_delay_matches_the_formula():
    book = SimpleNamespace(critic_ties={(1, "X")}, critic_hist={(0, "X"): [True, True, False, True],
                                                                (0, "Y"): [True, False, False, False],
                                                                (1, "X"): [False, False]})
    c = SimpleNamespace(critics=SimpleNamespace(tie_delay=4, embarrassment=True, emb_max=10))
    assert C.delay_for(c, book, 0, "X", False) == 8      # p = 0.75 -> 7.5 rounds half up
    assert C.delay_for(c, book, 0, "Y", False) == 3      # p = 0.25 -> 2.5 -> 3
    assert C.delay_for(c, book, 0, "Z", False) == 0      # no earlier review
    assert C.delay_for(c, book, 1, "X", False) == 4      # tied: max(4, 0)
    assert C.delay_for(c, book, 0, "X", True) == 0       # positives are never held
    c.critics.embarrassment = False
    assert C.delay_for(c, book, 0, "X", False) == 0


def test_embarrassment_in_a_run_uses_the_history_written_before_today():
    base = cfg(*BR, "market.days=8", seed=5)
    target = _genuine(base)[0]
    c = cfg(*BR, "market.days=8", "critics.count=2", "critics.sample=48", "critics.embarrassment=true",
            "critics.emb_max=6", *_bust(target.sid, 4), seed=5)
    out = bazaar.run(c)
    hist: dict = {}
    seen = 0
    for d in out["days"]:
        for r in d["critic_reviews"]["written"]:
            h = hist.setdefault((r["critic"], r["brand"]), [])
            if not r["positive"]:
                p = sum(h) / len(h) if h else 0.0
                assert r["delay"] == C.round_half_up(6 * p)
                seen += r["stall"] == target.sid
            h.append(r["positive"])
    assert seen >= 2
    # first negative review of the busted stall: 3 earlier positives of 3 -> held 6 days
    first = next(r for d in out["days"] for r in d["critic_reviews"]["written"]
                 if r["stall"] == target.sid and not r["positive"])
    assert first["day"] == 4 and first["delay"] == 6


def test_critic_ties_are_an_exact_share_of_genuine_pairs():
    c = cfg(*BR, "market.days=2", "critics.count=4", "critics.tie_share=0.3", seed=6)
    eng = bazaar.BazaarEngine(c)
    book = eng.book
    assert len(book.genuine_origin) == sum(st.stype == "genuine" for st in eng.stalls)
    assert len(book.critic_ties) == C.round_half_up(0.3 * 4 * len(book.genuine_origin))
    assert {b for _, b in book.critic_ties} <= set(book.genuine_origin)


# ------------------------------------------------------------------ inspector capture

def test_capture_factor_only_for_tied_dedicated_inspectors():
    c = cfg(*BR, "market.days=2", "inspectors.count=3", "inspectors.capture=0.5", seed=7)
    eng = bazaar.BazaarEngine(c)
    ties = eng.book.capture_ties
    assert ties and len(ties) < 3 * len(eng.book.genuine_origin)
    insp = [p for p in eng.people if p.kind == "inspector"]
    for p in insp:
        for st in eng.stalls:
            f = eng.capture_factor(p, st)
            assert f == (pytest.approx(0.2) if (eng.insp_ord[p.pid], st.brand) in ties else 1.0)
    buyer = eng.buyers[0]
    assert all(eng.capture_factor(buyer, st) == 1.0 for st in eng.stalls)


def test_full_capture_stops_catches_of_tied_brands_only():
    base = cfg(*BR, "market.days=6", "inspectors.count=4", seed=8)
    targets = _genuine(base)[:3]
    sched = "{" + ",".join(f'"{t.sid}":2' for t in targets) + "}"
    ov = [*BR, "market.days=6", "inspectors.count=4", "agents.seller.genuine=rule_genuine_bust_at",
          f"agents.params.rule_genuine_bust_at.schedule={sched}"]
    _, free = _run(cfg(*ov, seed=8))
    _, caught = _run(cfg(*ov, "inspectors.capture=1", "inspectors.capture_effect=1", seed=8))
    ids = {t.sid for t in targets}

    def catches(lines, want):
        return sum(1 for x in lines if '"ev":"delta"' in x for c in json.loads(x)["catches"] if want(c["stall"]))
    assert catches(free, lambda s: s in ids) > 0
    assert catches(caught, lambda s: s in ids) == 0
    assert catches(caught, lambda s: s not in ids) > 0


# ------------------------------------------------------------------ bargain hunters

def test_bargain_hunters_replace_only_q_req():
    a = bazaar.BazaarEngine(cfg(seed=9))
    b = bazaar.BazaarEngine(cfg("buyers.bargain_share=0.3", seed=9))
    n = 0
    for x, y in zip(a.buyers, b.buyers):
        assert (x.pid, x.profile, x.route, x.arrive, x.task["category"], x.task["units"], x.task["budget_cents"]) == \
               (y.pid, y.profile, y.route, y.arrive, y.task["category"], y.task["units"], y.task["budget_cents"])
        if y.task.get("bargain"):
            n += 1
            assert 0.30 <= y.task["q_req"] <= 0.45
        else:
            assert y.task["q_req"] == x.task["q_req"]
    assert 0.2 < n / len(a.buyers) < 0.4


# ------------------------------------------------------------------ profits, policy, benchmark

def test_bust_at_with_nothing_scheduled_is_rule_honest():
    ov = [*BR, "market.days=4"]
    a, la = _run(cfg(*ov, seed=11))
    b, lb = _run(cfg(*ov, "agents.seller.genuine=rule_genuine_bust_at", seed=11))
    strip = lambda s: s.replace("rule_genuine_bust_at-1", "rule_honest-1").replace("rule_genuine_bust_at", "rule_honest")
    assert dumps(a) == strip(dumps(b))
    assert [strip(x) for x in lb[1:]] == la[1:]


def test_scheduled_stall_busts_out_on_its_day_and_no_other_does():
    base = cfg(*BR, "market.days=6", seed=12)
    t = _genuine(base)[2]
    out = bazaar.run(cfg(*BR, "market.days=6", *_bust(t.sid, 4), seed=12))
    busts = [b for d in out["days"] for b in d["bust_outs"]]
    assert [(b["stall"], b["day"]) for b in busts] == [(t.sid, 4)]


def test_benchmark_with_only_never_has_gain_zero():
    c = cfg(*BR, "market.days=3", seed=13)
    sid = _genuine(c)[0].sid
    g = benchmark.best_response(c, sid, candidates=(benchmark.NEVER,))
    assert g["gain_floored"] == 0 and g["gain_unfloored"] is None and g["best_day"] is None


def test_benchmark_gains():
    g = benchmark.gain({benchmark.NEVER: 100, 10: 90, 20: 130, 27: 130})
    assert g["gain_floored"] == 30 and g["gain_unfloored"] == 30 and g["best_day"] == 20
    g = benchmark.gain({benchmark.NEVER: 100, 10: 40, 20: 60})
    assert g["gain_floored"] == 0 and g["gain_unfloored"] == -40 and g["best_day"] == 20


def test_benchmark_runs_the_bust_and_never_chains():
    c = cfg(*BR, "market.days=4", seed=14)
    sid = _genuine(c)[0].sid
    g = benchmark.best_response(c, sid, candidates=(benchmark.NEVER, 2))
    never = bazaar.run(benchmark.bust_config(c, None, None))
    bust = bazaar.run(benchmark.bust_config(c, sid, 2))
    assert g["totals"] == {benchmark.NEVER: benchmark.stall_total(never, sid), 2: benchmark.stall_total(bust, sid)}
    assert [b["stall"] for d in bust["days"] for b in d["bust_outs"]] == [sid]
    with pytest.raises(ValueError):
        benchmark.bust_config(cfg(seed=0), sid, 2)


# ------------------------------------------------------------------ replay and validation

def test_critics_and_capture_log_replays():
    base = cfg(*BR, "market.days=4", seed=15)
    t = _genuine(base)[0]
    log = JsonlLog(keep=True)
    bazaar.run(cfg(*BR, "market.days=4", "critics.count=3", "critics.tie_share=0.5", "critics.embarrassment=true",
                   "inspectors.capture=0.5", "buyers.bargain_share=0.2",
                   *_bust(t.sid, 2), seed=15), log=log)
    _, new = replay(log.lines)
    assert compare_logs(log.lines, new.lines)["identical"]


def test_bad_settings_rejected():
    for ov in (["critics.count=2"], ["inspectors.capture=0.5"], [*BR, "critics.tie_share=1.5", "critics.count=1"],
               [*BR, "critics.count=1", "ratings.mode=off"], ["buyers.bargain_share=2"]):
        with pytest.raises(ValueError):
            bazaar.run(cfg(*ov, "market.days=2", "market.ticks=40"))
