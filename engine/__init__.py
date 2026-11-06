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
ENGINE_VERSION = "0.10.0"
