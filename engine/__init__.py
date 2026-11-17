"""Bazaar Markets: a deterministic market-simulation engine.

The engine owns ground truth and accounting. Agents act only at decision
points, through role-specific JSON observations and schema-validated actions.
"""

# Bump when a change can alter the log for the same config, seed and agent outputs.
# 0.2.0: selection/tie-break/cap options, treatment-stable populations and ids.
# 0.3.0: uniformed inspectors, seller sign action, public catch notices,
#        reachable-buyer and false-claim diagnostics in the outcome.
# 0.4.0: inspectors.recognition_range, inspectors.disguised_shift ("full_shift");
#        reachable.shortfall_rate dropped (equal to shortfall_rate by construction).
# 0.5.0: market.scale (grid refinement); rule sellers' whisper_every cooldown.
# 0.6.0: market.days (multi-day runs with between-day entry and exit by imitation),
#        per-day stream roots; discarded logs are no longer serialized (speed only).
# 0.7.0: public ratings (ratings.*), switching costs (pricing.switch_cost_to_*),
#        market.whispers_allowed, rugpull logging. All off by default.
# 0.8.0: brands (brands.*: ratings by brand name, renames at reopening, look-alikes,
#        reputation premium), market.horizon_known, bust-out action and
#        rule_genuine_rational. All off by default.
# 0.9.0: "look-alike" renamed "counterfeit" (rename action, agent parameter, log and outcome
#        fields; "lookalike" still accepted, and 0.8.0 logs replay with the word mapped),
#        buyers.budget_factor_override, rule_genuine_rational_v2 (penalty-aware benchmark with a
#        privileged catch-rate input). All off by default.
# 0.10.0: buyers.search_depth (per-profile search depth: browse k stalls, then buy here or walk back
#         to a stall seen; buyer action "choose"; k = 1 is 0.9.0) and buyers.search_log (per-buyer
#         search records and per-stall exposure in the outcome). Off by default.
# 0.11.0: critics (critics.*: reviewers who file weighted reviews between days, with ties and
#         embarrassment delays on negative reviews), inspector capture (inspectors.capture,
#         capture_effect), bargain hunters (buyers.bargain_share, bargain_q_req), benchmark policy
#         rule_genuine_bust_at and the ex-post best bust-out benchmark (engine/benchmark.py). All off by default (0.10.0 bytes).
# 0.12.0: demand (buyers.demand_mode: "walk" = 0.11.0, or "choice_set": a consideration set of
#         buyers.consider stalls of the buyer's category drawn with position rent
#         buyers.position_rent, a walk along that category's aisle, choice among the set only;
#         bargain_share null = 0 in walk, 0.2 in choice_set) and bust-out benchmark candidates
#         {never, 10, 20, 25, 27, 28, 29}. Walk by default (0.11.0 bytes).
# 0.13.0: verification dial (rule_buyer local_inspect_prob, expert_inspect_prob; draws from the
#         buyer's own agent stream, only when strictly between 0 and 1), benchmark.candidates()
#         for a validated candidate list, and a range check on buyers.bargain_q_req. Defaults
#         reproduce 0.12.0.
# 0.14.0: two search fixes and a guard. (1) Trapped buyers: a searching buyer stays in the "choose"
#         phase once there; before, one that chose at its route end with fewer than search_k stalls
#         seen (a stall closed when passed) reverted to "browse" on walking back and could not buy.
#         (2) Parked buyers: a searching buyer that decides not to buy at the stall it chose drops
#         the target and carries on; before, it stood at that stall for the rest of the day.
#         Guard: outcome stuck_buyers and idle_choosers at the end of each day (multi-day results
#         add per-day and total counts). Runs where neither case occurs reproduce 0.13.0, apart
#         from the two new outcome keys.
# 0.15.0: liability dials. inspectors.detect_scale multiplies every catch probability (the detection
#         draw is consumed whenever the unscaled probability is > 0); pricing.penalty_lag_days: a catch
#         still closes the stall at once, its fine falls due L days later, uncollectible if the stall
#         has exited by then, outstanding at close if due after the last day; seller action "exit"
#         (leave the market for good at the end of the day: closed every later day, in no consideration
#         set, no counterfeit target); rule_genuine_bust_at exit_at; benchmark.exit_candidates.
#         Outcome "liability" (fines charged, deferred, uncollectible, outstanding; exits; catches per
#         deceptive stall), and its run totals in multi-day results. Defaults reproduce 0.14.0, apart
#         from the new outcome key.
# 0.16.0: licensing (licensing.*; engine/licensing.py): at the start of a scheduled day a genuine owner
#         licenses its brand to N non-genuine stalls of its category (dedicated stream [seed, 19, owner
#         index]); licensees bear the name, post the owner's price, claim its quality ("cheap": low true
#         quality, deceptive policy; "contract": the owner's quality, rule_honest), never rename, pay a
#         royalty per unit; reviews of their sales go to the brand; licensing.owner_liable moves fines
#         from catches at licensees to the owner. Outcome "licensing" and royalties in the profit
#         identity, only when on. Defaults reproduce 0.15.0 byte for byte.
# 0.17.0: brands.counterfeit_entry "day" (every deceptive stall copies the top-rated genuine brand of its
#         category at the start of brands.counterfeit_day, claims its quality, never renames; stream
#         [seed, 23]); brands.counterfeit_price_factor (a counterfeit posts phi x the original's price; day
#         log reports counterfeit prices and unit costs, flagging prices below cost); licensing.brand
#         "white_label" (licensees under one fresh unrated brand each, stream [seed, 24, owner index]: no
#         royalty, no tie to the owner); licensing schedules may have n = 0. Defaults reproduce 0.16.0
#         byte for byte.
# 0.18.0: licensing.white_label_tier ("type" = 0.17.0; "genuine": a white label prices at tier 1.0, the owner's
#         formula) and ratings.prior_n (every brand starts with prior_n pseudo-reviews at 0.5, counted in
#         each day's share and fading by ratings.memory per day; brands only). Defaults reproduce 0.17.0
#         byte for byte.
# 0.19.0: ratings.prior_scope ("all" = 0.18.0; "new": the prior reaches only brands created on day 2 or later, so
#         the owner's and every original stall's name rate as with prior_n 0). market.days 60 checked end to end:
#         nothing in the engine or agents assumes 30 days; the horizon (market.horizon_known) is read only by the
#         rule_genuine_rational benchmark sellers. Defaults reproduce 0.18.0 byte for byte.
ENGINE_VERSION = "0.19.0"
