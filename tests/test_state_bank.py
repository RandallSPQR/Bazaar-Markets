"""analysis/state_bank.py on synthetic lotteries: labels, split-half agreement, collection, allocation, markets."""
import analysis.state_bank as SB


def _lot(means, K=20, noise=1.0):
    out = {}
    for j, (o, m) in enumerate(means.items()):
        out[o] = {"pay": [m + noise * (((k * 7 + j * 3) % 5) - 2) for k in range(K)], "caught": [False] * K}
    out.setdefault("exit", {"pay": [0] * K, "caught": [False] * K})
    return out


def test_markets_and_hidden():
    assert len(SB.MARKETS) == 8
    h = SB.hidden("t100|ds0|pn10new")
    assert (h["tourist_share"], h["detect_scale"], h["prior_n"], h["prior_scope"]) == (1.0, 0.0, 10.0, "new")
    h = SB.hidden("t40|ds1|pn0")
    assert (h["tourist_share"], h["detect_scale"], h["prior_n"]) == (0.4, 1.0, 0.0)
    assert set(SB.NEUTRAL) == set(SB.OPTIONS)


def test_labels_best_pays_and_close_call():
    lot = _lot({"honest": 100, "switch_now": 150, "switch_d5": 120, "switch_d10": 110, "license_contract_6": 90,
                "license_cheap_6": 80})
    lab = SB.labels(lot)
    assert lab["best"] == "switch_now" and lab["second"] == "switch_d5" and lab["pays"]
    assert lab["best_paying_option"] == "switch_now" and lab["paying_minus_honest"] == 50
    assert not lab["close_call"]
    lab = SB.labels(_lot({"honest": 100, "switch_now": 100.1, "switch_d5": 50, "switch_d10": 50,
                          "license_contract_6": 50, "license_cheap_6": 50}, noise=5.0))
    assert lab["close_call"]
    lab = SB.labels(_lot({"honest": 100, "switch_now": 10, "switch_d5": 10, "switch_d10": 10,
                          "license_contract_6": 200, "license_cheap_6": 20}))
    assert lab["best"] == "license_contract_6" and not lab["pays"]


def test_split_half_and_collect():
    lots = {"a": _lot({"honest": 100, "switch_now": 150, "switch_d5": 0, "switch_d10": 0, "license_contract_6": 0,
                       "license_cheap_6": 0}, K=30)}
    r = SB.split_half(lots, 20)
    assert r == {"K": 20, "states": 1, "agree": 1, "share": 1.0}
    st = [{"id": "m|1|5|s01", "market": "m", "seed": 1, "d": 5, "stall": "s01"}]
    res = {"s01": {o: {"pay": [k for k in range(2)], "caught": [False, True]} for o in SB.SIM_OPTIONS}}
    recs = [{"market": "m", "seed": 1, "d": 5, "sids": ["s01"], "k0": 2, "k1": 4, "res": res},
            {"market": "m", "seed": 1, "d": 5, "sids": ["s01"], "k0": 0, "k1": 2,
             "res": {"s01": {o: {"pay": [10, 11], "caught": [True, False]} for o in SB.SIM_OPTIONS}}}]
    lot = SB.collect(recs, st, 4)["m|1|5|s01"]
    assert lot["honest"]["pay"] == [10, 11, 0, 1] and lot["exit"]["pay"] == [0, 0, 0, 0]


def test_allocation_targets_half():
    states = [{"id": f"{m}|{s}|{d}|x", "market": m, "seed": s, "d": d, "stall": "x"}
              for m in SB.MARKETS for d in SB.DAYS for s in range(30)]
    C = SB.cells(states)
    ps = SB.pilot_states(states)
    assert len(ps) == 32
    paying = {m: i % 2 == 0 for i, m in enumerate(SB.MARKETS)}
    lab = {s["id"]: {"pays": paying[s["market"]]} for s in ps}
    al = SB.allocation(lab, ps, C)
    assert sum(al["alloc"].values()) == SB.N_BANK
    bank = SB.bank_states(states, ps, al["alloc"])
    assert len(bank) == SB.N_BANK and all(s["id"] in {b["id"] for b in bank} for s in ps)
    assert abs(sum(paying[b["market"]] for b in bank) - 100) <= 4
    assert all(b["weight"] == b["cell_size"] / b["cell_drawn"] for b in bank)
