# Plan: Brand Equity at the genuine tier (engine 0.18.0)

Status: plan only, written 2026-11-13 after the Brand Equity results (1c0ed96). Nothing is built or run yet.

## Why

In Brand Equity, white labels are priced at their stall type's tier. A seconds-type white label therefore posts
0.55 × base, below its contract unit cost ($35.69 against $38.87, contract, t40), while the same stall under the
owner's brand posts the owner's price ($67.78). Seconds-type licensees carry $11.5k of the $14.8k contract name
effect, and the white labels' ratings reach 0.98 on their first day. The measured name effect is therefore mostly
the tier, not the reputation. This run prices white labels at the genuine tier, so the only price difference
between R and W is the brand's rating.

## Engine 0.18.0: one key

- `licensing.white_label_tier`: `"type"` (default; 0.17.0 behaviour) | `"genuine"`.
  - Under `"genuine"`, a white-label licensee's tier factor is 1.0, so it posts base × (1 + premium × (rating − 0.5)) from its own brand's rating.
  - This is the same formula as the owner's price, so R and W differ in price only through the rating.
  - The change goes in `engine/brands.py` `tier_factor`, for stalls with `white_label` set, so `premium_price` and `neutral_price` both follow it.
- **What it touches.** Only seconds-type white labels are affected: `pricing.deceptive_price_factor` is already 1.0, so deceptive-type white labels are unchanged.
  - Unit cost depends on true quality, not the tier, so it is unchanged.
  - The fine is 1.5 × base, also independent of the tier.
- **No decision reads it.**
  - `neutral_price_cents` is read only by `rule_genuine_rational(_v2)`'s bust test (`agents/rule_based.py` `should_bust`).
  - That test runs only for honest genuine stalls (`bust_out_unit_cost_cents` is None otherwise), and genuine stalls' tier is 1.0 either way.
  - Prices are engine-set (`morning_prices`).
- Validation: the value must be in ("type", "genuine"). It is ignored unless `licensing.brand` is "white_label".
- `docs/config_reference.md` row, scaling rule NONE, `ENGINE_VERSION` notes.

**Tests (`tests/test_v0180.py`)**
1. **Defaults reproduce 0.17.0 bit for bit.** New reference cells are made at 1c0ed96 (`tests/reference/outcomes_v0170_all.json`): the 110 v0160 cells, plus Canal Street day-entry cells (φ 1.0 and 0.6, t40/t100), plus white-label cells (contract and cheap). The test checks the full-outcome dump and the log-body sha256, with the key unset and with it set explicitly to "type".
2. **The genuine tier posts the formula exactly.** Under "genuine", each white label's posted price equals base × (1 + 0.4 × (rating − 0.5)), rounded as `premium_price`, on every day from licensing. A white label whose rating equals the owner's posts exactly the owner's price.
3. **Only seconds-type white labels change.** With only deceptive-type licensees (a constructed config), "genuine" equals "type" bit for bit.
4. **Owner and R arms are untouched.** "genuine" with `licensing.brand="owner"` equals 0.17.0 bit for bit.
5. Determinism and replay under "genuine"; bad values are rejected; the full suite passes.

## Run: Brand Equity, genuine tier

- **Script:** `analysis/brand_equity_tier.py`, a new frozen script. It reuses `analysis/brand_equity.py`'s job, J, split, royalty check and report code by import, and the frozen script is not edited.
- **Market, owners, licence option, conditions and measures:** as Brand Equity. That means:
  - 3 owners per seed, N 6 from day 10, royalty 0.10;
  - {contract, cheap} × {t40, t100}, detect_scale 1, owner not liable;
  - J over days 10–30, the name effect and its split, the composition effect, the owner's gain at 0.05–0.25 by recompute, the rating paths and PQ5-style buyer rows.
- **Arms:** never, R, W_g (white label at the genuine tier), and, if you choose (decision 2), W_t (the 0.17.0 white label at its type's tier).
  - With W_t in the run, the old name effect R − W_t splits exactly into a reputation part R − W_g and a tier part W_g − W_t, on the same seeds.
- **Chains:** never 60, R 360, W_g 360, W_t 360 (optional), royalty check 12.
- **Wall clock:** about 8 s per chain on 4 workers at load ≈ 6 (Brand Equity: 792 chains in 1.72 h).
  - Without W_t: 792 chains, about 1.7 h.
  - With W_t: 1,152 chains, about 2.5 h.
  - If seeds 300–329 are reused (decision 1), never and R could come from the cached 0.17.0 chains after an identity check. Only W_g (and W_t) would then run: about 0.8 h or 1.6 h. The run record would then mix two engine versions.
- **Predictions:** yours to write and fix before the pilot, copied verbatim into the design section. The script will report each against its interval as before. For reference, these are the 0.17.0 name effects they would be compared with (contract t40 +$14,819; contract t100 +$15,279; cheap t40 +$2,499; cheap t100 +$8,694).

## Pilot gate (seeds 900–902)

- **G1:** the pipeline runs end to end and the summary renders.
- **G2:** identities.
  - (a) never and R chains equal Brand Equity's 0.17.0 chains for the same seeds (full-outcome digest, worktree at 1c0ed96).
  - (b) W_t chains equal 0.17.0 W chains.
  - (c) J identity to the cent; the split adds up.
  - (d) The royalty no-decision replay passes.
  - (e) Under W_g, every seconds-type white label's posted price equals the formula on every day.
- **G3:** each run is projected at ≤ 5.5 h on 4 workers at nice 19; if over, seeds are cut to 20.
- **G4:** contract seconds-type white labels under W_g price above unit cost on > 90% of stall-days. Reported, design unchanged.
- **G5:** stuck, parked and idle buyers are 0 in every pilot chain.

## Order of work

1. Engine 0.18.0, tests, reference cells, docs; commit the engine.
2. Run script and pilot script; commit.
3. Pilot; gate report `runs/pilot_brand_equity_tier.md`; queue script `runs/queue_brand_equity_tier.sh`; commit; stop and report the launch command.
4. After your go, run detached (nohup), then the summary reading and caveats.

## Decisions for you

1. **Seeds:** fresh seeds 330–359 (an independent replication of R and never), or reuse 300–329 (W_g paired directly against the existing R and W chains).
2. **Include W_t in the new run?** Yes gives an exact reputation/tier split on the same seeds (+0.8 h); no compares against the 0.17.0 run.
3. **Predictions:** the new PQs, written by you and fixed before the pilot.
